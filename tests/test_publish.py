from pathlib import Path

from typer.testing import CliRunner

from socialdrop.cli import app
from socialdrop.publisher import publish_drop

runner = CliRunner()


def make_drop(tmp_path: Path) -> Path:
    (tmp_path / "clip.mp4").write_bytes(b"x" * 32)
    md = tmp_path / "clip.md"
    md.write_text("---\ntitle: Clip\nschedule: \"\"\nplatforms:\n  mock: {}\n---\nBody.\n")
    return md


def test_publish_drop_end_to_end(tmp_path: Path):
    md = make_drop(tmp_path)
    result = publish_drop(md, force=True)
    state = result["state"]
    assert state.status == "published"
    attempt = state.platforms["mock"]
    assert attempt.status == "published"
    assert attempt.url is not None
    content = md.read_text()
    assert "## Published" in content and "## Insights" not in content


def test_publish_idempotent_no_double_post(tmp_path: Path):
    md = make_drop(tmp_path)
    publish_drop(md, force=True)
    first = md.read_text()
    publish_drop(md, force=False)
    assert md.read_text() == first


def test_stats_writeback(tmp_path: Path):
    md = make_drop(tmp_path)
    publish_drop(md, force=True)
    from socialdrop.publisher import sync_folder_stats

    sync_folder_stats(tmp_path)
    content = md.read_text()
    assert "## Insights" in content
    views_line = [line for line in content.splitlines() if line.startswith("| mock |")]
    assert views_line, "insights table row missing"


def test_cli_doctor_ok(tmp_path: Path):
    make_drop(tmp_path)
    res = runner.invoke(app, ["doctor", str(tmp_path)])
    assert res.exit_code == 0
    assert "drop file(s) valid" in res.output


def test_cli_doctor_invalid_platform(tmp_path: Path):
    (tmp_path / "bad.mp4").write_bytes(b"x")
    (tmp_path / "bad.md").write_text("---\ntitle: B\nplatforms:\n  nosuch: {}\n---\n")
    res = runner.invoke(app, ["doctor", str(tmp_path)])
    assert res.exit_code == 1
    assert "unknown platform 'nosuch'" in res.output


def test_cli_demo(tmp_path: Path):
    monkey_dir = tmp_path / "demo"
    res = runner.invoke(app, ["demo", str(monkey_dir)], env={"HOME": str(tmp_path)})
    assert res.exit_code == 0, res.output
    assert (monkey_dir / "my-first-video.md").exists()
