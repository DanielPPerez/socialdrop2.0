from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import YouTubeAdapter
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return YouTubeAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    return PlatformConfig(caption="Test caption")


@respx.mock
@pytest.mark.asyncio
async def test_youtube_publish_happy_path(adapter, video_path, meta):
    respx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"part": "snippet,status", "uploadType": "resumable"},
    ).mock(return_value=httpx.Response(200, headers={"Location": "https://upload.youtube.com/abc"}))
    respx.put("https://upload.youtube.com/abc").mock(
        return_value=httpx.Response(200, json={"id": "vid123"})
    )
    token = {"access_token": "ya29.abc"}
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "vid123"
    assert result.url == "https://youtu.be/vid123"


@respx.mock
@pytest.mark.asyncio
async def test_youtube_publish_401(adapter, video_path, meta):
    respx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"part": "snippet,status", "uploadType": "resumable"},
    ).mock(return_value=httpx.Response(401, json={"error": "invalid_token"}))
    token = {"access_token": "ya29.expired"}
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_youtube_publish_403_forbidden(adapter, video_path, meta):
    respx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"part": "snippet,status", "uploadType": "resumable"},
    ).mock(return_value=httpx.Response(403, json={"error": "quota_exceeded"}))
    token = {"access_token": "ya29.ok"}
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_youtube_publish_timeout(adapter, video_path, meta):
    respx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"part": "snippet,status", "uploadType": "resumable"},
    ).mock(side_effect=httpx.TimeoutException("timeout"))
    token = {"access_token": "ya29.ok"}
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_youtube_get_stats_happy_path(adapter):
    respx.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "statistics", "id": "vid123"},
    ).mock(
        return_value=httpx.Response(
            200, json={"items": [{"statistics": {"viewCount": "1000", "likeCount": "100"}}]}
        )
    )
    token = {"access_token": "ya29.ok"}
    metrics = await adapter.get_stats("vid123", PlatformConfig(), token=token)
    assert metrics.views == 1000
    assert metrics.likes == 100
