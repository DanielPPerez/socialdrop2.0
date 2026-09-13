from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import TikTokAdapter
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return TikTokAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    return PlatformConfig(caption="TikTok test")


@respx.mock
@pytest.mark.asyncio
async def test_tiktok_publish_happy_path(adapter, video_path, meta):
    respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
        return_value=httpx.Response(
            200,
            json={
                "error": {"code": "ok"},
                "data": {"publish_id": "pub123", "upload_url": "https://upload.tiktok.com/abc"},
            },
        )
    )
    respx.put("https://upload.tiktok.com/abc").mock(return_value=httpx.Response(200))
    token = {"access_token": "tiktok.token"}
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "pub123"
    assert result.url == "https://www.tiktok.com/upload/pub123"


@respx.mock
@pytest.mark.asyncio
async def test_tiktok_publish_401(adapter, video_path, meta):
    respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
        return_value=httpx.Response(401, json={"error": {"code": "invalid_token"}})
    )
    token = {"access_token": "tiktok.expired"}
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_tiktok_publish_timeout(adapter, video_path, meta):
    respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    token = {"access_token": "tiktok.ok"}
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)
