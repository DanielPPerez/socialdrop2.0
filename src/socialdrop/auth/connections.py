from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVICE = "socialdrop"
CONNECTIONS_FILE = Path.home() / ".config" / "socialdrop" / "connections.json"


def _read_connections() -> dict[str, Any]:
    if not CONNECTIONS_FILE.exists():
        return {}
    return json.loads(CONNECTIONS_FILE.read_text())


def _write_connections(data: dict[str, Any]) -> None:
    CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONNECTIONS_FILE.write_text(json.dumps(data, indent=2))
    os.chmod(CONNECTIONS_FILE, stat.S_IRUSR | stat.S_IWUSR)


def _connection_key(user_id: str, platform: str) -> str:
    return f"{user_id}:{platform}"


def save_connection(
    user_id: str,
    platform: str,
    account_label: str | None = None,
) -> None:
    data = _read_connections()
    key = _connection_key(user_id, platform)
    data[key] = {
        "user_id": user_id,
        "platform": platform,
        "account_label": account_label,
        "connected_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_connections(data)


def load_connection(user_id: str, platform: str) -> dict | None:
    data = _read_connections()
    return data.get(_connection_key(user_id, platform))


def load_user_connections(user_id: str) -> list[dict]:
    data = _read_connections()
    return [
        conn for conn in data.values()
        if conn.get("user_id") == user_id
    ]


def delete_connection(user_id: str, platform: str) -> None:
    data = _read_connections()
    data.pop(_connection_key(user_id, platform), None)
    _write_connections(data)