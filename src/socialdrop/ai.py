from __future__ import annotations

import os
from pathlib import Path
from typing import Any


async def suggest_from_video(video_path: Path) -> dict[str, Any]:
    model = os.environ.get("SOCIALDROP_WHISPER_MODEL", "base")
    try:
        import whisper

        model_obj = whisper.load_model(model)
        result = model_obj.transcribe(str(video_path))
        transcript = result.get("text", "").strip()
    except Exception:
        transcript = ""

    title = "Untitled"
    description = ""
    hashtags: list[str] = []
    per_platform: dict[str, str] = {}

    if transcript:
        sentences = transcript.split(". ")
        title = sentences[0][:100] if sentences else transcript[:100]
        description = transcript[:500]
        words = transcript.split()
        hashtags = list({w.lower().strip(".,!?") for w in words if len(w) > 4})[:10]
        per_platform = {
            "youtube": f"{title}\n\n{description}",
            "tiktok": title[:2200],
            "instagram": f"{title}\n\n{' '.join(f'#{h}' for h in hashtags[:5])}",
            "x": title[:280],
            "linkedin": title,
            "bluesky": f"{title}\n\n{' '.join(f'#{h}' for h in hashtags[:5])}",
        }

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "transcript": transcript,
        "per_platform_captions": per_platform,
    }
