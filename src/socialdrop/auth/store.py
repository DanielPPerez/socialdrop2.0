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
        import keyring.errors
        kr = keyring.get_keyring()
        if hasattr(kr, 'priority') and kr.priority is not None:
            return True
        return False
    except keyring.errors.NoKeyringError:
        return False
    except Exception:
        return False


def _token_key(platform: str, account_id: str | None = None) -> str:
    if account_id:
        return f"{platform}:{account_id}"
    return platform


def save_token(platform: str, token: dict, account_id: str | None = None) -> None:
    key = _token_key(platform, account_id)
    payload = json.dumps(token)
    if _keyring_available():
        keyring.set_password(SERVICE, key, payload)
        return
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tokens = _read_fallback()
    tokens[key] = token
    FALLBACK_FILE.write_text(json.dumps(tokens, indent=2))
    os.chmod(FALLBACK_FILE, stat.S_IRUSR | stat.S_IWUSR)


def load_token(platform: str, account_id: str | None = None) -> dict | None:
    key = _token_key(platform, account_id)
    if _keyring_available():
        raw = keyring.get_password(SERVICE, key)
        if raw:
            return json.loads(raw)
        return None
    return _read_fallback().get(key)


def delete_token(platform: str, account_id: str | None = None) -> None:
    key = _token_key(platform, account_id)
    if _keyring_available():
        try:
            keyring.delete_password(SERVICE, key)
            return
        except Exception:
            pass
    tokens = _read_fallback()
    tokens.pop(key, None)
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_FILE.write_text(json.dumps(tokens, indent=2))


def configured_platforms() -> list[str]:
    from socialdrop.platforms import registry

    return [name for name in registry.names() if any(load_token(name) is not None for _ in [None])]


def _read_fallback() -> dict:
    if not FALLBACK_FILE.exists():
        return {}
    return json.loads(FALLBACK_FILE.read_text())


def storage_backend() -> str:
    return "os-keyring" if _keyring_available() else f"file:{FALLBACK_FILE} (0600)"
