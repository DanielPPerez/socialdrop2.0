from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from socialdrop.api.main import app
from socialdrop.jobs import Job
from socialdrop.platforms.adapters import MockAdapter
from socialdrop.platforms.exceptions import PlatformAuthError


def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _headers() -> dict[str, str]:
    return {"x-api-key": "test-key"}


def _setup_api_key() -> None:
    os.environ["SOCIALDROP_API_KEY"] = "test-key"


def _clear_api_key() -> None:
    os.environ.pop("SOCIALDROP_API_KEY", None)


@pytest.fixture(autouse=True)
def _env():
    _setup_api_key()
    yield
    _clear_api_key()


@pytest.mark.asyncio
async def test_list_platforms():
    adapter = MockAdapter()
    with patch("socialdrop.api.main.all_adapters", return_value=[adapter]):
        async with _client() as client:
            resp = await client.get("/api/v1/platforms", headers=_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1
            assert data[0]["platform"] == "mock"
            assert data[0]["configured"] is False
            assert data[0]["authenticated"] is True


@pytest.mark.asyncio
async def test_start_auth():
    from socialdrop.auth.oauth import OAuthConfig

    cfg = OAuthConfig(
        platform="youtube",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    os.environ["SOCIALDROP_YOUTUBE_CLIENT_ID"] = "dummy"
    with patch.dict("socialdrop.api.main.OAUTH_CONFIGS", {"youtube": cfg}, clear=True):
        async with _client() as client:
            resp = await client.post("/api/v1/platforms/youtube/auth/start", headers=_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert "authorize_url" in data
            assert "state" in data
    os.environ.pop("SOCIALDROP_YOUTUBE_CLIENT_ID", None)


@pytest.mark.asyncio
async def test_auth_callback():
    os.environ["SOCIALDROP_API_KEY"] = "test-key"
    state = "abc123"
    from socialdrop.api.main import AUTH_SESSIONS

    AUTH_SESSIONS[state] = {"platform": "youtube", "verifier": "verifier"}
    mock_token = {"access_token": "ya29.abc", "expires_at": 9999999999}
    with patch("socialdrop.api.main.oauth.run_authorization_code_flow", return_value=mock_token) as mock_flow:
        with patch("socialdrop.api.main.store.save_token"):
            async with _client() as client:
                resp = await client.get(
                    "/api/v1/platforms/youtube/auth/callback",
                    params={"code": "code123", "state": state},
                    headers=_headers(),
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"
                mock_flow.assert_called_once()
    AUTH_SESSIONS.pop(state, None)


@pytest.mark.asyncio
async def test_list_drops(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    (tmp_path / "drop1.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "drop1.md"
    md.write_text("---\ntitle: T\nplatforms:\n  mock: {}\n---\nbody", encoding="utf-8")
    async with _client() as client:
        resp = await client.get("/api/v1/drops", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "drop1"
        assert data[0]["video_filename"] == "drop1.mp4"


@pytest.mark.asyncio
async def test_create_drop(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    drop_json = json.dumps({"title": "T", "platforms": {"mock": {}}, "body": "hello"})
    files = {"video": ("test.mp4", b"x" * 32, "video/mp4")}
    data = {"drop_create": drop_json}
    async with _client() as client:
        resp = await client.post("/api/v1/drops", files=files, data=data, headers=_headers())
        assert resp.status_code == 200
        out = resp.json()
        assert out["title"] == "T"
        assert out["status"] == "draft"
        assert out["video_filename"] == "test.mp4"


@pytest.mark.asyncio
async def test_get_drop(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    (tmp_path / "abc.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "abc.md"
    md.write_text("---\ntitle: T\nplatforms:\n  mock: {}\n---\nbody", encoding="utf-8")
    async with _client() as client:
        resp = await client.get("/api/v1/drops/abc", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "abc"
        assert data["video_filename"] == "abc.mp4"


@pytest.mark.asyncio
async def test_publish_drop_api(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    (tmp_path / "abc.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "abc.md"
    md.write_text("---\ntitle: T\nplatforms:\n  mock: {}\n---\nbody", encoding="utf-8")
    with patch("socialdrop.api.main.JOB_QUEUE") as mock_queue:
        mock_queue.enqueue.return_value = Job(drop_id="abc", platform="mock")
        async with _client() as client:
            resp = await client.post("/api/v1/drops/abc/publish", headers=_headers())
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "publishing"
            assert mock_queue.enqueue.called


@pytest.mark.asyncio
async def test_publish_drop_auth_error(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    (tmp_path / "abc.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "abc.md"
    md.write_text("---\ntitle: T\nplatforms:\n  mock: {}\n---\nbody", encoding="utf-8")
    with patch("socialdrop.api.main.JOB_QUEUE") as mock_queue:
        mock_queue.enqueue.side_effect = PlatformAuthError("bad token")
        async with _client() as client:
            resp = await client.post("/api/v1/drops/abc/publish", headers=_headers())
            assert resp.status_code == 401
            assert resp.json()["error"] == "bad token"


@pytest.mark.asyncio
async def test_delete_drop(tmp_path):
    os.environ["SOCIALDROP_API_DROPS_FOLDER"] = str(tmp_path)
    (tmp_path / "abc.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "abc.md"
    md.write_text("---\ntitle: T\nplatforms:\n  mock: {}\n---\nbody", encoding="utf-8")
    async with _client() as client:
        resp = await client.delete("/api/v1/drops/abc", headers=_headers())
        assert resp.status_code == 204
        assert not md.exists()


@pytest.mark.asyncio
async def test_auth_required():
    async with _client() as client:
        resp = await client.get("/api/v1/drops")
        assert resp.status_code == 401
