"""Database pool lifecycle and connection helpers."""

from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg_pool import ConnectionPool

from .config import Settings

_pool: ConnectionPool | None = None


def init_pool(settings: Settings) -> ConnectionPool:
    """Initialize process-wide connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            max_idle=settings.db_pool_max_idle_seconds,
            kwargs={"autocommit": False},
            open=True,
        )
    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator[Connection]:
    """Yield one pooled connection with transaction control left to callers."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
