"""MCP server exposing socialdrop operations to any MCP client.

Run:  python mcp/server.py        (stdio transport)
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP("socialdrop")


class DropInfo(BaseModel):
    md: str
    title: str
    schedule: str | None
    platforms: list[str]
    status: str


def _folder(folder: str) -> Path:
    p = Path(folder).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"{p} is not a directory")
    return p


@mcp.tool()
async def list_drops(folder: str = ".") -> list[DropInfo]:
    """List every video drop (md + video pair) in a folder with its publish status."""
    from socialdrop import state as state_mod
    from socialdrop.schema import find_drops, load_drop

    drops = []
    for md_path in find_drops(_folder(folder)):
        drop = load_drop(md_path)
        state = state_mod.load_state(md_path)
        drops.append(
            DropInfo(
                md=md_path.name,
                title=drop.meta.title,
                schedule=drop.meta.schedule,
                platforms=drop.meta.platform_names,
                status=state.status if state else "new",
            )
        )
    return drops


@mcp.tool()
async def doctor(folder: str = ".") -> dict:
    """Report per-platform authentication/setup status and drop-file validation errors."""
    from socialdrop.auth.store import storage_backend
    from socialdrop.platforms.registry import all_adapters
    from socialdrop.schema import find_drops, validate_drop_file

    target = _folder(folder)
    platforms = {}
    for adapter in all_adapters():
        ready, detail = await adapter.is_ready()
        platforms[adapter.name] = {"ready": ready, "detail": detail}
    problems = []
    for md_path in find_drops(target):
        problems.extend(validate_drop_file(md_path))
    return {"token_storage": storage_backend(), "platforms": platforms, "problems": problems}


@mcp.tool()
async def publish(folder: str = ".", only: list[str] | None = None, now: bool = False) -> dict:
    """Publish all due video drops in a folder. Set only=[...] to restrict platforms,
    now=True to ignore future schedules. Returns per-video results."""
    from socialdrop.publisher import publish_folder

    results = await publish_folder(_folder(folder), only=only, respect_schedule=not now)
    return {k: v for k, v in results.items()}


@mcp.tool()
async def get_stats(folder: str = ".") -> dict:
    """Refresh consolidated Insights tables in every md file and return the metrics."""
    from socialdrop.publisher import collect_metrics
    from socialdrop.schema import find_drops
    from socialdrop.writeback import write_insights

    target = _folder(folder)
    out: dict[str, dict] = {}
    for md_path in find_drops(target):
        metrics = await collect_metrics(md_path)
        if metrics:
            write_insights(md_path, metrics)
            out[md_path.name] = metrics
    return out


if __name__ == "__main__":
    mcp.run()
