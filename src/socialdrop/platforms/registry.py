from __future__ import annotations

from functools import lru_cache

from socialdrop.platforms.adapters import ADAPTERS


@lru_cache(maxsize=1)
def _map() -> dict:
    return {a.name: a for a in ADAPTERS}


def get(name: str):
    adapters = _map()
    if name not in adapters:
        raise KeyError(f"unknown platform '{name}'. Available: {', '.join(sorted(adapters))}")
    return adapters[name]


def all_adapters() -> list:
    return list(ADAPTERS)


def names() -> list[str]:
    return list(_map().keys())
