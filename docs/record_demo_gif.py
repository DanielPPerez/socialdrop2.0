"""
Record a short GIF of the socialdrop dashboard for the README hero.

Requirements:
- ffmpeg installed and in PATH
- Either:
  - Windows: use the built-in ScreenRecorder (PowerShell 5.1+)
  - Or run the app manually and record with OBS/ShareX

Usage:
    python docs/record_demo_gif.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUTPUT = Path("docs/assets/dashboard-demo.gif")
DURATION = 15


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def record_windows() -> Path:
    raw = Path("docs/assets/demo_raw.mp4")
    ps = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
    $bmp.Save("docs/assets/demo_frame.png")
    $g.Dispose()
    $bmp.Dispose()
    """
    Path("docs/assets").mkdir(exist_ok=True)
    frames = []
    for i in range(DURATION * 2):
        subprocess.run(["powershell", "-Command", ps], check=True)
        frame = Path(f"docs/assets/frame_{i:04d}.png")
        frame.write_bytes(Path("docs/assets/demo_frame.png").read_bytes())
        frames.append(frame)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "2",
            "-i",
            "docs/assets/frame_%04d.png",
            "-vf",
            "scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse",
            str(raw),
        ],
        check=True,
    )
    for f in frames:
        f.unlink()
    Path("docs/assets/demo_frame.png").unlink(missing_ok=True)
    return raw


def convert_to_gif(src: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            "scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse",
            str(OUTPUT),
        ],
        check=True,
    )
    return OUTPUT


def main() -> None:
    if not check_ffmpeg():
        print("ffmpeg not found. Install ffmpeg and retry.", file=sys.stderr)
        sys.exit(1)
    raw = record_windows()
    gif = convert_to_gif(raw)
    raw.unlink(missing_ok=True)
    print(f"GIF saved to {gif}")


if __name__ == "__main__":
    main()
