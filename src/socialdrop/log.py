from __future__ import annotations

import logging
from typing import Any

import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


def bind_drop(drop_id: str) -> None:
    structlog.contextvars.bind_contextvars(drop_id=drop_id)


def unbind_drop() -> None:
    structlog.contextvars.unbind_contextvars("drop_id")


def log_event(event: str, **kwargs: Any) -> None:
    log.info(event, **kwargs)
