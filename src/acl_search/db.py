"""Backward-compatible db exports."""

from .core.db import close_pool, connection, get_pool, init_pool

__all__ = ["init_pool", "get_pool", "close_pool", "connection"]
