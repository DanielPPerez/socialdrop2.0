from __future__ import annotations

import time
from pathlib import Path

import httpx

from socialdrop.platforms.base import (
    MAX_RETRIES,
    RETRYABLE_STATUS,
    Metrics,
    PlatformAdapter,
    PublishError,
    PublishResult,
)
from socialdrop.schema import PlatformConfig


class MockAdapter(PlatformAdapter):
    """Always succeeds without network. Used by 'socialdrop demo' and tests."""

    name = "mock"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        return PublishResult(
            platform=self.name,
            url=f"https://mock.social/@demo/video/{video_path.stem}",
            post_id=video_path.stem,
            raw={"simulated": True},
        )

    def metrics(self, post_id: str, meta: PlatformConfig) -> Metrics:
        seed = sum(ord(c) for c in post_id) % 1000
        return Metrics(
            views=1000 + seed * 7,
            likes=100 + seed % 50,
            comments=seed % 20,
            shares=(seed * 3) % 40,
            raw={"simulated": True},
        )

    def is_ready(self) -> tuple[bool, str]:
        return True, "mock always ready"


def _request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last_error = str(exc)
            resp = None  # type: ignore[assignment]
        if resp is not None and resp.status_code not in RETRYABLE_STATUS:
            return resp
        if attempt == MAX_RETRIES:
            break
        time.sleep(min(2**attempt, 30))
    raise PublishError(f"{method} {url} failed after {MAX_RETRIES} attempts: {last_error}", retryable=True)


def raise_api_error(platform: str, resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    body = resp.text[:500]
    retryable = resp.status_code in RETRYABLE_STATUS
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


class YouTubeAdapter(PlatformAdapter):
    name = "youtube"
    requires = ("google-api-python-client", "google-auth-oauthlib")

    def _service(self):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise PublishError(
                f"missing dependency; install with: pip install socialdrop[youtube] ({exc})"
            ) from exc
        from socialdrop.auth import store

        token = store.load_token(self.name)
        if token is None:
            raise PublishError("youtube not authenticated", retryable=False)
        creds = Credentials(token=token["access_token"], refresh_token=token.get("refresh_token"))
        return build("youtube", "v3", credentials=creds), MediaFileUpload

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        import os

        service, MediaFileUpload = self._service()
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
                "privacyStatus": os.environ.get("SOCIALDROP_YOUTUBE_PRIVACY", "private"),
                "selfDeclaredMadeForKids": bool(meta.get("madeForKids", False)),
                "license": "creativeCommon" if meta.get("license") == "creativeCommon" else "youtube",
            },
        }
        media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response: dict = {}
        while not response:
            _, response = request.next_chunk()
        video_id = response["id"]
        return PublishResult(
            platform=self.name, url=f"https://youtu.be/{video_id}", post_id=video_id, raw=response
        )

    def metrics(self, post_id: str, meta: PlatformConfig) -> Metrics | None:
        service, _ = self._service()
        resp = service.videos().list(part="statistics", id=post_id).execute()
        items = resp.get("items", [])
        if not items:
            return None
        stats = items[0].get("statistics", {})
        return Metrics(
            views=int(stats.get("viewCount", 0)) or None,
            likes=int(stats.get("likeCount", 0)) or None,
            comments=int(stats.get("commentCount", 0)) or None,
            raw=stats,
        )


class TikTokAdapter(PlatformAdapter):
    name = "tiktok"
    API = "https://open.tiktokapis.com/v2"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        from socialdrop.auth.oauth import get_access_token

        headers = {"Authorization": f"Bearer {get_access_token('tiktok')}"}
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
                "chunk_size": min(video_path.stat().st_size, 64 * 1024 * 1024),
                "total_chunk_count": 1,
            },
        }
        with httpx.Client(timeout=120) as client:
            resp = _request_with_retry(
                client, "POST", f"{self.API}/post/publish/video/init/", json=init_body, headers=headers
            )
            raise_api_error(self.name, resp)
            data = resp.json()
            if data.get("error", {}).get("code") not in ("ok", ""):
                raise PublishError(f"tiktok init failed: {data['error']}")
            upload_url = data["data"]["upload_url"]
            with open(video_path, "rb") as fh:
                put = _request_with_retry(
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


class InstagramAdapter(PlatformAdapter):
    """Requires an Instagram Business/Creator account and a public video URL.

    Meta fetches video_url itself; local files are uploaded via the resumable
    endpoint when possible, otherwise set platforms.instagram.url in frontmatter.
    """

    name = "instagram"
    GRAPH = "https://graph.facebook.com/v21.0"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        from socialdrop.auth.oauth import get_access_token

        token = get_access_token("instagram")
        ig_user_id = meta.get("ig_user_id")
        if not ig_user_id:
            ig_user_id = self._resolve_ig_user_id(token)
        caption = meta.caption or ""

        params = {
            "media_type": "REELS",
            "caption": caption,
            "access_token": token,
        }
        public_url = meta.url
        if public_url:
            params["video_url"] = public_url
        with httpx.Client(timeout=120) as client:
            resp = _request_with_retry(client, "POST", f"{self.GRAPH}/{ig_user_id}/media", data=params)
            raise_api_error(self.name, resp)
            container_id = resp.json()["id"]

            if not public_url:
                self._rupload(client, container_id, video_path, token)

            status = self._wait_container(client, container_id, token)
            pub = _request_with_retry(
                client,
                "POST",
                f"{self.GRAPH}/{ig_user_id}/media_publish",
                data={"creation_id": container_id, "access_token": token},
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

    def _resolve_ig_user_id(self, token: str) -> str:
        with httpx.Client(timeout=60) as client:
            resp = client.get(f"{self.GRAPH}/me/accounts", params={"access_token": token})
            raise_api_error(self.name, resp)
            pages = resp.json().get("data", [])
            if not pages:
                raise PublishError(
                    "no Facebook Page found; link your IG Business account to a Page first"
                )
            page_id = pages[0]["id"]
            resp = client.get(
                f"{self.GRAPH}/{page_id}",
                params={"fields": "instagram_business_account", "access_token": token},
            )
            raise_api_error(self.name, resp)
            ig = resp.json().get("instagram_business_account")
            if not ig:
                raise PublishError("no Instagram Business account linked to the first Page")
            return ig["id"]

    def _rupload(self, client: httpx.Client, container_id: str, video_path: Path, token: str) -> None:
        size = video_path.stat().st_size
        headers = {
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(size),
        }
        with open(video_path, "rb") as fh:
            resp = client.post(
                f"https://rupload.facebook.com/ig-api-upload/{container_id}",
                headers=headers,
                content=fh.read(),
            )
        if resp.status_code >= 400:
            raise PublishError(f"instagram rupload failed: {resp.status_code} {resp.text[:300]}")

    def _wait_container(self, client: httpx.Client, container_id: str, token: str, timeout: int = 600) -> dict:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = _request_with_retry(
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
            time.sleep(5)
        raise PublishError("instagram container timed out", retryable=True)


class XAdapter(PlatformAdapter):
    name = "x"
    API = "https://api.x.com/2"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        from socialdrop.auth.oauth import get_access_token

        headers = {"Authorization": f"Bearer {get_access_token('x')}"}
        text = meta.caption or video_path.stem
        with httpx.Client(timeout=300) as client:
            init = _request_with_retry(
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
                    append = _request_with_retry(
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

            finalize = _request_with_retry(
                client, "POST", f"{self.API}/media/upload/{media_id}/finalize", headers=headers
            )
            raise_api_error(self.name, finalize)
            processing = finalize.json().get("data", {}).get("processing_info")
            if processing:
                self._wait_processing(client, media_id, processing, headers)

            tweet = _request_with_retry(
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

    def _wait_processing(self, client: httpx.Client, media_id: str, info: dict, headers: dict) -> None:
        import time

        while info.get("state") in ("pending", "in_progress"):
            time.sleep(info.get("check_after_secs", 5))
            resp = _request_with_retry(
                client, "GET", f"{self.API}/media/upload/{media_id}", params={}, headers=headers
            )
            raise_api_error(self.name, resp)
            info = resp.json().get("data", {}).get("processing_info", {})
        if info.get("state") == "failed":
            raise PublishError(f"x media processing failed: {info}")


class LinkedInAdapter(PlatformAdapter):
    name = "linkedin"
    API = "https://api.linkedin.com"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        from socialdrop.auth.oauth import get_access_token

        headers = {
            "Authorization": f"Bearer {get_access_token('linkedin')}",
            "LinkedIn-Version": "202401",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        with httpx.Client(timeout=300) as client:
            me = _request_with_retry(client, "GET", f"{self.API}/v2/userinfo", headers=headers)
            raise_api_error(self.name, me)
            owner_urn = f"urn:li:person:{me.json()['sub']}"

            init = _request_with_retry(
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
                put = httpx.put(
                    instruction["uploadUrl"],
                    content=part,
                    headers={"Content-Type": "application/octet-stream"},
                )
                if put.status_code >= 400:
                    raise PublishError(f"linkedin part upload failed: {put.status_code}", retryable=True)
                etag = put.headers.get("etag")
                if etag:
                    etags.append({"etag": etag})

            finalize = _request_with_retry(
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

            post = _request_with_retry(
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


class BlueskyAdapter(PlatformAdapter):
    name = "bluesky"
    SERVICE = "https://bsky.social"

    def publish(self, video_path: Path, meta: PlatformConfig) -> PublishResult:
        import os

        try:
            from atproto import Client
        except ImportError as exc:
            raise PublishError(
                f"missing dependency; install with: pip install socialdrop[bluesky] ({exc})"
            ) from exc
        from socialdrop.auth import store

        token = store.load_token(self.name)
        caption_parts = [meta.caption or video_path.stem]
        tags = meta.hashtags or []
        if tags:
            caption_parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags))
        text = "\n\n".join(caption_parts)

        client = Client()
        if token and token.get("session"):
            client.login(session_string=token["session"])
            handle_name = token.get("identifier", "did")
        elif token and token.get("identifier") and token.get("password"):
            client.login(token["identifier"], token["password"])
            handle_name = token["identifier"]
        else:
            handle = os.environ.get("SOCIALDROP_BLUESKY_HANDLE")
            password = os.environ.get("SOCIALDROP_BLUESKY_APP_PASSWORD")
            if not handle or not password:
                raise PublishError(
                    "bluesky not configured; run 'socialdrop auth login bluesky' "
                    "(uses an app password, never your main password)"
                )
            client.login(handle, password)
            store.save_token(self.name, {"identifier": handle, "session": client.export_session_string()})
            handle_name = handle

        with open(video_path, "rb") as fh:
            video_data = fh.read()
        post = client.send_video(text=text, video=video_data, video_alt="")
        uri = post.uri if hasattr(post, "uri") else str(post)
        rkey = uri.rsplit("/", 1)[-1]
        return PublishResult(
            platform=self.name,
            url=f"https://bsky.app/profile/{handle_name}/post/{rkey}",
            post_id=rkey,
            raw={"uri": uri},
        )

    def is_ready(self) -> tuple[bool, str]:
        import os

        from socialdrop.auth.store import load_token

        if load_token(self.name) is not None:
            return True, "authenticated"
        if os.environ.get("SOCIALDROP_BLUESKY_HANDLE") and os.environ.get("SOCIALDROP_BLUESKY_APP_PASSWORD"):
            return True, "app password via environment"
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
