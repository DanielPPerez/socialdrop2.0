from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PublishResult(BaseModel):
    platform: str
    url: str | None = None
    post_id: str | None = None
    raw: dict[str, Any] = {}


class Metrics(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    watch_pct: float | None = None
    raw: dict[str, Any] = {}

    def has_any(self) -> bool:
        return any(v is not None for v in (self.views, self.likes, self.comments, self.shares, self.watch_pct))


class PublishError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class PlatformAdapter(ABC):
    name: str = "base"
    requires: tuple[str, ...] = ()

    @abstractmethod
    def publish(self, video_path: Path, meta: Any) -> PublishResult:
        ...

    def metrics(self, post_id: str, meta: Any) -> Metrics | None:
        return None

    def is_ready(self) -> tuple[bool, str]:
        import os

        from socialdrop.auth.store import load_token

        if load_token(self.name) is not None:
            return True, "authenticated"
        if os.environ.get(f"SOCIALDROP_{self.name.upper()}_ACCESS_TOKEN"):
            return True, "access token via environment"
        return False, f"not authenticated; run 'socialdrop auth login {self.name}'"
