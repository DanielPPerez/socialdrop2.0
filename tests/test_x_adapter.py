from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import XAdapter
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return XAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    return PlatformConfig(caption="X test")


@respx.mock
@pytest.mark.asyncio
async def test_x_publish_happy_path(adapter, video_path, meta):
    token = {"access_token": "x.token"}
    respx.post("https://api.x.com/2/media/upload/initialize").mock(
        return_value=httpx.Response(200, json={"data": {"id": "media123"}})
    )
    respx.post("https://api.x.com/2/media/upload/media123/append").mock(
        return_value=httpx.Response(204)
    )
    respx.post("https://api.x.com/2/media/upload/media123/finalize").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )
    respx.post("https://api.x.com/2/tweets").mock(
        return_value=httpx.Response(200, json={"data": {"id": "tweet123", "username": "user"}})
    )
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "tweet123"
    assert result.url == "https://x.com/user/status/tweet123"


@respx.mock
@pytest.mark.asyncio
async def test_x_publish_401(adapter, video_path, meta):
    token = {"access_token": "x.expired"}
    respx.post("https://api.x.com/2/media/upload/initialize").mock(
        return_value=httpx.Response(401, json={"detail": "Invalid token"})
    )
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_x_publish_timeout(adapter, video_path, meta):
    token = {"access_token": "x.ok"}
    respx.post("https://api.x.com/2/media/upload/initialize").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)
