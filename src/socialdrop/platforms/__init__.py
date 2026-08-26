from __future__ import annotations

from typing import Any

from socialdrop.platforms.base import Metrics, PlatformAdapter, PublishResult
from socialdrop.schema import PlatformConfig


def get(platform: str) -> PlatformAdapter:
    from socialdrop.platforms import registry

    return registry.get(platform)


def names() -> list[str]:
    from socialdrop.platforms import registry

    return registry.names()


__all__ = ["get", "names", "Metrics", "PlatformAdapter", "PublishResult", "PlatformConfig", "Any"]
