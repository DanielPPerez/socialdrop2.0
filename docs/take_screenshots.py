"""
Grab screenshots for the README.

Usage:
    python docs/take_screenshots.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUTPUT_DIR = Path("docs/assets")
URLS = {
    "connect": "http://localhost:3000/platforms",
    "create": "http://localhost:3000/drops/new",
    "published": "http://localhost:3000/drops",
}


def open_browser(url: str) -> None:
    subprocess.run(["start", "", url], shell=True, check=False)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    print("Open each URL and save the screenshot manually:")
    for name, url in URLS.items():
        print(f"  {name}: {url}")
    print(f"\nSave screenshots into {OUTPUT_DIR.resolve()}")
    print("Recommended size: 1280x800, dark theme.")


if __name__ == "__main__":
    main()
