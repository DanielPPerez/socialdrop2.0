from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dateutil import parser as dateutil_parser
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette import status

from socialdrop import __version__
from socialdrop.api.events import event_manager
from socialdrop.api.models import (
    AuthCallbackResponse,
    AuthStartResponse,
    DropCreate,
    DropOut,
    ErrorResponse,
    InsightsRow,
    PlatformConnection,
    PlatformStatus,
    PublicDropOut,
    User,
)
from socialdrop.auth import oauth, store
from socialdrop.auth.connections import (
    load_connection,
    load_user_connections,
    save_connection,
)
from socialdrop.auth.oauth import OAUTH_CONFIGS, generate_pkce_pair
from socialdrop.jobs import Job, JobQueue
from socialdrop.notifier import DiscordWebhook, EmailSMTP, Notifier
from socialdrop.platforms.base import PublishResult
from socialdrop.platforms.exceptions import (
    PlatformAuthError,
    PlatformRateLimitError,
    PlatformValidationError,
)
from socialdrop.platforms.registry import all_adapters
from socialdrop.publisher import publish_drop, sync_folder_stats
from socialdrop.schema import find_drops, load_drop, video_for
from socialdrop.state import DropState, load_state, new_state, save_state

API_KEY_VALUE = os.environ.get("SOCIALDROP_API_KEY", "")
API_BASE_URL = os.environ.get("SOCIALDROP_API_URL", "http://localhost:8000")


def _api_key() -> str:
    return os.environ.get("SOCIALDROP_API_KEY", "")


def _get_drops_folder() -> Path:
    return Path(os.environ.get("SOCIALDROP_API_DROPS_FOLDER", "./drops")).expanduser().resolve()


AUTH_SESSIONS: dict[str, dict[str, Any]] = {}


router = APIRouter()


def _require_api_key(request: Request) -> None:
    key = request.headers.get("x-api-key", "")
    if not _api_key() or key != _api_key():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def _map_status(state: DropState | None) -> Literal["draft", "scheduled", "publishing", "published", "failed"]:
    if state is None:
        return "draft"
    if state.status == "discovered":
        return "draft"
    if state.status == "scheduled":
        return "scheduled"
    if state.status == "publishing":
        return "publishing"
    if state.status == "published":
        return "published"
    if state.status == "failed":
        return "failed"
    return "draft"


def _load_insights(md_path: Path) -> list[InsightsRow]:
    insights: list[InsightsRow] = []
    content = md_path.read_text(encoding="utf-8")
    start = content.find("<!-- socialdrop:insights:start -->")
    end = content.find("<!-- socialdrop:insights:end -->")
    if start == -1 or end == -1:
        return insights
    block = content[start + len("<!-- socialdrop:insights:start -->") : end]
    for line in block.splitlines():
        if line.startswith("| ") and not line.startswith("| Platform "):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 6:
                insights.append(
                    InsightsRow(
                        platform=parts[0],
                        views=_parse_int(parts[1]),
                        likes=_parse_int(parts[2]),
                        comments=_parse_int(parts[3]),
                        shares=_parse_int(parts[4]),
                        watch_pct=_parse_pct(parts[5]),
                    )
                )
    return insights


def _parse_int(value: str) -> int | None:
    value = value.replace(",", "").replace("k", "000").replace("m", "000000")
    if value in ("—", "-", ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_pct(value: str) -> float | None:
    value = value.replace("%", "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _drop_to_out(drop_path: Path, state: DropState | None) -> DropOut:
    drop = load_drop(drop_path)
    video = video_for(drop_path)
    published: list[PublishResult] = []
    insights = _load_insights(drop_path)
    if state:
        for name, attempt in state.platforms.items():
            if attempt.status == "published":
                published.append(
                    PublishResult(
                        platform=name,
                        url=attempt.url,
                        post_id=attempt.post_id,
                        raw={},
                    )
                )
    body = ""
    if drop_path.exists():
        try:
            body = drop_path.read_text(encoding="utf-8").split("---", 2)[-1].strip()
        except Exception:
            body = ""
    schedule_dt: datetime | None = None
    if drop.meta.schedule:
        try:
            schedule_dt = dateutil_parser.parse(drop.meta.schedule)
        except Exception:
            schedule_dt = None
    timezone = "UTC"
    if drop.meta.schedule:
        parts = drop.meta.schedule.split()
        if len(parts) >= 3:
            timezone = parts[-1]
    return DropOut(
        id=drop_path.stem,
        video_filename=video.name if video else "",
        title=drop.meta.title,
        schedule=schedule_dt,
        timezone=timezone,
        platforms=drop.meta.platforms,
        hashtags=drop.meta.hashtags,
        body=body,
        public=drop.meta.public,
        status=_map_status(state),
        published=published,
        insights=insights,
    )


def _resolve_drop(drop_id: str) -> Path:
    _get_drops_folder().mkdir(parents=True, exist_ok=True)
    for md_path in find_drops(_get_drops_folder()):
        if md_path.stem == drop_id:
            return md_path
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")


@router.get("/platforms", response_model=list[PlatformStatus], dependencies=[Depends(_require_api_key)])
async def list_platforms() -> list[PlatformStatus]:
    statuses: list[PlatformStatus] = []
    for adapter in all_adapters():
        configured = False
        authenticated = False
        detail = None
        token = store.load_token(adapter.name)
        if token:
            configured = True
            authenticated = True
            detail = "token stored"
        else:
            env_vars = {
                "youtube": ["SOCIALDROP_YOUTUBE_CLIENT_ID", "SOCIALDROP_YOUTUBE_CLIENT_SECRET"],
                "tiktok": ["SOCIALDROP_TIKTOK_CLIENT_ID", "SOCIALDROP_TIKTOK_CLIENT_SECRET"],
                "instagram": ["SOCIALDROP_INSTAGRAM_CLIENT_ID", "SOCIALDROP_INSTAGRAM_CLIENT_SECRET"],
                "x": ["SOCIALDROP_X_CLIENT_ID", "SOCIALDROP_X_CLIENT_SECRET"],
                "linkedin": ["SOCIALDROP_LINKEDIN_CLIENT_ID", "SOCIALDROP_LINKEDIN_CLIENT_SECRET"],
                "bluesky": ["SOCIALDROP_BLUESKY_HANDLE", "SOCIALDROP_BLUESKY_APP_PASSWORD"],
            }.get(adapter.name, [])
            configured = bool(env_vars) and all(os.environ.get(v) for v in env_vars)
            ready, detail = await adapter.is_ready()
            authenticated = ready
        statuses.append(
            PlatformStatus(
                platform=adapter.name,
                configured=configured,
                authenticated=authenticated,
                detail=detail,
            )
        )
    return statuses


@router.post(
    "/platforms/{platform}/auth/start",
    response_model=AuthStartResponse,
    dependencies=[Depends(_require_api_key)],
)
async def start_auth(platform: str) -> AuthStartResponse:
    cfg = OAUTH_CONFIGS.get(platform)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No OAuth config for platform '{platform}'",
        )
    state = secrets.token_urlsafe(24)
    redirect_uri = f"{API_BASE_URL}/api/v1/platforms/{platform}/auth/callback"
    verifier = None
    if cfg.use_pkce:
        verifier, challenge = generate_pkce_pair()
    AUTH_SESSIONS[state] = {"platform": platform, "verifier": verifier}
    params = {
        "client_id": oauth.client_id_for(cfg),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(cfg.scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    if cfg.use_pkce and verifier:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    query = "&".join(f"{k}={v}" for k, v in params.items())
    authorize_url = f"{cfg.auth_url}?{query}"
    return AuthStartResponse(authorize_url=authorize_url, state=state)


@router.get(
    "/platforms/{platform}/auth/callback",
    response_model=AuthCallbackResponse,
    dependencies=[Depends(_require_api_key)],
)
async def auth_callback(platform: str, code: str = Query(...), state: str = Query(...)) -> AuthCallbackResponse:
    session = AUTH_SESSIONS.pop(state, None)
    if not session or session.get("platform") != platform:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    cfg = OAUTH_CONFIGS.get(platform)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No OAuth config for platform '{platform}'",
        )
    redirect_uri = f"{API_BASE_URL}/api/v1/platforms/{platform}/auth/callback"
    try:
        token = oauth.run_authorization_code_flow(
            cfg, redirect_uri=redirect_uri, code=code, verifier=session.get("verifier")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Auth failed: {exc}",
        ) from exc
    store.save_token(platform, token)
    await event_manager.publish(
        {"drop_id": "", "status": "auth", "message": f"{platform} authenticated", "ts": ""}
    )
    return AuthCallbackResponse(status="ok", detail=f"{platform} token stored")


JOB_QUEUE = JobQueue()
NOTIFIER: Notifier | None = None


def _get_notifier() -> Notifier | None:
    global NOTIFIER
    if NOTIFIER is None:
        webhook = os.environ.get("SOCIALDROP_DISCORD_WEBHOOK")
        if webhook:
            NOTIFIER = DiscordWebhook(webhook)
        else:
            smtp_host = os.environ.get("SOCIALDROP_SMTP_HOST")
            if smtp_host:
                NOTIFIER = EmailSMTP(
                    host=smtp_host,
                    port=int(os.environ.get("SOCIALDROP_SMTP_PORT", "587")),
                    username=os.environ.get("SOCIALDROP_SMTP_USER", ""),
                    password=os.environ.get("SOCIALDROP_SMTP_PASS", ""),
                    from_addr=os.environ.get("SOCIALDROP_SMTP_FROM", ""),
                    to_addrs=os.environ.get("SOCIALDROP_SMTP_TO", "").split(","),
                )
    return NOTIFIER


@router.get("/drops", response_model=list[DropOut], dependencies=[Depends(_require_api_key)])
async def list_drops() -> list[DropOut]:
    _get_drops_folder().mkdir(parents=True, exist_ok=True)
    out: list[DropOut] = []
    for md_path in find_drops(_get_drops_folder()):
        state = load_state(md_path)
        try:
            out.append(_drop_to_out(md_path, state))
        except Exception:
            continue
    return out


@router.post("/drops", response_model=DropOut, dependencies=[Depends(_require_api_key)])
async def create_drop(
    video: UploadFile = File(...),
    drop_create: str = Form(...),
) -> DropOut:
    _get_drops_folder().mkdir(parents=True, exist_ok=True)
    data = DropCreate.model_validate_json(drop_create)
    original_name = video.filename or "video.mp4"
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_name)
    video_path = _get_drops_folder() / safe_name
    if video_path.exists():
        stem, suffix = video_path.stem, video_path.suffix
        i = 1
        while video_path.exists():
            video_path = _get_drops_folder() / f"{stem}_{i}{suffix}"
            i += 1
    md_path = video_path.with_suffix(".md")
    video_path.write_bytes(await video.read())
    schedule_str = ""
    if data.schedule:
        schedule_str = data.schedule.strftime("%Y-%m-%d %H:%M") + f" {data.timezone}"
    md_content = f"""---
title: {data.title}
schedule: "{schedule_str}"
platforms:
"""
    for name in data.platforms.keys():
        md_content += f"  {name}: {{}}\n"
    if data.hashtags:
        md_content += f"hashtags: {data.hashtags}\n"
    if data.public:
        md_content += "public: true\n"
    md_content += "---\n"
    md_content += data.body + "\n"
    md_path.write_text(md_content, encoding="utf-8")
    state = new_state(md_path, list(data.platforms.keys()))
    save_state(md_path, state)
    return _drop_to_out(md_path, state)


@router.get("/drops/{drop_id}", response_model=DropOut, dependencies=[Depends(_require_api_key)])
async def get_drop(drop_id: str) -> DropOut:
    md_path = _resolve_drop(drop_id)
    state = load_state(md_path)
    return _drop_to_out(md_path, state)


@router.post("/drops/{drop_id}/publish", response_model=DropOut, dependencies=[Depends(_require_api_key)])
async def publish_drop_api(drop_id: str) -> DropOut:
    md_path = _resolve_drop(drop_id)
    drop = load_drop(md_path)
    state = load_state(md_path)
    if state is None:
        state = new_state(md_path, drop.meta.platform_names)
    state.status = "publishing"
    save_state(md_path, state)
    for platform in drop.meta.platform_names:
        job = Job(drop_id=drop_id, platform=platform, payload={"md_path": str(md_path)})
        JOB_QUEUE.enqueue(job)
    await event_manager.publish(
        {
            "drop_id": drop_id,
            "status": "publishing",
            "message": f"queued {len(drop.meta.platform_names)} jobs",
            "ts": "",
        }
    )
    return _drop_to_out(md_path, state)


@router.post("/drops/{drop_id}/stats/refresh", response_model=DropOut, dependencies=[Depends(_require_api_key)])
async def refresh_stats(drop_id: str) -> DropOut:
    md_path = _resolve_drop(drop_id)
    await sync_folder_stats(_get_drops_folder())
    state = load_state(md_path)
    await event_manager.publish(
        {
            "drop_id": drop_id,
            "status": state.status if state else "draft",
            "message": "insights refreshed",
            "ts": "",
        }
    )
    return _drop_to_out(md_path, state)


@router.delete("/drops/{drop_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_require_api_key)])
async def delete_drop(drop_id: str) -> None:
    md_path = _resolve_drop(drop_id)
    video = video_for(md_path)
    if md_path.exists():
        md_path.unlink()
    if video and video.exists():
        video.unlink()
    return None


def _current_user_id(request: Request) -> str:
    """Get user identifier from API key (placeholder for real auth in Phase B)."""
    api_key = request.headers.get("x-api-key", "")
    if not api_key:
        return "anonymous"
    # Use a hash of the API key as user ID for now
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


@router.get("/me", response_model=User, dependencies=[Depends(_require_api_key)])
async def get_me(request: Request) -> User:
    user_id = _current_user_id(request)
    # Placeholder user - in Phase B this will come from auth session
    return User(
        id=user_id,
        email=f"{user_id}@socialdrop.local",
        name="API User",
        avatar_url=None,
        created_at=datetime.now(timezone.utc),
    )


@router.get("/me/connections", response_model=list[PlatformConnection], dependencies=[Depends(_require_api_key)])
async def get_my_connections(request: Request) -> list[PlatformConnection]:
    user_id = _current_user_id(request)
    connections = load_user_connections(user_id)
    result: list[PlatformConnection] = []
    for conn in connections:
        result.append(
            PlatformConnection(
                user_id=conn["user_id"],
                platform=conn["platform"],
                account_label=conn.get("account_label"),
                connected_at=datetime.fromisoformat(conn["connected_at"]),
            )
        )
    return result


@router.get("/public/drops", response_model=list[PublicDropOut])
async def list_public_drops() -> list[PublicDropOut]:
    """Public endpoint - no API key required. Returns only drops with public=true."""
    _get_drops_folder().mkdir(parents=True, exist_ok=True)
    out: list[PublicDropOut] = []
    for md_path in find_drops(_get_drops_folder()):
        drop = load_drop(md_path)
        if not drop.meta.public:
            continue
        state = load_state(md_path)
        # Find published platforms with URLs
        published_platforms: list[dict[str, str]] = []
        if state:
            for name, attempt in state.platforms.items():
                if attempt.status == "published" and attempt.url:
                    published_platforms.append({"name": name, "url": attempt.url})
        # Get published_at from the earliest published platform
        published_at: datetime | None = None
        if state:
            for attempt in state.platforms.values():
                if attempt.status == "published" and attempt.published_at:
                    try:
                        dt = datetime.fromisoformat(attempt.published_at.replace("Z", "+00:00"))
                        if published_at is None or dt < published_at:
                            published_at = dt
                    except Exception:
                        pass
        out.append(
            PublicDropOut(
                id=md_path.stem,
                title=drop.meta.title,
                thumbnail_url=None,  # Could be enhanced later
                platforms=published_platforms,
                published_at=published_at,
            )
        )
    return out


@router.post("/drops/suggest", dependencies=[Depends(_require_api_key)])
async def suggest_drop(video: UploadFile = File(...)) -> dict[str, Any]:
    from socialdrop.ai import suggest_from_video

    path = _get_drops_folder() / f"suggest-{video.filename}"
    path.write_bytes(await video.read())
    try:
        return await suggest_from_video(path)
    finally:
        path.unlink(missing_ok=True)


@router.get("/jobs", dependencies=[Depends(_require_api_key)])
async def list_jobs() -> list[dict[str, Any]]:
    jobs = JOB_QUEUE.get_due_jobs(limit=200)
    return [j.__dict__ for j in jobs]


@router.get("/events", dependencies=[Depends(_require_api_key)])
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream() -> Any:
        queue = event_manager.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            event_manager.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


app = FastAPI(
    title="socialdrop API",
    description="HTTP API for socialdrop",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGIN", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.exception_handler(PlatformAuthError)
async def platform_auth_handler(request: Request, exc: PlatformAuthError) -> Response:
    body = ErrorResponse(
        error=str(exc), platform=getattr(exc, "platform", None), detail=str(exc)
    ).model_dump_json()
    return Response(content=body, status_code=status.HTTP_401_UNAUTHORIZED, media_type="application/json")


@app.exception_handler(PlatformRateLimitError)
async def platform_rate_limit_handler(request: Request, exc: PlatformRateLimitError) -> Response:
    body = ErrorResponse(
        error=str(exc), platform=getattr(exc, "platform", None), detail=str(exc)
    ).model_dump_json()
    return Response(
        content=body,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        media_type="application/json",
    )


@app.exception_handler(PlatformValidationError)
async def platform_validation_handler(request: Request, exc: PlatformValidationError) -> Response:
    body = ErrorResponse(
        error=str(exc), platform=getattr(exc, "platform", None), detail=str(exc)
    ).model_dump_json()
    return Response(
        content=body,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/json",
    )


@app.on_event("startup")
async def startup_event() -> None:
    import asyncio

    async def worker() -> None:
        while True:
            JOB_QUEUE.reset_stuck()
            jobs = JOB_QUEUE.get_due_jobs(limit=10)
            for job in jobs:
                if job.id is None:
                    continue
                JOB_QUEUE.mark_running(job.id)
                try:
                    if job.payload:
                        md_path = Path(job.payload["md_path"])
                        result = await publish_drop(md_path, force=True)
                        state = result["state"]
                        JOB_QUEUE.mark_done(job.id, {"status": state.status})
                        await event_manager.publish(
                            {
                                "drop_id": job.drop_id,
                                "status": state.status,
                                "message": f"{job.platform} published",
                                "ts": "",
                            }
                        )
                        notifier = _get_notifier()
                        if notifier:
                            await notifier.send("publish.succeeded", {"drop_id": job.drop_id, "platform": job.platform})
                    else:
                        JOB_QUEUE.mark_failed(job.id, "missing payload")
                except Exception as exc:
                    retryable = isinstance(exc, (PlatformRateLimitError,)) or (
                        hasattr(exc, "status") and getattr(exc, "status", 500) >= 500
                    )
                    if retryable and JOB_QUEUE.schedule_retry(job, exc):
                        await event_manager.publish(
                            {"drop_id": job.drop_id, "status": "retrying", "message": str(exc), "ts": ""}
                        )
                    else:
                        JOB_QUEUE.mark_failed(job.id, str(exc))
                        await event_manager.publish(
                            {"drop_id": job.drop_id, "status": "failed", "message": str(exc), "ts": ""}
                        )
                        notifier = _get_notifier()
                        if notifier:
                            await notifier.send(
                                "publish.failed",
                                {"drop_id": job.drop_id, "platform": job.platform, "message": str(exc)},
                            )
            await asyncio.sleep(5)

    asyncio.create_task(worker())
