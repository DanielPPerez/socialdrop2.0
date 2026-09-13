from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from socialdrop.platforms.registry import names

console = Console()

PLATFORM_ENV_VARS = {
    "youtube": [
        "SOCIALDROP_YOUTUBE_CLIENT_ID",
        "SOCIALDROP_YOUTUBE_CLIENT_SECRET",
    ],
    "tiktok": [
        "SOCIALDROP_TIKTOK_CLIENT_ID",
        "SOCIALDROP_TIKTOK_CLIENT_SECRET",
    ],
    "instagram": [
        "SOCIALDROP_INSTAGRAM_CLIENT_ID",
        "SOCIALDROP_INSTAGRAM_CLIENT_SECRET",
    ],
    "x": [
        "SOCIALDROP_X_CLIENT_ID",
        "SOCIALDROP_X_CLIENT_SECRET",
    ],
    "linkedin": [
        "SOCIALDROP_LINKEDIN_CLIENT_ID",
        "SOCIALDROP_LINKEDIN_CLIENT_SECRET",
    ],
    "bluesky": [
        "SOCIALDROP_BLUESKY_HANDLE",
        "SOCIALDROP_BLUESKY_APP_PASSWORD",
    ],
}

ENV_EXAMPLE_CONTENT = """\
# socialdrop environment variables
# YouTube OAuth client credentials (create at https://console.cloud.google.com/)
SOCIALDROP_YOUTUBE_CLIENT_ID=your_client_id
SOCIALDROP_YOUTUBE_CLIENT_SECRET=your_client_secret
# Optional manual access token override (bypasses OAuth flow)
SOCIALDROP_YOUTUBE_ACCESS_TOKEN=your_access_token
# Optional privacy status for uploads: private, public, unlisted
SOCIALDROP_YOUTUBE_PRIVACY=private

# TikTok OAuth client credentials (create at https://developers.tiktok.com/)
SOCIALDROP_TIKTOK_CLIENT_ID=your_client_id
SOCIALDROP_TIKTOK_CLIENT_SECRET=your_client_secret

# Instagram/Facebook OAuth client credentials (create at https://developers.facebook.com/)
SOCIALDROP_INSTAGRAM_CLIENT_ID=your_client_id
SOCIALDROP_INSTAGRAM_CLIENT_SECRET=your_client_secret

# X (Twitter) OAuth client credentials (create at https://developer.twitter.com/)
SOCIALDROP_X_CLIENT_ID=your_client_id
SOCIALDROP_X_CLIENT_SECRET=your_client_secret

# LinkedIn OAuth client credentials (create at https://www.linkedin.com/developers/)
SOCIALDROP_LINKEDIN_CLIENT_ID=your_client_id
SOCIALDROP_LINKEDIN_CLIENT_SECRET=your_client_secret

# Bluesky app password (never your main password)
SOCIALDROP_BLUESKY_HANDLE=your_handle.bsky.social
SOCIALDROP_BLUESKY_APP_PASSWORD=your_app_password
"""


def _target_platforms(selected: list[str] | None) -> list[str]:
    all_platforms = [n for n in names() if n != "mock"]
    if not selected:
        return all_platforms
    unknown = [p for p in selected if p not in PLATFORM_ENV_VARS]
    if unknown:
        console.print(f"[red]Unknown platforms: {', '.join(unknown)}[/red]")
        raise typer.Exit(1)
    return selected


def _ensure_env_files(folder: Path) -> tuple[Path, Path]:
    example = folder / ".env.example"
    env = folder / ".env"
    if not example.exists():
        example.write_text(ENV_EXAMPLE_CONTENT, encoding="utf-8")
    if not env.exists():
        env.write_text("", encoding="utf-8")
    return example, env


def _load_env(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _save_env(env_path: Path, data: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _missing_vars(platform: str, env_data: dict[str, str]) -> list[str]:
    return [var for var in PLATFORM_ENV_VARS.get(platform, []) if not env_data.get(var)]


def _prompt_for_vars(platform: str, missing: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for var in missing:
        if "SECRET" in var or "PASSWORD" in var:
            value = Prompt.ask(f"Enter {var} for {platform}", password=True)
        else:
            value = Prompt.ask(f"Enter {var} for {platform}")
        values[var] = value
    return values


def _doctor_table(platforms: list[str]) -> Table:
    import asyncio

    from socialdrop.platforms.registry import all_adapters

    table = Table(title="Init status")
    table.add_column("Plataforma", style="cyan")
    table.add_column("Configurada", style="bold")
    table.add_column("Autenticada", style="bold")
    table.add_column("Lista para publicar", style="bold")

    env_path = Path.cwd() / ".env"
    env_data = _load_env(env_path)
    adapters = {a.name: a for a in all_adapters()}
    for platform in platforms:
        env_vars = PLATFORM_ENV_VARS.get(platform, [])
        configured = all(env_data.get(var) for var in env_vars)
        authenticated = False
        adapter = adapters.get(platform)
        if adapter:
            try:
                ready, _ = asyncio.run(adapter.is_ready())
                authenticated = ready
            except Exception:
                authenticated = False
        ready_to_publish = configured and authenticated
        table.add_row(
            platform,
            "✅" if configured else "—",
            "✅" if authenticated else "—",
            "✅" if ready_to_publish else "—",
        )
    return table


def run_init(platforms: list[str] | None, non_interactive: bool) -> None:
    target = _target_platforms(platforms)
    folder = Path.cwd()
    _, env_path = _ensure_env_files(folder)
    env_data = _load_env(env_path)

    missing_all: list[str] = []
    for platform in target:
        missing = _missing_vars(platform, env_data)
        missing_all.extend(missing)
        if non_interactive and missing:
            for var in missing:
                print(f"{var}=missing", file=sys.stderr)
            raise typer.Exit(1)

        if not non_interactive and missing:
            console.print(f"[yellow]Missing vars for {platform}: {', '.join(missing)}[/yellow]")
            values = _prompt_for_vars(platform, missing)
            env_data.update(values)
            _save_env(env_path, env_data)
            console.print(f"[green]Updated {env_path}[/green]")

    if non_interactive and not missing_all:
        console.print("All required variables present.")

    table = _doctor_table(target)
    console.print(table)
