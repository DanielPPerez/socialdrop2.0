from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

console = Console()

SAMPLE_MD = """---
title: My first socialdrop video
schedule: ""
platforms:
  mock: {}
---

This description is published wherever the platform config does not override it.

Add real platforms like `youtube`, `tiktok`, `instagram`, `x`, `linkedin`,
`bluesky` once you have authenticated them.
"""


async def run_demo(out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)
    md_path = out_dir / "my-first-video.md"
    video_path = out_dir / "my-first-video.mp4"

    if not video_path.exists():
        _write_placeholder_video(video_path)

    if not md_path.exists():
        md_path.write_text(SAMPLE_MD)

    console.print(f"[cyan]Created demo folder:[/cyan] {out_dir.resolve()}")

    from socialdrop.publisher import publish_drop, sync_folder_stats

    outcome = await publish_drop(md_path, force=True)
    await sync_folder_stats(out_dir)
    state = outcome["state"]
    console.print()
    console.print(f"[bold green]Demo complete — status: {state.status}[/bold green]")
    console.print(f"Open {md_path} to see the Published + Insights tables written back.")
    console.print("\nNext steps:")
    console.print("  1. socialdrop auth login <platform>   # connect real accounts")
    console.print("  2. edit the md file: replace 'mock' with your platforms")
    console.print("  3. socialdrop watch demo              # live folder watching")


def _write_placeholder_video(video_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        import subprocess

        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=2:size=1280x720:rate=30",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-shortest",
                str(video_path),
            ],
            check=True,
            capture_output=True,
        )
        return
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 256)
