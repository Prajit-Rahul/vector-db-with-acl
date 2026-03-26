# src/vecgate/adapters/base.py
from typing import Protocol, runtime_checkable
import psycopg
from vecgate.core.models import IngestRequest, IngestResponse, SearchResult, UserContext


@runtime_checkable
class VectorBackend(Protocol):
    async def init_schema(self, enable_rls: bool = False) -> None: ...
    async def ingest(self, conn: psycopg.AsyncConnection, request: IngestRequest) -> IngestResponse: ...
    async def search(
        self, conn: psycopg.AsyncConnection, ctx: UserContext, embedding: list[float], top_k: int
    ) -> list[SearchResult]: ...
    async def create_facet(self, conn: psycopg.AsyncConnection, name: str, description: str | None = None) -> int: ...
