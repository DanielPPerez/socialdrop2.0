from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


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


def client_id_for(cfg: OAuthConfig) -> str:
    import os

    env = cfg.client_id_env.replace("{P}", cfg.platform.upper())
    value = os.environ.get(env)
    if not value:
        raise RuntimeError(f"set {env} before running 'socialdrop auth {cfg.platform}'")
    return value


def client_secret_for(cfg: OAuthConfig) -> str | None:
    import os

    env = cfg.client_secret_env.replace("{P}", cfg.platform.upper())
    return os.environ.get(env)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


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

    def log_message(self, *args):
        pass


def run_authorization_code_flow(
    cfg: OAuthConfig, redirect_uri: str = "http://127.0.0.1:8642/callback", port: int = 8642
) -> dict:
    from rich.console import Console

    console = Console()
    state = secrets.token_urlsafe(24)
    params: dict[str, str] = {
        "client_id": client_id_for(cfg),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": " ".join(cfg.scopes),
    }
    verifier = None
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

    form: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id_for(cfg),
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
        "client_id": client_id_for(cfg),
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


def get_access_token(platform: str) -> str:
    """Return a valid access token for the platform, refreshing when needed.

    Also honors SOCIALDROP_<PLATFORM>_ACCESS_TOKEN as a manual override.
    """
    import os
    import time

    from socialdrop.auth import store

    env_override = os.environ.get(f"SOCIALDROP_{platform.upper()}_ACCESS_TOKEN")
    token = store.load_token(platform)
    if token is None and env_override is None:
        raise RuntimeError(f"{platform} is not authenticated; run 'socialdrop auth login {platform}'")
    if token is None:
        return env_override  # type: ignore[return-value]
    expires_at = token.get("expires_at", 0)
    if expires_at - 60 < time.time():
        refreshed = refresh_token(platform, token)
        if refreshed:
            store.save_token(platform, refreshed)
            token = refreshed
    return token["access_token"]
