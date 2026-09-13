from pathlib import Path

import httpx
import pytest
import respx

from socialdrop.platforms.adapters import LinkedInAdapter
from socialdrop.platforms.exceptions import PlatformAuthError, PlatformTimeoutError
from socialdrop.schema import PlatformConfig


@pytest.fixture
def adapter():
    return LinkedInAdapter()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.fixture
def meta() -> PlatformConfig:
    return PlatformConfig(caption="LinkedIn test")


@respx.mock
@pytest.mark.asyncio
async def test_linkedin_publish_happy_path(adapter, video_path, meta):
    token = {"access_token": "li.token"}
    respx.get("https://api.linkedin.com/v2/userinfo").mock(
        return_value=httpx.Response(200, json={"sub": "person123"})
    )
    respx.post("https://api.linkedin.com/rest/videos?action=initializeUpload").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": {
                    "uploadToken": "token123",
                    "video": "urn:li:video:123",
                    "uploadInstructions": [
                        {
                            "uploadUrl": "https://upload.linkedin.com/part",
                            "byteRange": {"firstByte": 0, "lastByte": 31},
                        }
                    ],
                }
            },
        )
    )
    respx.put("https://upload.linkedin.com/part").mock(
        return_value=httpx.Response(200, headers={"etag": "abc"})
    )
    respx.post("https://api.linkedin.com/rest/videos?action=finalizeUpload").mock(
        return_value=httpx.Response(200)
    )
    respx.post("https://api.linkedin.com/v2/ugcPosts").mock(
        return_value=httpx.Response(202, headers={"x-restli-id": "urn:li:ugcPost:456"})
    )
    result = await adapter.publish(video_path, meta, token=token)
    assert result.post_id == "urn:li:ugcPost:456"
    assert result.url == "https://www.linkedin.com/feed/update/urn:li:ugcPost:456"


@respx.mock
@pytest.mark.asyncio
async def test_linkedin_publish_auth_fail(adapter, video_path, meta):
    token = {"access_token": "li.expired"}
    respx.get("https://api.linkedin.com/v2/userinfo").mock(
        return_value=httpx.Response(401, json={"serviceErrorCode": 401})
    )
    with pytest.raises(PlatformAuthError):
        await adapter.publish(video_path, meta, token=token)


@respx.mock
@pytest.mark.asyncio
async def test_linkedin_publish_timeout(adapter, video_path, meta):
    token = {"access_token": "li.ok"}
    respx.get("https://api.linkedin.com/v2/userinfo").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    with pytest.raises(PlatformTimeoutError):
        await adapter.publish(video_path, meta, token=token)
