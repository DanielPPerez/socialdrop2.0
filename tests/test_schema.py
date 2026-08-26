from pathlib import Path

import pytest

from socialdrop.schema import PlatformConfig, VideoMeta, load_drop, parse_schedule, video_for


def write_drop(folder: Path, stem: str = "test-video", platforms: str = "  mock: {}", schedule: str = '""') -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.mp4").write_bytes(b"\x00" * 64)
    md = folder / f"{stem}.md"
    md.write_text(
        f"---\ntitle: Test Video\nschedule: {schedule}\nplatforms:\n{platforms}\n---\n\nBody description here.\n"
    )
    return md


def test_parses_basic_frontmatter(tmp_path: Path):
    md = write_drop(tmp_path)
    drop = load_drop(md)
    assert isinstance(drop.meta, VideoMeta)
    assert drop.meta.title == "Test Video"
    assert drop.meta.platform_names == ["mock"]
    assert drop.meta.description == "Body description here."
    assert drop.video_path.name == "test-video.mp4"


def test_body_becomes_description_fallback(tmp_path: Path):
    md = write_drop(tmp_path)
    drop = load_drop(md)
    assert drop.meta.description == "Body description here."


def test_global_hashtags_propagate_to_platform_configs(tmp_path: Path):
    folder = tmp_path / "d"
    md = write_drop(
        folder,
        platforms="  mock:\n    caption: hi\n",
    )
    content = md.read_text().replace("platforms:", "hashtags: [a, b]\nplatforms:")
    md.write_text(content)
    drop = load_drop(md)
    assert drop.meta.platforms["mock"].hashtags == ["a", "b"]


def test_per_platform_caption_override(tmp_path: Path):
    md = write_drop(tmp_path, platforms='  mock:\n    caption: "Custom"\n')
    drop = load_drop(md)
    cfg: PlatformConfig = drop.meta.platforms["mock"]
    assert cfg.caption == "Custom"


def test_missing_video_file_raises(tmp_path: Path):
    folder = tmp_path / "d"
    folder.mkdir()
    md = folder / "lonely.md"
    md.write_text("---\ntitle: X\nplatforms:\n  mock: {}\n---\n")
    with pytest.raises(FileNotFoundError):
        load_drop(md)


def test_unknown_timezone_in_schedule_rejected(tmp_path: Path):
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        parse_schedule("2026-08-30 10:00 Not/AZone")


def test_parse_schedule_with_tz():
    dt = parse_schedule("2026-08-30 10:00 America/New_York")
    assert dt.utcoffset() is not None
    assert dt.hour == 10
    assert dt.tzinfo is not None


def test_video_for_prefers_exact_extension(tmp_path: Path):
    (tmp_path / "clip.mov").write_bytes(b"x")
    assert video_for(tmp_path / "clip.md").name == "clip.mov"
