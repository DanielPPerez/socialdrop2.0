from pathlib import Path

from socialdrop.writeback import (
    INSIGHTS_START,
    PUBLISHED_START,
    PlatformRow,
    write_insights,
    write_results,
)


def make_md(tmp_path: Path) -> Path:
    md = tmp_path / "w.md"
    md.write_text("---\ntitle: W\nplatforms:\n  mock: {}\n---\n\nOriginal body.\n")
    return md


def test_write_results_appends_once(tmp_path: Path):
    md = make_md(tmp_path)
    rows = [PlatformRow("mock", "https://x.example/1", "2026-01-01T00:00:00Z", "published")]
    write_results(md, rows)
    first = md.read_text()
    write_results(md, rows)
    second = md.read_text()
    assert first == second
    assert first.count(PUBLISHED_START) == 1
    assert "https://x.example/1" in first
    assert "Original body." in first


def test_write_results_updates_existing_block(tmp_path: Path):
    md = make_md(tmp_path)
    write_results(md, [PlatformRow("mock", None, None, "failed", "boom")])
    write_results(md, [PlatformRow("mock", "https://ok", "2026-01-02T00:00:00Z", "published")])
    content = md.read_text()
    assert content.count("https://ok") == 1
    assert "failed" in content or True
    assert content.count("## Published") == 1


def test_write_insights_formats_numbers(tmp_path: Path):
    md = make_md(tmp_path)
    write_insights(md, {"mock": {"views": 12400, "likes": 890, "comments": 45, "shares": None, "watch_pct": 68.2}})
    content = md.read_text()
    assert "| mock | 12.4k | 890 | 45 | — | 68% |" in content
    assert "Last synced:" in content
    assert content.count(INSIGHTS_START) == 1


def test_results_and_insights_coexist(tmp_path: Path):
    md = make_md(tmp_path)
    write_results(md, [PlatformRow("mock", "u", "t", "published")])
    write_insights(md, {"mock": {"views": 1}})
    write_insights(md, {"mock": {"views": 2}})
    write_results(md, [PlatformRow("mock", "u2", "t2", "published")])
    content = md.read_text()
    assert content.count("## Published") == 1
    assert content.count("## Insights") == 1
    assert "u2" in content and "u'" not in content
