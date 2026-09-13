from pathlib import Path

import pytest

from socialdrop.ai import suggest_from_video


@pytest.fixture
def fake_video(tmp_path: Path) -> Path:
    v = tmp_path / "video.mp4"
    v.write_bytes(b"x" * 32)
    return v


@pytest.mark.asyncio
async def test_suggest_from_video(fake_video: Path):
    import sys
    from unittest.mock import MagicMock

    mock_whisper = MagicMock()
    mock_model = mock_whisper.load_model.return_value
    mock_model.transcribe.return_value = {"text": "Hello world. This is a test."}
    sys.modules["whisper"] = mock_whisper
    try:
        result = await suggest_from_video(fake_video)
    finally:
        del sys.modules["whisper"]

    assert result["title"] == "Hello world"
    assert result["description"] == "Hello world. This is a test."
    assert "world" in result["hashtags"]
    assert "youtube" in result["per_platform_captions"]
    assert "tiktok" in result["per_platform_captions"]
