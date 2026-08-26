from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from socialdrop.publisher import publish_folder

console = Console()


def run_loop(folder: Path, interval_seconds: int = 60, only: list[str] | None = None) -> None:
    console.print(f"[cyan]👀 watching {folder} (scan every {interval_seconds}s; Ctrl-C to stop)[/cyan]")
    try:
        while True:
            try:
                results = publish_folder(folder, only=only, respect_schedule=True)
                if results["published"] or results["failed"]:
                    console.print(
                        f"[bold]cycle:[/bold] published={results['published']} "
                        f"failed={results['failed']} waiting={results['skipped']}"
                    )
            except Exception as exc:
                console.print(f"[red]cycle error: {exc}[/red]")
            _sleep(interval_seconds)
    except KeyboardInterrupt:
        console.print("[yellow]watch stopped[/yellow]")


def _sleep(seconds: int) -> None:
    time.sleep(seconds)


def next_due(folder: Path) -> datetime | None:
    from socialdrop.schema import find_drops, load_drop, parse_schedule

    due_times = []
    for md_path in find_drops(folder):
        drop = load_drop(md_path)
        if not drop.meta.schedule:
            continue
        due_times.append(parse_schedule(drop.meta.schedule))
    return min(due_times) if due_times else None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
