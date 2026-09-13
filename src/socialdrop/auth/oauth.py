from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

from socialdrop.auth import store

load_dotenv()


@dataclass
class OAuthConfig:
    platform: str
    auth_url: str
    token_url: str
    scopes: list[str]
    client_id_env: str = "SOCIALDROP_{P}_CLIENT_ID"
    client_secret_env: str = "SOCIALDROP_{P}_CLIENT_SECRET"
    use_pkce: bool = True


OAUTH_CONFIGS: dict[str, OAuthConfig] = {
    "youtube": OAuthConfig(
        platform="youtube",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    ),
    "tiktok": OAuthConfig(
        platform="tiktok",
        auth_url="https://www.tiktok.com/v2/auth/authorize/",
        token_url="https://open.tiktokapis.com/v2/oauth/token/",
        scopes=["user.info.basic", "video.publish", "video.upload"],
    ),
    "instagram": OAuthConfig(
        platform="instagram",
        auth_url="https://www.facebook.com/v21.0/dialog/oauth",
        token_url="https://graph.facebook.com/v21.0/oauth/access_token",
        scopes=["instagram_basic", "instagram_content_publish", "pages_show_list"],
        use_pkce=False,
    ),
    "x": OAuthConfig(
        platform="x",
        auth_url="https://twitter.com/i/oauth2/authorize",
        token_url="https://api.x.com/2/oauth2/token",
        scopes=["tweet.read", "tweet.write", "users.read", "media.write", "offline.access"],
    ),
    "linkedin": OAuthConfig(
        platform="linkedin",
        auth_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        scopes=["w_member_social"],
        use_pkce=False,
    ),
}

# TikTok's OAuth implementation uses "client_key" instead of the standard
# OAuth2 "client_id" parameter name, both in the authorization URL and in
# the token/refresh requests. Every other platform here follows the normal
# "client_id" convention.
CLIENT_ID_PARAM_OVERRIDES: dict[str, str] = {
    "tiktok": "client_key",
}

# Facebook Login only waives its HTTPS requirement for the literal hostname
# "localhost" (not the loopback IP). TikTok does the opposite: it rejects
# "localhost" outright and requires the loopback IP "127.0.0.1". Everyone
# else is fine with either; default to "localhost".
REDIRECT_URI_OVERRIDES: dict[str, str] = {
    "tiktok": "http://127.0.0.1:8642/callback",
}
DEFAULT_REDIRECT_URI = "http://localhost:8642/callback"


def _client_id_param_name(cfg: OAuthConfig) -> str:
    return CLIENT_ID_PARAM_OVERRIDES.get(cfg.platform, "client_id")


def _default_redirect_uri(cfg: OAuthConfig) -> str:
    return REDIRECT_URI_OVERRIDES.get(cfg.platform, DEFAULT_REDIRECT_URI)


def client_id_for(cfg: OAuthConfig) -> str:
    env = cfg.client_id_env.replace("{P}", cfg.platform.upper())
    value = os.environ.get(env)
    if not value:
        raise RuntimeError(f"set {env} before running 'socialdrop auth {cfg.platform}'")
    return value


def client_secret_for(cfg: OAuthConfig) -> str | None:
    env = cfg.client_secret_env.replace("{P}", cfg.platform.upper())
    return os.environ.get(env)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def generate_pkce_pair() -> tuple[str, str]:
    return _pkce_pair()


class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params or "error" in params:
            type(self).result = {k: v[0] for k, v in params.items()}
            self.send_response(200)
            self.end_headers()
            msg = b"<html><body><h3>socialdrop: authorization received. You can close this tab.</h3></body></html>"
            self.wfile.write(msg)
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def run_authorization_code_flow(
    cfg: OAuthConfig,
    redirect_uri: str | None = None,
    port: int = 8642,
    code: str | None = None,
    verifier: str | None = None,
) -> dict:
    from rich.console import Console

    console = Console()
    if redirect_uri is None:
        redirect_uri = _default_redirect_uri(cfg)
    state = secrets.token_urlsafe(24)
    id_param = _client_id_param_name(cfg)
    if code is None:
        params = {
            id_param: client_id_for(cfg),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(cfg.scopes),
        }
        if cfg.use_pkce:
            verifier, challenge = _pkce_pair()
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"

        url = f"{cfg.auth_url}?{urlencode(params)}"
        server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
        console.print(f"[cyan]Opening browser for {cfg.platform} authorization...[/cyan]")
        console.print(f"If the browser does not open, visit:\n[link={url}]{url}[/link]")
        webbrowser.open(url)
        server.serve_forever()

        result = _CallbackHandler.result
        if "error" in result:
            raise RuntimeError(f"authorization failed: {result['error']}")
        code = result.get("code")
        if not code:
            raise RuntimeError("no authorization code received")
    else:
        if verifier is None and cfg.use_pkce:
            verifier, _ = _pkce_pair()

    form: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        id_param: client_id_for(cfg),
    }
    secret = client_secret_for(cfg)
    if secret:
        form["client_secret"] = secret
    if verifier:
        form["code_verifier"] = verifier

    resp = httpx.post(cfg.token_url, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp.raise_for_status()
    token = resp.json()
    if "expires_at" not in token and "expires_in" in token:
        import time

        token["expires_at"] = int(time.time()) + int(token["expires_in"])
    return token


def refresh_token(platform: str, token: dict) -> dict | None:
    cfg = OAUTH_CONFIGS.get(platform)
    if cfg is None or "refresh_token" not in token:
        return None
    form = {
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        _client_id_param_name(cfg): client_id_for(cfg),
    }
    secret = client_secret_for(cfg)
    if secret:
        form["client_secret"] = secret
    try:
        resp = httpx.post(cfg.token_url, data=form)
        resp.raise_for_status()
    except Exception:
        return None
    new_token = resp.json()
    new_token.setdefault("refresh_token", token["refresh_token"])
    if "expires_in" in new_token:
        import time

        new_token["expires_at"] = int(time.time()) + int(new_token["expires_in"])
    return new_token


def get_token(platform: str, account_id: str | None = None) -> dict:
    """Return the full token dict for the platform, refreshing when needed.

    Honors SOCIALDROP_<PLATFORM>_ACCESS_TOKEN as a manual override by wrapping
    it into a minimal dict.
    """
    env_override = os.environ.get(f"SOCIALDROP_{platform.upper()}_ACCESS_TOKEN")
    token = store.load_token(platform, account_id)
    if token is None and env_override is None:
        raise RuntimeError(f"{platform} is not authenticated; run 'socialdrop auth login {platform}'")
    if token is None:
        return {"access_token": env_override, "expires_at": int(time.time()) + 3600}
    expires_at = token.get("expires_at", 0)
    if expires_at - 60 < time.time():
        refreshed = refresh_token(platform, token)
        if refreshed:
            store.save_token(platform, refreshed, account_id)
            token = refreshed
    return token


def get_access_token(platform: str, account_id: str | None = None) -> str:
    """Return a valid access token string for the platform, refreshing when needed.

    Also honors SOCIALDROP_<PLATFORM>_ACCESS_TOKEN as a manual override.
    """
    return get_token(platform, account_id)["access_token"]
