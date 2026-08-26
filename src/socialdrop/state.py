from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

STATUS_DISCOVERED = "discovered"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHING = "publishing"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"


class PlatformAttempt(BaseModel):
    platform: str
    status: str = STATUS_DISCOVERED
    attempts: int = 0
    url: str | None = None
    post_id: str | None = None
    error: str | None = None
    published_at: str | None = None


class DropState(BaseModel):
    video: str
    md: str
    status: str = STATUS_DISCOVERED
    platforms: dict[str, PlatformAttempt] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: _now_iso())

    def attempt(self, platform: str) -> PlatformAttempt:
        if platform not in self.platforms:
            self.platforms[platform] = PlatformAttempt(platform=platform)
        return self.platforms[platform]

    @property
    def all_published(self) -> bool:
        return all(a.status == STATUS_PUBLISHED for a in self.platforms.values()) and bool(
            self.platforms
        )

    def refresh_status(self) -> None:
        if self.all_published:
            self.status = STATUS_PUBLISHED
        elif any(a.status == STATUS_FAILED for a in self.platforms.values()):
            self.status = STATUS_FAILED
        elif any(a.status == STATUS_PUBLISHING for a in self.platforms.values()):
            self.status = STATUS_PUBLISHING


def state_dir(folder: Path) -> Path:
    d = folder / ".socialdrop"
    d.mkdir(exist_ok=True)
    return d


def state_path(md_path: Path) -> Path:
    return state_dir(md_path.parent) / f"{md_path.stem}.state.json"


def load_state(md_path: Path) -> DropState | None:
    p = state_path(md_path)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return DropState.model_validate(data)


def save_state(md_path: Path, state: DropState) -> Path:
    state.updated_at = _now_iso()
    state.refresh_status()
    p = state_path(md_path)
    p.write_text(state.model_dump_json(indent=2))
    os.chmod(p, 0o600)
    return p


def new_state(md_path: Path, platforms: list[str]) -> DropState:
    return DropState(
        video=video_name_for(md_path),
        md=md_path.name,
        platforms={name: PlatformAttempt(platform=name) for name in platforms},
    )


def is_due(md_path: Path, now: datetime | None = None) -> bool:
    from socialdrop.schema import load_drop

    drop = load_drop(md_path)
    if not drop.meta.schedule:
        return True
    from socialdrop.schema import parse_schedule

    scheduled = parse_schedule(drop.meta.schedule)
    now = now or datetime.now(timezone.utc)
    return scheduled <= now


def video_name_for(md_path: Path) -> str:
    from socialdrop.schema import video_for

    return video_for(md_path).name


def reset_platform(md_path: Path, platform: str) -> None:
    state = load_state(md_path)
    if state is None:
        return
    attempt = state.attempt(platform)
    attempt.status = STATUS_DISCOVERED
    attempt.error = None
    save_state(md_path, state)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_dict(state: DropState) -> dict[str, Any]:
    return state.model_dump()
