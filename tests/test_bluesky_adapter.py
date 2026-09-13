from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import BlueskyAdapter
from socialdrop.platforms.base import PublishError
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return BlueskyAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    return PlatformConfig(caption="Hello Bluesky")


@respx.mock
@pytest.mark.asyncio
async def test_bluesky_publish_happy_path(adapter, video_path, meta):
    token = {
        "accessJwt": "jwt.token",
        "did": "did:plc:abc123",
        "identifier": "alice.bsky.social",
    }
    respx.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob").mock(
        return_value=httpx.Response(
            200, json={"blob": {"ref": {"$link": "bafyreibc"}, "mimeType": "video/mp4", "size": 32}}
        )
    )
    respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
        return_value=httpx.Response(
            200, json={"uri": "at://did:plc:abc123/app.bsky.feed.post/rkey123"}
        )
    )
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "rkey123"
    assert result.url == "https://bsky.app/profile/alice.bsky.social/post/rkey123"


@respx.mock
@pytest.mark.asyncio
async def test_bluesky_publish_auth_fail(adapter, video_path, meta):
    token = {
        "accessJwt": "jwt.token",
        "did": "did:plc:abc123",
        "identifier": "alice.bsky.social",
    }
    respx.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob").mock(
        return_value=httpx.Response(401, json={"error": "InvalidToken"})
    )
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_bluesky_publish_upload_fail(adapter, video_path, meta):
    token = {
        "accessJwt": "jwt.token",
        "did": "did:plc:abc123",
        "identifier": "alice.bsky.social",
    }
    respx.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob").mock(
        return_value=httpx.Response(400, json={"error": "BadRequest"})
    )
    with pytest.raises(PublishError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_bluesky_publish_timeout(adapter, video_path, meta):
    token = {
        "accessJwt": "jwt.token",
        "did": "did:plc:abc123",
        "identifier": "alice.bsky.social",
    }
    respx.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)
