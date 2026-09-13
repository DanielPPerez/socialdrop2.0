from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
from pydantic import BaseModel, Field, ValidationError


class PlatformConfig(BaseModel):
    account_id: str | None = None
    caption: str | None = None
    url: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    def get(self, key: str, default: Any = None) -> Any:
        value = getattr(self, key, None)
        if value is not None:
            return value
        return self.extra.get(key, default)


class VideoMeta(BaseModel):
    title: str
    schedule: str | None = None
    platforms: dict[str, PlatformConfig]
    hashtags: list[str] = Field(default_factory=list)
    description: str | None = None
    public: bool = False

    @property
    def platform_names(self) -> list[str]:
        return list(self.platforms.keys())


def parse_schedule(value: str) -> Any:
    from zoneinfo import ZoneInfo

    from dateutil.parser import parse as dt_parse

    tokens = value.replace(",", " ").split()
    tz = None
    remaining = []
    for token in tokens:
        try:
            tz = ZoneInfo(token)
        except Exception:
            remaining.append(token)
    if not remaining:
        raise ValueError(f"schedule '{value}' has no date")
    dt = dt_parse(" ".join(remaining))
    if tz is None:
        raise ValueError(
            f"schedule '{value}' has no timezone; add one like '10:00 America/New_York'"
        )
    return dt.replace(tzinfo=tz)


class VideoDrop(BaseModel):
    path: Path
    meta: VideoMeta

    @property
    def video_path(self) -> Path:
        return self.path

    @property
    def stem(self) -> str:
        return self.path.stem


def load_drop(md_path: Path) -> VideoDrop:
    if md_path.suffix.lower() == ".json":
        return _load_json_drop(md_path)
    video_path = video_for(md_path)
    if not video_path.exists():
        raise FileNotFoundError(f"no video file found next to {md_path.name}")
    post = frontmatter.load(str(md_path))
    data = dict(post.metadata)
    if "description" not in data and post.content.strip():
        data["description"] = post.content.strip()
    meta = VideoMeta.model_validate(data)
    for cfg in meta.platforms.values():
        if not cfg.hashtags and meta.hashtags:
            cfg.hashtags = list(meta.hashtags)
    if meta.schedule:
        parse_schedule(meta.schedule)
    return VideoDrop(path=video_path, meta=meta)


JSON_PLATFORM_KEYS = (
    "youtube",
    "instagram",
    "tiktok",
    "x",
    "linkedin",
    "bluesky",
    "facebook",
    "threads",
    "pinterest",
    "mock",
)


def _load_json_drop(json_path: Path) -> VideoDrop:
    import json

    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{json_path.name}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{json_path.name}: top level must be an object")

    file_name = data.get("file")
    if file_name:
        video_path = json_path.parent / str(file_name)
    else:
        video_path = video_for(json_path)

    platforms: dict[str, PlatformConfig] = {}
    for key, value in data.items():
        if isinstance(value, dict) and (key in JSON_PLATFORM_KEYS):
            platforms[key] = PlatformConfig.model_validate(value)

    title = data.get("title") or platforms.get("youtube", PlatformConfig()).get("title") or json_path.stem
    schedule = data.get("schedule")
    meta = VideoMeta(title=str(title), schedule=schedule, platforms=platforms)
    if meta.schedule:
        parse_schedule(meta.schedule)
    return VideoDrop(path=video_path, meta=meta)


VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}


def video_for(md_path: Path) -> Path:
    stem = md_path.stem
    parent = md_path.parent
    for ext in VIDEO_EXTENSIONS:
        candidate = parent / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    matches = [p for p in parent.iterdir() if p.stem == stem and p.suffix.lower() in VIDEO_EXTENSIONS]
    if matches:
        return matches[0]
    return parent / f"{stem}.mp4"


def find_drops(folder: Path) -> list[Path]:
    md = (p for p in folder.glob("*.md") if video_for(p).exists())
    json = (p for p in folder.glob("*.json") if _json_drop_video(p).exists())
    return sorted({*md, *json})


def _json_drop_video(json_path: Path) -> Path:
    import json

    try:
        data = json.loads(json_path.read_text())
        file_name = data.get("file")
    except Exception:
        file_name = None
    if file_name:
        return json_path.parent / str(file_name)
    return video_for(json_path)


def validate_drop_file(md_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        drop = load_drop(md_path)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"{md_path.name}: {loc}: {err['msg']}")
        return errors
    except FileNotFoundError as exc:
        return [str(exc)]
    except ValueError as exc:
        return [f"{md_path.name}: {exc}"]
    unknown = set(drop.meta.platform_names) - known_platforms()
    for name in sorted(unknown):
        errors.append(f"{md_path.name}: unknown platform '{name}'")
    return errors


def known_platforms() -> set[str]:
    from socialdrop.platforms import registry

    return set(registry.names())
