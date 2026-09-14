from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jose import jwt
from pydantic import BaseModel

from socialdrop.auth.connections import load_user_connections, save_connection

# JWT settings
JWT_SECRET = os.environ.get("SOCIALDROP_JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 30  # 30 days

# User storage
USERS_FILE = Path.home() / ".config" / "socialdrop" / "users.json"


def _read_users() -> dict[str, Any]:
    if not USERS_FILE.exists():
        return {}
    import json
    return json.loads(USERS_FILE.read_text())


def _write_users(data: dict[str, Any]) -> None:
    import json
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(data, indent=2))
    import stat
    import os
    os.chmod(USERS_FILE, stat.S_IRUSR | stat.S_IWUSR)


def _user_key_by_google_sub(google_sub: str) -> str:
    return f"google_sub:{google_sub}"


def _user_key_by_email(email: str) -> str:
    return f"email:{email.lower()}"


def _user_key_by_id(user_id: str) -> str:
    return f"id:{user_id}"


def create_user_if_not_exists(
    email: str,
    name: str | None = None,
    avatar_url: str | None = None,
    google_sub: str | None = None,
) -> tuple[str, bool]:
    """Create user if not exists. Returns (user_id, created)."""
    data = _read_users()
    
    # Check by google_sub first
    if google_sub:
        key = _user_key_by_google_sub(google_sub)
        if key in data:
            user_id = data[key]
            user_data = data[_user_key_by_id(user_id)]
            # Update avatar/name if changed
            updated = False
            if name and user_data.get("name") != name:
                user_data["name"] = name
                updated = True
            if avatar_url and user_data.get("avatar_url") != avatar_url:
                user_data["avatar_url"] = avatar_url
                updated = True
            if updated:
                _write_users(data)
            return user_id, False
    
    # Check by email
    email_key = _user_key_by_email(email)
    if email_key in data:
        user_id = data[email_key]
        user_data = data[_user_key_by_id(user_id)]
        # Link google_sub if not linked
        if google_sub and _user_key_by_google_sub(google_sub) not in data:
            data[_user_key_by_google_sub(google_sub)] = user_id
        # Update avatar/name if changed
        updated = False
        if name and user_data.get("name") != name:
            user_data["name"] = name
            updated = True
        if avatar_url and user_data.get("avatar_url") != avatar_url:
            user_data["avatar_url"] = avatar_url
            updated = True
        if updated or google_sub:
            _write_users(data)
        return user_id, False
    
    # Create new user
    import uuid
    user_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    
    user_data = {
        "id": user_id,
        "email": email.lower(),
        "name": name,
        "avatar_url": avatar_url,
        "created_at": now,
    }
    
    data[_user_key_by_id(user_id)] = user_data
    data[email_key] = user_id
    if google_sub:
        data[_user_key_by_google_sub(google_sub)] = user_id
    
    _write_users(data)
    return user_id, True


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    data = _read_users()
    return data.get(_user_key_by_id(user_id))


def create_api_token(user_id: str) -> str:
    """Create a signed JWT token for the user."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + JWT_EXPIRY_HOURS * 3600,
        "type": "api_token",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_api_token(token: str) -> str | None:
    """Verify JWT token and return user_id if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "api_token":
            return None
        return payload.get("sub")
    except Exception:
        return None


def is_local_mode() -> bool:
    return os.environ.get("SOCIALDROP_MODE", "").lower() == "local"