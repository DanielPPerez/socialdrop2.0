from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from socialdrop.publisher import publish_folder

console = Console()

DEBOUNCE_SECONDS = 2.0
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".md"}


def watch_folder(folder: Path, only: list[str] | None = None) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:
        raise SystemExit(f"install watch support first: pip install socialdrop[watch] ({exc})") from exc

    class DropHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            suffix = Path(str(event.src_path)).suffix.lower()
            if suffix in VIDEO_EXTENSIONS or suffix == ".md":
                self._debounced(event.src_path)

        def on_moved(self, event):
            if event.is_directory:
                return
            suffix = Path(str(event.dest_path)).suffix.lower()
            if suffix in VIDEO_EXTENSIONS or suffix == ".md":
                self._debounced(event.dest_path)

        def _debounced(self, src_path):
            console.print(f"[cyan]📥 detected {Path(src_path).name}[/cyan]")
            time.sleep(DEBOUNCE_SECONDS)
            run_cycle(folder, only)

    def run_cycle(target: Path, only: list[str] | None):
        try:
            results = publish_folder(target, only=only, respect_schedule=True)
            console.print(
                f"[bold]published={results['published']} failed={results['failed']} waiting={results['skipped']}[/bold]"
            )
        except Exception as exc:
            console.print(f"[red]error: {exc}[/red]")

    observer = Observer()
    observer.schedule(DropHandler(), str(folder), recursive=False)
    observer.start()
    console.print(f"[cyan]👀 watching {folder} — drop video + md to publish (Ctrl-C to stop)[/cyan]")
    run_cycle(folder, only)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        console.print("[yellow]watch stopped[/yellow]")
