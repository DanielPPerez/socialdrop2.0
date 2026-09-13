from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from socialdrop.platforms.base import (
    MAX_RETRIES,
    RETRYABLE_STATUS,
    BasePlatformAdapter,
    Metrics,
    PublishError,
    PublishResult,
)
from socialdrop.platforms.exceptions import (
    PlatformAuthError,
    PlatformRateLimitError,
    PlatformTimeoutError,
)
from socialdrop.schema import PlatformConfig


class MockAdapter(BasePlatformAdapter):
    name = "mock"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        return PublishResult(
            platform=self.name,
            url=f"https://mock.social/@demo/video/{video_path.stem}",
            post_id=video_path.stem,
            raw={"simulated": True},
        )

    async def get_stats(self, post_id: str, meta: PlatformConfig, token: dict | None = None) -> Metrics | None:
        seed = sum(ord(c) for c in post_id) % 1000
        return Metrics(
            views=1000 + seed * 7,
            likes=100 + seed % 50,
            comments=seed % 20,
            shares=(seed * 3) % 40,
            raw={"simulated": True},
        )

    async def is_ready(self) -> tuple[bool, str]:
        return True, "mock always ready"

    async def authenticate(self, redirect_uri: str | None = None) -> dict:
        return {"access_token": "mock-token", "expires_at": int(time.time()) + 3600}


async def _request_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.request(method, url, **kwargs)
        except httpx.TimeoutException:
            last_error = "timeout"
            if attempt == MAX_RETRIES:
                raise PlatformTimeoutError(
                    f"{method} {url} timed out after {MAX_RETRIES} attempts"
                ) from None
            await asyncio.sleep(min(2**attempt, 30))
            continue
        except httpx.TransportError as exc:
            last_error = str(exc)
            if attempt == MAX_RETRIES:
                raise PublishError(
                    f"{method} {url} failed after {MAX_RETRIES} attempts: {last_error}", retryable=True
                ) from None
            await asyncio.sleep(min(2**attempt, 30))
            continue
        if resp.status_code not in RETRYABLE_STATUS:
            return resp
        if attempt == MAX_RETRIES:
            break
        await asyncio.sleep(min(2**attempt, 30))
    raise PlatformRateLimitError(f"{method} {url} failed after {MAX_RETRIES} attempts: {last_error}")


def raise_api_error(platform: str, resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    body = resp.text[:500]
    retryable = resp.status_code in RETRYABLE_STATUS
    if resp.status_code == 401:
        raise PlatformAuthError(f"{platform} API error {resp.status_code}: {body}")
    if resp.status_code == 403:
        raise PlatformAuthError(f"{platform} API error {resp.status_code}: {body}")
    if resp.status_code == 429:
        raise PlatformRateLimitError(f"{platform} API error {resp.status_code}: {body}")
    raise PublishError(f"{platform} API error {resp.status_code}: {body}", retryable=retryable)


YOUTUBE_CATEGORY_IDS = {
    "film & animation": "1",
    "music": "10",
    "pets & animals": "15",
    "sports": "17",
    "travel & events": "19",
    "gaming": "20",
    "videoblogging": "21",
    "people & blogs": "22",
    "comedy": "23",
    "entertainment": "24",
    "news & politics": "25",
    "howto & style": "26",
    "education": "27",
    "science & technology": "28",
    "nonprofits & activism": "29",
}


class YouTubeAdapter(BasePlatformAdapter):
    name = "youtube"
    requires = ()

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("youtube not authenticated")
        access_token = token.get("access_token") or token.get("token")
        if not access_token:
            raise PlatformAuthError("youtube token missing access_token")
        caption = meta.caption or ""
        title = meta.get("title") or (caption.splitlines()[0] if caption else "") or video_path.stem
        description = meta.get("description") or caption
        raw_tags = meta.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",")]
        hashtags = meta.hashtags or []
        tags = [str(t).strip().lstrip("#") for t in list(raw_tags) + hashtags if str(t).strip()]
        category_id = YOUTUBE_CATEGORY_IDS.get(str(meta.get("category") or "").lower(), "22")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": bool(meta.get("madeForKids", False)),
                "license": "creativeCommon" if meta.get("license") == "creativeCommon" else "youtube",
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
            }
            init = await _request_with_retry(
                client,
                "POST",
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"part": "snippet,status", "uploadType": "resumable"},
                json=body,
                headers=headers,
            )
            raise_api_error(self.name, init)
            upload_url = init.headers.get("Location")
            if not upload_url:
                raise PublishError("youtube init missing Location header", retryable=True)

            size = video_path.stat().st_size
            with open(video_path, "rb") as fh:
                data = fh.read()
            put = await client.put(
                upload_url,
                content=data,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                },
            )
            if put.status_code == 308:
                raise PublishError("youtube resumable upload requires chunking", retryable=False)
            raise_api_error(self.name, put)
            video_id = put.json().get("id")
            if not video_id:
                raise PublishError("youtube upload response missing id", retryable=True)
        return PublishResult(
            platform=self.name,
            url=f"https://youtu.be/{video_id}",
            post_id=video_id,
            raw=put.json(),
        )

    async def get_stats(self, post_id: str, meta: PlatformConfig, token: dict | None = None) -> Metrics | None:
        if token is None:
            return None
        access_token = token.get("access_token") or token.get("token")
        if not access_token:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": post_id},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 401:
                raise PlatformAuthError("youtube stats auth failed")
            if resp.status_code >= 400:
                raise PublishError(f"youtube stats error {resp.status_code}", retryable=True)
            items = resp.json().get("items", [])
            if not items:
                return None
            stats = items[0].get("statistics", {})
            return Metrics(
                views=int(stats.get("viewCount", 0)) or None,
                likes=int(stats.get("likeCount", 0)) or None,
                comments=int(stats.get("commentCount", 0)) or None,
                raw=stats,
            )


class TikTokAdapter(BasePlatformAdapter):
    name = "tiktok"
    API = "https://open.tiktokapis.com/v2"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("tiktok not authenticated")
        access_token = token.get("access_token")
        if not access_token:
            raise PlatformAuthError("tiktok token missing access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        privacy = meta.get("privacy", "PUBLIC_TO_EVERYONE")
        init_body = {
            "post_info": {
                "title": (meta.caption or video_path.stem)[:2200],
                "privacy_level": privacy,
                "disable_duet": not bool(meta.get("duet", False)),
                "disable_comment": not bool(meta.get("comments", True)),
                "disable_stitch": not bool(meta.get("stitch", False)),
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_path.stat().st_size,
                "chunk_size": video_path.stat().st_size,
                "total_chunk_count": 1,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await _request_with_retry(
                client, "POST", f"{self.API}/post/publish/video/init/", json=init_body, headers=headers
            )
            raise_api_error(self.name, resp)
            data = resp.json()
            error = data.get("error", {})
            if error.get("code") not in ("ok", "", 0, None):
                raise PublishError(f"tiktok init failed: {error}")
            upload_url = data["data"]["upload_url"]
            with open(video_path, "rb") as fh:
                put = await _request_with_retry(
                    client,
                    "PUT",
                    upload_url,
                    content=fh.read(),
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes 0-{video_path.stat().st_size - 1}/{video_path.stat().st_size}",
                    },
                )
            if put.status_code >= 400:
                raise PublishError(f"tiktok upload failed: {put.status_code} {put.text[:300]}", retryable=True)
            post_id = data["data"].get("publish_id")
        return PublishResult(
            platform=self.name,
            url=f"https://www.tiktok.com/upload/{post_id}" if post_id else None,
            post_id=post_id,
            raw=data,
        )


class InstagramAdapter(BasePlatformAdapter):
    name = "instagram"
    GRAPH = "https://graph.facebook.com/v21.0"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("instagram not authenticated")
        access_token = token.get("access_token")
        if not access_token:
            raise PlatformAuthError("instagram token missing access_token")
        ig_user_id = meta.get("ig_user_id")
        if not ig_user_id:
            ig_user_id = await self._resolve_ig_user_id(access_token)
        caption = meta.caption or ""
        params = {
            "media_type": "REELS",
            "caption": caption,
            "access_token": access_token,
        }
        public_url = meta.url
        if public_url:
            params["video_url"] = public_url
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await _request_with_retry(client, "POST", f"{self.GRAPH}/{ig_user_id}/media", data=params)
            raise_api_error(self.name, resp)
            container_id = resp.json()["id"]

            if not public_url:
                await self._rupload(client, container_id, video_path, access_token)

            status = await self._wait_container(client, container_id, access_token)
            pub = await _request_with_retry(
                client,
                "POST",
                f"{self.GRAPH}/{ig_user_id}/media_publish",
                data={"creation_id": container_id, "access_token": access_token},
            )
            raise_api_error(self.name, pub)
            media_id = pub.json().get("id")

        permalink = status.get("permalink") if isinstance(status, dict) else None
        return PublishResult(
            platform=self.name,
            url=permalink or f"https://www.instagram.com/reel/{media_id}/" if media_id else None,
            post_id=media_id,
            raw={"container": container_id, "publish": pub.json()},
        )

    async def _resolve_ig_user_id(self, token: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(f"{self.GRAPH}/me/accounts", params={"access_token": token})
            raise_api_error(self.name, resp)
            pages = resp.json().get("data", [])
            if not pages:
                raise PlatformAuthError("no Facebook Page found; link your IG Business account to a Page first")
            page_id = pages[0]["id"]
            resp = await client.get(
                f"{self.GRAPH}/{page_id}",
                params={"fields": "instagram_business_account", "access_token": token},
            )
            raise_api_error(self.name, resp)
            ig = resp.json().get("instagram_business_account")
            if not ig:
                raise PlatformAuthError("no Instagram Business account linked to the first Page")
            return ig["id"]

    async def _rupload(self, client: httpx.AsyncClient, container_id: str, video_path: Path, token: str) -> None:
        size = video_path.stat().st_size
        headers = {
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(size),
        }
        with open(video_path, "rb") as fh:
            resp = await client.post(
                f"https://rupload.facebook.com/ig-api-upload/{container_id}",
                headers=headers,
                content=fh.read(),
            )
        if resp.status_code >= 400:
            raise PublishError(f"instagram rupload failed: {resp.status_code} {resp.text[:300]}")

    async def _wait_container(
        self, client: httpx.AsyncClient, container_id: str, token: str, timeout: int = 600
    ) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = await _request_with_retry(
                client,
                "GET",
                f"{self.GRAPH}/{container_id}",
                params={"fields": "status_code,status,permalink", "access_token": token},
            )
            raise_api_error(self.name, resp)
            data = resp.json()
            code = data.get("status_code")
            if code == "FINISHED":
                return data
            if code == "ERROR":
                raise PublishError(f"instagram container error: {data.get('status')}")
            await asyncio.sleep(5)
        raise PublishError("instagram container timed out", retryable=True)


class XAdapter(BasePlatformAdapter):
    name = "x"
    API = "https://api.x.com/2"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("x not authenticated")
        access_token = token.get("access_token")
        if not access_token:
            raise PlatformAuthError("x token missing access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        text = meta.caption or video_path.stem
        async with httpx.AsyncClient(timeout=300) as client:
            init = await _request_with_retry(
                client,
                "POST",
                f"{self.API}/media/upload/initialize",
                json={
                    "total_bytes": video_path.stat().st_size,
                    "media_type": "video/mp4",
                    "media_category": "tweet_video",
                },
                headers=headers,
            )
            raise_api_error(self.name, init)
            media_id = init.json()["data"]["id"]

            with open(video_path, "rb") as fh:
                index = 0
                while chunk := fh.read(4 * 1024 * 1024):
                    append = await _request_with_retry(
                        client,
                        "POST",
                        f"{self.API}/media/upload/{media_id}/append",
                        files={"chunk": (f"segment_{index}", chunk)},
                        data={"segment_index": str(index)},
                        headers=headers,
                    )
                    if append.status_code == 204 or append.status_code < 400:
                        index += 1
                        continue
                    raise_api_error(self.name, append)

            finalize = await _request_with_retry(
                client, "POST", f"{self.API}/media/upload/{media_id}/finalize", headers=headers
            )
            raise_api_error(self.name, finalize)
            processing = finalize.json().get("data", {}).get("processing_info")
            if processing:
                await self._wait_processing(client, media_id, processing, headers)

            tweet = await _request_with_retry(
                client,
                "POST",
                f"{self.API}/tweets",
                json={"text": text[:280], "media": {"media_ids": [media_id]}},
                headers=headers,
            )
            raise_api_error(self.name, tweet)
            data = tweet.json()["data"]
        username = data.get("username") or "i"
        return PublishResult(
            platform=self.name,
            url=f"https://x.com/{username}/status/{data['id']}",
            post_id=data["id"],
            raw=tweet.json(),
        )

    async def _wait_processing(self, client: httpx.AsyncClient, media_id: str, info: dict, headers: dict) -> None:
        while info.get("state") in ("pending", "in_progress"):
            await asyncio.sleep(info.get("check_after_secs", 5))
            resp = await _request_with_retry(
                client, "GET", f"{self.API}/media/upload/{media_id}", params={}, headers=headers
            )
            raise_api_error(self.name, resp)
            info = resp.json().get("data", {}).get("processing_info", {})
        if info.get("state") == "failed":
            raise PublishError(f"x media processing failed: {info}")


class LinkedInAdapter(BasePlatformAdapter):
    name = "linkedin"
    API = "https://api.linkedin.com"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("linkedin not authenticated")
        access_token = token.get("access_token")
        if not access_token:
            raise PlatformAuthError("linkedin token missing access_token")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "LinkedIn-Version": "202401",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        async with httpx.AsyncClient(timeout=300) as client:
            me = await _request_with_retry(client, "GET", f"{self.API}/v2/userinfo", headers=headers)
            raise_api_error(self.name, me)
            owner_urn = f"urn:li:person:{me.json()['sub']}"

            init = await _request_with_retry(
                client,
                "POST",
                f"{self.API}/rest/videos?action=initializeUpload",
                headers=headers,
                json={"initializeUploadRequest": {"owner": owner_urn, "fileSizeBytes": video_path.stat().st_size}},
            )
            raise_api_error(self.name, init)
            init_data = init.json()["value"]
            upload_token = init_data["uploadToken"]
            upload_instructions = init_data["uploadInstructions"]

            etags = []
            for instruction in upload_instructions:
                with open(video_path, "rb") as fh:
                    fh.seek(instruction["byteRange"]["firstByte"])
                    part = fh.read(instruction["byteRange"]["lastByte"] - instruction["byteRange"]["firstByte"] + 1)
                put = await client.put(
                    instruction["uploadUrl"],
                    content=part,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if put.status_code >= 400:
                    raise PublishError(f"linkedin part upload failed: {put.status_code}", retryable=True)
                etag = put.headers.get("etag")
                if etag:
                    etags.append({"etag": etag})

            finalize = await _request_with_retry(
                client,
                "POST",
                f"{self.API}/rest/videos?action=finalizeUpload",
                headers=headers,
                json={
                    "finalizeUploadRequest": {
                        "video": init_data["video"],
                        "uploadToken": upload_token,
                        "uploadedPartIds": etags,
                    }
                },
            )
            raise_api_error(self.name, finalize)
            video_urn = init_data["video"]

            post = await _request_with_retry(
                client,
                "POST",
                f"{self.API}/v2/ugcPosts",
                headers=headers,
                json={
                    "author": owner_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": meta.caption or video_path.stem},
                            "shareMediaCategory": "VIDEO",
                            "media": [{"status": "READY", "media": video_urn}],
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                },
            )
            raise_api_error(self.name, post)
            post_urn = post.headers.get("x-restli-id", "")

        return PublishResult(
            platform=self.name,
            url=f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None,
            post_id=post_urn,
            raw={"videoUrn": video_urn},
        )


class BlueskyAdapter(BasePlatformAdapter):
    name = "bluesky"
    SERVICE = "https://bsky.social"

    async def publish(self, video_path: Path, meta: PlatformConfig, token: dict | None = None) -> PublishResult:
        if token is None:
            raise PlatformAuthError("bluesky not authenticated")
        handle = token.get("identifier") or token.get("handle")
        password = token.get("password")
        access_jwt = token.get("accessJwt") or token.get("access_token")
        did = token.get("did")
        if not access_jwt or not did:
            if not handle or not password:
                raise PlatformAuthError(
                    "bluesky not configured; set SOCIALDROP_BLUESKY_HANDLE and SOCIALDROP_BLUESKY_APP_PASSWORD"
                )
            session = await self._login(handle, password)
            access_jwt = session["accessJwt"]
            did = session["did"]
            handle = session["handle"]
        else:
            handle = handle or token.get("identifier", "did")

        async with httpx.AsyncClient(timeout=120) as client:
            blob_ref = await self._upload_blob(client, access_jwt, video_path)
            caption_parts = [meta.caption or video_path.stem]
            tags = meta.hashtags or []
            if tags:
                caption_parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags))
            text = "\n\n".join(caption_parts)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            record = {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "text": text,
                    "createdAt": now,
                    "embed": {
                        "$type": "app.bsky.embed.video",
                        "video": {
                            "$type": "blob",
                            "ref": {"$link": blob_ref["ref"]},
                            "mimeType": blob_ref["mimeType"],
                            "size": blob_ref["size"],
                        },
                    },
                },
            }
            resp = await _request_with_retry(
                client,
                "POST",
                f"{self.SERVICE}/xrpc/com.atproto.repo.createRecord",
                headers={
                    "Authorization": f"Bearer {access_jwt}",
                    "Content-Type": "application/json",
                },
                json=record,
            )
            if resp.status_code == 401:
                raise PlatformAuthError(f"bluesky auth failed: {resp.text[:200]}")
            if resp.status_code >= 400:
                raise PublishError(f"bluesky createRecord failed {resp.status_code}: {resp.text[:300]}")
            uri = resp.json().get("uri", "")
        rkey = uri.rsplit("/", 1)[-1]
        return PublishResult(
            platform=self.name,
            url=f"https://bsky.app/profile/{handle}/post/{rkey}",
            post_id=rkey,
            raw={"uri": uri},
        )

    async def _login(self, handle: str, password: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.SERVICE}/xrpc/com.atproto.server.createSession",
                json={"identifier": handle, "password": password},
            )
            if resp.status_code == 401:
                raise PlatformAuthError("bluesky app password rejected")
            if resp.status_code >= 400:
                raise PublishError(f"bluesky login failed {resp.status_code}: {resp.text[:300]}")
            return resp.json()

    async def _upload_blob(self, client: httpx.AsyncClient, access_jwt: str, video_path: Path) -> dict:
        with open(video_path, "rb") as fh:
            resp = await _request_with_retry(
                client,
                "POST",
                f"{self.SERVICE}/xrpc/com.atproto.repo.uploadBlob",
                headers={
                    "Authorization": f"Bearer {access_jwt}",
                    "Content-Type": "video/mp4",
                },
                content=fh.read(),
            )
        if resp.status_code == 401:
            raise PlatformAuthError("bluesky upload auth failed")
        if resp.status_code >= 400:
            raise PublishError(f"bluesky upload failed {resp.status_code}: {resp.text[:300]}")
        blob = resp.json().get("blob", {})
        return {
            "ref": blob.get("ref", {}),
            "mimeType": blob.get("mimeType", "video/mp4"),
            "size": blob.get("size", video_path.stat().st_size),
        }

    async def get_stats(self, post_id: str, meta: PlatformConfig, token: dict | None = None) -> Metrics | None:
        if token is None:
            return None
        did = token.get("did") or token.get("identifier")
        handle = token.get("identifier") or token.get("handle")
        if not did or not handle or not post_id:
            return None
        uri = f"at://{did}/app.bsky.feed.post/{post_id}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.SERVICE}/xrpc/app.bsky.feed.getPostThread",
                params={"uri": uri},
                headers={"Authorization": f"Bearer {token.get('accessJwt', token.get('access_token', ''))}"},
            )
            if resp.status_code == 401:
                raise PlatformAuthError("bluesky stats auth failed")
            if resp.status_code >= 400:
                raise PublishError(f"bluesky stats error {resp.status_code}", retryable=True)
            thread = resp.json().get("thread", {})
            post = thread.get("post", {})
            return Metrics(
                likes=post.get("likeCount"),
                comments=post.get("replyCount"),
                shares=post.get("repostCount"),
                raw=post,
            )

    async def is_ready(self) -> tuple[bool, str]:
        from socialdrop.auth.store import load_token

        if load_token(self.name) is not None:
            return True, "authenticated"
        return False, "run 'socialdrop auth login bluesky' (app password)"


ADAPTERS = [
    MockAdapter(),
    YouTubeAdapter(),
    TikTokAdapter(),
    InstagramAdapter(),
    XAdapter(),
    LinkedInAdapter(),
    BlueskyAdapter(),
]
