# src/vecgate/core/db.py
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncIterator

import psycopg
from psycopg_pool import AsyncConnectionPool

from vecgate.core.config import Settings
from vecgate.core.errors import BackendError, SchemaError, ConfigError

_pool: AsyncConnectionPool | None = None


async def init_pool(settings: Settings) -> None:
    global _pool
    if not settings.database_url:
        raise ConfigError("VECGATE_DATABASE_URL is not set")
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def acquire() -> AsyncIterator[psycopg.AsyncConnection]:
    if _pool is None:
        raise SchemaError("DB pool not initialised — call init_pool() first")
    try:
        async with _pool.connection() as conn:
            yield conn
    except psycopg.OperationalError as e:
        raise BackendError(str(e)) from e
