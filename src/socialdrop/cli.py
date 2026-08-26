from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from socialdrop import __version__

app = typer.Typer(
    name="socialdrop",
    help="Drop a video and an md file in a folder. Every platform publishes itself.",
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Authenticate platform accounts (OAuth; passwords are never stored).")
app.add_typer(auth_app, name="auth")

console = Console()


def _folder(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise typer.BadParameter(f"{p} is not a directory")
    return p


@app.command()
def version() -> None:
    console.print(f"socialdrop {__version__}")


@app.command()
def doctor(folder: Path = typer.Argument(Path("."), help="Folder to scan.")) -> None:
    """Report per-platform setup status and validate drops in FOLDER."""
    from socialdrop.auth import store
    from socialdrop.platforms.registry import all_adapters
    from socialdrop.schema import find_drops, validate_drop_file

    table = Table(title="Platform status")
    table.add_column("Platform", style="cyan")
    table.add_column("Ready", style="bold")
    table.add_column("Detail")
    for adapter in all_adapters():
        ready, detail = adapter.is_ready()
        table.add_row(adapter.name, "✅" if ready else "—", detail)
    console.print(table)
    console.print(f"Token storage: [bold]{store.storage_backend()}[/bold]")

    md_files = find_drops(_folder(str(folder)))
    problems: list[str] = []
    for md_path in md_files:
        problems.extend(validate_drop_file(md_path))
    if not md_files:
        console.print("[yellow]No .md drop files found.[/yellow]")
        return
    if problems:
        for problem in problems:
            console.print(f"[red]✗ {problem}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓ {len(md_files)} drop file(s) valid[/green]")


@app.command()
def publish(
    folder: Path = typer.Argument(Path("."), help="Drop folder."),
    only: list[str] | None = typer.Option(None, "--only", "-o", help="Restrict to platforms."),
    ignore_schedule: bool = typer.Option(False, "--now", help="Publish even if schedule is in the future."),
) -> None:
    """Scan FOLDER and publish every due video drop."""
    from socialdrop.publisher import publish_folder

    results = publish_folder(_folder(str(folder)), only=only, respect_schedule=not ignore_schedule)
    color = "green" if results["failed"] == 0 else "red"
    console.print(
        f"[{color}]published={results['published']} failed={results['failed']} "
        f"waiting={results['skipped']}[/{color}]"
    )
    raise typer.Exit(0 if results["failed"] == 0 else 1)


@app.command()
def stats(
    folder: Path = typer.Argument(Path("."), help="Drop folder."),
    loop_minutes: int = typer.Option(0, help="Resync forever every N minutes."),
) -> None:
    """Pull per-platform metrics and write Insights tables into each md file."""
    import time as time_mod

    from socialdrop.publisher import sync_folder_stats

    target = _folder(str(folder))
    while True:
        count = sync_folder_stats(target)
        if count == 0:
            console.print("[yellow]no published videos with metrics yet[/yellow]")
        if loop_minutes <= 0:
            return
        time_mod.sleep(loop_minutes * 60)


@app.command()
def watch(folder: Path = typer.Argument(Path("."), help="Drop folder.")) -> None:
    """Live-watch FOLDER; new video+md pairs publish automatically."""
    from socialdrop.watcher import watch_folder

    watch_folder(_folder(str(folder)))


@app.command()
def demo(out_dir: Path = typer.Argument(Path("demo"), help="Output folder.")) -> None:
    """Create a sample drop folder and run it end-to-end against the mock platform."""
    from socialdrop.demo import run_demo

    run_demo(Path(out_dir))


@auth_app.command("login")
def auth_login(platform: str) -> None:
    """Run the OAuth flow for PLATFORM (opens browser; PKCE where supported)."""
    from socialdrop.auth import oauth, store

    cfg = oauth.OAUTH_CONFIGS.get(platform)
    if cfg is None:
        supported = ", ".join(sorted(oauth.OAUTH_CONFIGS))
        console.print(f"[red]No browser-OAuth config for '{platform}'. Supported: {supported}[/red]")
        console.print(
            "[dim]bluesky uses app passwords: set SOCIALDROP_BLUESKY_HANDLE and "
            "SOCIALDROP_BLUESKY_APP_PASSWORD, or youtube/x tokens via SOCIALDROP_<PLATFORM>_ACCESS_TOKEN.[/dim]"
        )
        raise typer.Exit(1)
    try:
        token = oauth.run_authorization_code_flow(cfg)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    store.save_token(platform, token)
    console.print(f"[green]✅ {platform} authenticated. Token stored in {store.storage_backend()}[/green]")


@auth_app.command("status")
def auth_status() -> None:
    """Show which platforms have stored credentials."""
    from socialdrop.auth.store import configured_platforms, storage_backend

    platforms = configured_platforms()
    console.print(f"Storage: {storage_backend()}")
    if not platforms:
        console.print("No credentials stored.")
        return
    for name in platforms:
        console.print(f"✅ {name}")


@auth_app.command("logout")
def auth_logout(platform: str) -> None:
    """Delete stored credentials for PLATFORM."""
    from socialdrop.auth import store

    store.delete_token(platform)
    console.print(f"[green]Removed {platform} credentials.[/green]")


if __name__ == "__main__":
    app()
