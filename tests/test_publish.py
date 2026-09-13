from pathlib import Path

import pytest

from socialdrop.demo import run_demo
from socialdrop.publisher import publish_drop, sync_folder_stats


def make_drop(tmp_path: Path) -> Path:
    (tmp_path / "clip.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "clip.md"
    md.write_text("---\ntitle: Clip\nschedule: \"\"\nplatforms:\n  mock: {}\n---\nBody.\n")
    return md


@pytest.mark.asyncio
async def test_publish_drop_end_to_end(tmp_path: Path):
    md = make_drop(tmp_path)
    result = await publish_drop(md, force=True)
    state = result["state"]
    assert state.status == "published"
    attempt = state.platforms["mock"]
    assert attempt.status == "published"
    assert attempt.url is not None
    content = md.read_text(encoding="utf-8")
    assert "## Published" in content and "## Insights" not in content


@pytest.mark.asyncio
async def test_publish_idempotent_no_double_post(tmp_path: Path):
    md = make_drop(tmp_path)
    await publish_drop(md, force=True)
    first = md.read_text(encoding="utf-8")
    await publish_drop(md, force=False)
    assert md.read_text(encoding="utf-8") == first


@pytest.mark.asyncio
async def test_stats_writeback(tmp_path: Path):
    md = make_drop(tmp_path)
    await publish_drop(md, force=True)
    await sync_folder_stats(tmp_path)
    content = md.read_text(encoding="utf-8")
    assert "## Insights" in content
    views_line = [line for line in content.splitlines() if line.startswith("| mock |")]
    assert views_line, "insights table row missing"


def test_cli_doctor_ok(tmp_path: Path):
    from socialdrop.cli import doctor

    make_drop(tmp_path)
    doctor(tmp_path)


def test_cli_doctor_invalid_platform(tmp_path: Path):
    import typer

    from socialdrop.cli import doctor

    (tmp_path / "bad.mp4").write_bytes(b"x")
    (tmp_path / "bad.md").write_text("---\ntitle: B\nplatforms:\n  nosuch: {}\n---\n")
    with pytest.raises(typer.Exit):
        doctor(tmp_path)


@pytest.mark.asyncio
async def test_cli_demo(tmp_path: Path):
    monkey_dir = tmp_path / "demo"
    await run_demo(monkey_dir)
    assert (monkey_dir / "my-first-video.md").exists()
