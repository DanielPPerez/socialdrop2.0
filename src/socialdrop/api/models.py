from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from socialdrop.platforms.base import PublishResult
from socialdrop.schema import PlatformConfig


class DropCreate(BaseModel):
    title: str
    schedule: datetime | None = None
    timezone: str = "America/Mexico_City"
    platforms: dict[str, PlatformConfig]
    hashtags: list[str] = []
    body: str = ""
    public: bool = False


class InsightsRow(BaseModel):
    platform: str
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    watch_pct: float | None = None


class DropOut(DropCreate):
    id: str
    video_filename: str
    status: Literal["draft", "scheduled", "publishing", "published", "failed"]
    published: list[PublishResult] = []
    insights: list[InsightsRow] = []


class PublicDropOut(BaseModel):
    id: str
    title: str
    thumbnail_url: str | None = None
    platforms: list[dict[str, str]]  # [{"name": "youtube", "url": "https://..."}]
    published_at: datetime | None = None


class User(BaseModel):
    id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class PlatformConnection(BaseModel):
    user_id: str
    platform: str
    account_label: str | None = None
    connected_at: datetime


class PlatformStatus(BaseModel):
    platform: str
    configured: bool
    authenticated: bool
    detail: str | None = None


class AuthStartResponse(BaseModel):
    authorize_url: str
    state: str


class AuthCallbackResponse(BaseModel):
    status: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: str
    platform: str | None = None
    detail: str | None = None
