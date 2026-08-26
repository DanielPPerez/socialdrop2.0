from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from socialdrop import state as state_mod
from socialdrop.platforms.base import MAX_RETRIES, PublishError
from socialdrop.schema import VideoDrop, load_drop
from socialdrop.writeback import PlatformRow, write_results

console = Console()


def publish_drop(md_path: Path, only: list[str] | None = None, force: bool = False) -> dict:
    drop: VideoDrop = load_drop(md_path)
    state = state_mod.load_state(md_path)
    if state is None:
        state = state_mod.new_state(md_path, drop.meta.platform_names)

    targets = [p for p in drop.meta.platform_names if only is None or p in only]
    rows: list[PlatformRow] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with Progress(console=console) as progress:
        for name in targets:
            attempt = state.attempt(name)
            if attempt.status == state_mod.STATUS_PUBLISHED and not force:
                rows.append(PlatformRow(name, attempt.url, attempt.published_at, "published"))
                continue
            if attempt.attempts >= MAX_RETRIES and not force:
                rows.append(
                    PlatformRow(name, attempt.url, attempt.published_at, "failed", attempt.error)
                )
                continue

            task = progress.add_task(f"[cyan]{md_path.stem} → {name}", total=None)
            adapter = _adapter_or_none(name)
            if adapter is None:
                attempt.status = state_mod.STATUS_FAILED
                attempt.error = f"unknown platform '{name}'"
                rows.append(PlatformRow(name, None, None, "failed", attempt.error))
                continue

            attempt.status = state_mod.STATUS_PUBLISHING
            attempt.attempts += 1
            state_mod.save_state(md_path, state)
            cfg = drop.meta.platforms[name]
            try:
                result = adapter.publish(drop.path, cfg)
                attempt.status = state_mod.STATUS_PUBLISHED
                attempt.url = result.url
                attempt.post_id = result.post_id
                attempt.published_at = now_iso
                attempt.error = None
                rows.append(PlatformRow(name, result.url, now_iso, "published"))
                console.print(f"  [green]✅ {name}: {result.url or result.post_id}[/green]")
            except PublishError as exc:
                attempt.status = state_mod.STATUS_FAILED
                attempt.error = str(exc)
                rows.append(PlatformRow(name, attempt.url, attempt.published_at, "failed", str(exc)))
                console.print(f"  [red]❌ {name}: {exc}[/red]")
            except Exception as exc:  # unexpected adapter crash
                attempt.status = state_mod.STATUS_FAILED
                attempt.error = f"{type(exc).__name__}: {exc}"
                rows.append(PlatformRow(name, None, None, "failed", attempt.error))
                console.print(f"  [red]❌ {name}: {attempt.error}[/red]")
            finally:
                progress.remove_task(task)

    state.refresh_status()
    state_mod.save_state(md_path, state)
    write_results(md_path, rows)
    return {"state": state, "rows": rows}


def _adapter_or_none(name: str):
    from socialdrop.platforms.registry import get

    try:
        return get(name)
    except KeyError:
        return None


def publish_folder(folder: Path, only: list[str] | None = None, respect_schedule: bool = True) -> dict:
    results = {"published": 0, "skipped": 0, "failed": 0}
    md_files = load_drops(folder)
    for md_path in md_files:
        if respect_schedule and not state_mod.is_due(md_path):
            console.print(f"[yellow]⏳ {md_path.stem}: waiting for schedule[/yellow]")
            results["skipped"] += 1
            continue
        outcome = publish_drop(md_path, only=only)
        st = outcome["state"]
        if st.status == state_mod.STATUS_PUBLISHED:
            results["published"] += 1
        elif st.status == state_mod.STATUS_FAILED:
            results["failed"] += 1
        else:
            results["skipped"] += 1
    return results


def load_drops(folder: Path) -> list[Path]:
    from socialdrop.schema import find_drops

    return find_drops(folder)


def collect_metrics(md_path: Path) -> dict[str, dict]:
    drop = load_drop(md_path)
    state = state_mod.load_state(md_path)
    metrics: dict[str, dict] = {}
    if state is None:
        return metrics
    for name, attempt in state.platforms.items():
        if attempt.status != state_mod.STATUS_PUBLISHED or not attempt.post_id:
            continue
        adapter = _adapter_or_none(name)
        if adapter is None:
            continue
        try:
            m = adapter.metrics(attempt.post_id, drop.meta.platforms[name])
        except Exception as exc:
            console.print(f"  [red]⚠ {name} metrics failed: {exc}[/red]")
            continue
        if m and m.has_any():
            metrics[name] = m.model_dump(exclude={"raw"})
    return metrics


def sync_folder_stats(folder: Path) -> int:
    from socialdrop.writeback import write_insights

    count = 0
    for md_path in load_drops(folder):
        metrics = collect_metrics(md_path)
        if metrics:
            write_insights(md_path, metrics)
            console.print(f"[green]📊 {md_path.name}: updated insights for {len(metrics)} platform(s)[/green]")
            count += 1
    return count