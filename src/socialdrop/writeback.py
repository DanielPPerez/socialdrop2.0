from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

PUBLISHED_START = "<!-- socialdrop:published:start -->"
PUBLISHED_END = "<!-- socialdrop:published:end -->"
INSIGHTS_START = "<!-- socialdrop:insights:start -->"
INSIGHTS_END = "<!-- socialdrop:insights:end -->"


@dataclass
class PlatformRow:
    platform: str
    url: str | None = None
    posted_at: str | None = None
    status: str = "pending"
    error: str | None = None


def _render_published(rows: list[PlatformRow]) -> str:
    lines = [
        PUBLISHED_START,
        "## Published",
        "",
        "| Platform | URL | Posted at | Status |",
        "|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda r: r.platform):
        status_icon = {"published": "✅", "failed": "❌", "publishing": "⏳"}.get(row.status, "·")
        label = f"{status_icon} {row.platform}"
        if row.status == "failed" and row.error:
            short_error = row.error[:80]
            label = f"{status_icon} {row.platform} — {short_error}"
        lines.append(
            f"| {label} | {row.url or '—'} | {row.posted_at or '—'} | {row.status} |"
        )
    lines.append(PUBLISHED_END)
    return "\n".join(lines)


def _render_insights(metrics_rows: dict[str, dict], synced_at: str) -> str:
    lines = [
        INSIGHTS_START,
        "## Insights",
        "",
        "| Platform | Views | Likes | Comments | Shares | Watch % |",
        "|---|---|---|---|---|---|",
    ]

    def fmt(value):
        if value is None:
            return "—"
        if isinstance(value, int) and value >= 1000:
            return f"{value / 1000:.1f}k"
        return value

    for platform in sorted(metrics_rows):
        m = metrics_rows[platform]
        watch = m.get("watch_pct")
        watch_str = f"{watch:.0f}%" if isinstance(watch, (int, float)) else "—"
        lines.append(
            f"| {platform} | {fmt(m.get('views'))} | {fmt(m.get('likes'))} "
            f"| {fmt(m.get('comments'))} | {fmt(m.get('shares'))} | {watch_str} |"
        )
    lines.append("")
    lines.append(f"_Last synced: {synced_at}_")
    lines.append(INSIGHTS_END)
    return "\n".join(lines)


def _replace_block(content: str, start_marker: str, end_marker: str, new_block: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    if pattern.search(content):
        return pattern.sub(new_block.replace("\\", "\\\\"), content)
    separator = "" if content.endswith("\n\n") else ("\n" if content.endswith("\n") else "\n\n")
    return content + separator + new_block + "\n"


def write_results(md_path: Path, rows: list[PlatformRow]) -> None:
    if md_path.suffix.lower() == ".json":
        _write_json_block(md_path, "published", _json_published(rows))
        return
    post = frontmatter.load(str(md_path))
    block = _render_published(rows)
    post.content = _replace_block(post.content, PUBLISHED_START, PUBLISHED_END, block)
    frontmatter.dump(post, str(md_path))


def write_insights(md_path: Path, metrics_rows: dict[str, dict]) -> None:
    if md_path.suffix.lower() == ".json":
        synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_json_block(md_path, "insights", {"metrics": metrics_rows, "synced_at": synced_at})
        return
    post = frontmatter.load(str(md_path))
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = _render_insights(metrics_rows, synced_at)
    post.content = _replace_block(post.content, INSIGHTS_START, INSIGHTS_END, block)
    frontmatter.dump(post, str(md_path))


def _write_json_block(json_path: Path, key: str, value: dict) -> None:
    import json

    data = json.loads(json_path.read_text())
    data[key] = value
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _json_published(rows: list[PlatformRow]) -> dict:
    return {
        row.platform: {
            "status": row.status,
            "url": row.url,
            "posted_at": row.posted_at,
            "error": row.error,
        }
        for row in rows
    }
