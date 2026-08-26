from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import keyring

SERVICE = "socialdrop"
FALLBACK_FILE = Path.home() / ".config" / "socialdrop" / "tokens.json"

def _keyring_available() -> bool:
    try:
        priority = keyring.get_keyring().priority
        return priority is not None
    except Exception:
        return False


def save_token(platform: str, token: dict) -> None:
    payload = json.dumps(token)
    if _keyring_available():
        keyring.set_password(SERVICE, platform, payload)
        return
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tokens = _read_fallback()
    tokens[platform] = token
    FALLBACK_FILE.write_text(json.dumps(tokens, indent=2))
    os.chmod(FALLBACK_FILE, stat.S_IRUSR | stat.S_IWUSR)


def load_token(platform: str) -> dict | None:
    if _keyring_available():
        raw = keyring.get_password(SERVICE, platform)
        if raw:
            return json.loads(raw)
        return None
    return _read_fallback().get(platform)


def delete_token(platform: str) -> None:
    if _keyring_available():
        try:
            keyring.delete_password(SERVICE, platform)
            return
        except Exception:
            pass
    tokens = _read_fallback()
    tokens.pop(platform, None)
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_FILE.write_text(json.dumps(tokens, indent=2))


def configured_platforms() -> list[str]:
    from socialdrop.platforms.registry import names

    return [name for name in names() if load_token(name) is not None]


def _read_fallback() -> dict:
    if not FALLBACK_FILE.exists():
        return {}
    return json.loads(FALLBACK_FILE.read_text())


def storage_backend() -> str:
    return "os-keyring" if _keyring_available() else f"file:{FALLBACK_FILE} (0600)"
