from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import InstagramAdapter
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return InstagramAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    cfg = PlatformConfig(caption="Instagram test")
    cfg.extra["ig_user_id"] = "12345"
    return cfg


@respx.mock
@pytest.mark.asyncio
async def test_instagram_publish_happy_path(adapter, video_path, meta):
    token = {"access_token": "ig.token"}
    respx.post("https://graph.facebook.com/v21.0/12345/media").mock(
        return_value=httpx.Response(200, json={"id": "container123"})
    )
    respx.post("https://rupload.facebook.com/ig-api-upload/container123").mock(
        return_value=httpx.Response(200)
    )
    respx.get("https://graph.facebook.com/v21.0/container123").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED", "permalink": "https://instagram.com/reel/123"})
    )
    respx.post("https://graph.facebook.com/v21.0/12345/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "media123"})
    )
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "media123"
    assert result.url == "https://instagram.com/reel/123"


@respx.mock
@pytest.mark.asyncio
async def test_instagram_publish_auth_fail(adapter, video_path, meta):
    token = {"access_token": "ig.token"}
    respx.post("https://graph.facebook.com/v21.0/12345/media").mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid token"}})
    )
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_instagram_publish_timeout(adapter, video_path, meta):
    token = {"access_token": "ig.token"}
    respx.post("https://graph.facebook.com/v21.0/12345/media").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)
