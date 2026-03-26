# src/vecgate/sdk.py
"""VecGate and AsyncVecGate — the public SDK API."""
from __future__ import annotations
import asyncio
from typing import Any
import psycopg
from vecgate.acl.resolver import resolve_user_context
from vecgate.admin.admin import AdminClient
from vecgate.core.config import Settings
from vecgate.core.errors import ConfigError
from vecgate.core.models import ChunkIn, IngestRequest, IngestResponse, SearchResult
from vecgate.embeddings.provider import StubEmbeddingProvider
from vecgate.ingest.ingest import ingest_chunks
from vecgate.search.engine import fan_out_search


class AsyncVecGate:
    """Async SDK — use with `await` inside async code."""

    def __init__(
        self,
        db_url: str | None = None,
        settings: Settings | None = None,
        embedding_provider=None,
    ):
        if settings:
            self._settings = settings
        else:
            s = Settings()
            if db_url:
                s = s.model_copy(update={"database_url": db_url})
            if not s.database_url:
                raise ConfigError("db_url or VECGATE_DATABASE_URL is required")
            self._settings = s

        self._embedding_provider = embedding_provider or StubEmbeddingProvider()
        self._admin = AdminClient(self._settings)

    async def _conn(self) -> psycopg.AsyncConnection:
        return await psycopg.AsyncConnection.connect(self._settings.database_url)

    async def init(self, enable_rls: bool | None = None) -> None:
        """Bootstrap schema. Idempotent — safe to call on existing DB."""
        rls = enable_rls if enable_rls is not None else self._settings.enable_rls
        from vecgate.adapters.pgvector import PgVectorBackend
        backend = PgVectorBackend(self._settings)
        await backend.init_schema(enable_rls=rls)

    async def create_facet(self, name: str, description: str | None = None) -> int:
        async with await self._conn() as conn:
            return await self._admin.create_facet(conn, name, description)

    async def create_role(self, name: str, facets: list[str],
                          description: str | None = None) -> int:
        async with await self._conn() as conn:
            return await self._admin.create_role(conn, name, facets, description)

    async def assign_role(self, user_id: int, role: str) -> None:
        async with await self._conn() as conn:
            await self._admin.assign_role(conn, user_id, role)

    async def create_group(self, name: str, description: str | None = None) -> str:
        async with await self._conn() as conn:
            return await self._admin.create_group(conn, name, description)

    async def assign_group(self, user_id: int, group: str) -> None:
        async with await self._conn() as conn:
            await self._admin.assign_group(conn, user_id, group)

    async def ingest(
        self,
        document_id: str,
        facet: str,
        chunks: list[ChunkIn],
    ) -> IngestResponse:
        req = IngestRequest(document_id=document_id, facet=facet, chunks=chunks)
        async with await self._conn() as conn:
            return await ingest_chunks(conn, req, self._settings.embedding_dimensions)

    async def search(
        self,
        user_id: int,
        embedding: list[float] | None = None,
        query_text: str | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        if embedding is None and query_text is None:
            raise ValueError("Provide either embedding or query_text")
        if embedding is None:
            embedding = await self._embedding_provider.embed(query_text)
        top_k = min(top_k, self._settings.max_top_k)
        async with await self._conn() as conn:
            ctx = await resolve_user_context(conn, user_id)
            return await fan_out_search(
                conn, ctx, embedding, top_k, self._settings.embedding_dimensions
            )


class VecGate:
    """Sync SDK — wraps AsyncVecGate for use in synchronous code."""

    def __init__(self, db_url: str | None = None, settings: Settings | None = None,
                 embedding_provider=None):
        self._async = AsyncVecGate(db_url=db_url, settings=settings,
                                   embedding_provider=embedding_provider)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def init(self, enable_rls: bool | None = None) -> None:
        self._run(self._async.init(enable_rls=enable_rls))

    def create_facet(self, name: str, description: str | None = None) -> int:
        return self._run(self._async.create_facet(name, description))

    def create_role(self, name: str, facets: list[str],
                    description: str | None = None) -> int:
        return self._run(self._async.create_role(name, facets, description))

    def assign_role(self, user_id: int, role: str) -> None:
        self._run(self._async.assign_role(user_id, role))

    def create_group(self, name: str, description: str | None = None) -> str:
        return self._run(self._async.create_group(name, description))

    def assign_group(self, user_id: int, group: str) -> None:
        self._run(self._async.assign_group(user_id, group))

    def ingest(self, document_id: str, facet: str, chunks: list[ChunkIn]) -> IngestResponse:
        return self._run(self._async.ingest(document_id, facet, chunks))

    def search(self, user_id: int, embedding: list[float] | None = None,
               query_text: str | None = None, top_k: int = 10) -> list[SearchResult]:
        return self._run(self._async.search(user_id=user_id, embedding=embedding,
                                            query_text=query_text, top_k=top_k))
