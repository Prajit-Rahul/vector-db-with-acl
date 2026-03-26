# vecgate/tests/test_adapter.py
import pytest
import psycopg
from vecgate.adapters.pgvector import PgVectorBackend
from vecgate.core.config import Settings
from vecgate.core.errors import ValidationError, NotFoundError
from vecgate.core.models import IngestRequest, ChunkIn, UserContext
import os

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/vecgate_test",
)


@pytest.fixture
async def conn():
    async with await psycopg.AsyncConnection.connect(TEST_DB_URL) as c:
        yield c


@pytest.fixture
def backend():
    s = Settings(database_url=TEST_DB_URL)
    return PgVectorBackend(s)


@pytest.mark.asyncio
async def test_ingest_and_search(conn, backend):
    # Create prerequisite data
    await conn.execute("INSERT INTO facets (name) VALUES ('test_facet') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM facets WHERE name = 'test_facet'")
    facet_row = await cur.fetchone()
    facet_id = facet_row[0]

    req = IngestRequest(
        document_id="11111111-1111-1111-1111-111111111111",
        facet="test_facet",
        chunks=[ChunkIn(content="hello world", embedding=[0.1]*1536, chunk_index=0)],
    )
    resp = await backend.ingest(conn, req)
    assert len(resp.chunk_ids) == 1

    ctx = UserContext(user_id=1, facet_ids=[facet_id], group_ids=[])
    results = await backend.search(conn, ctx, [0.1]*1536, top_k=5)
    assert len(results) >= 1
    assert results[0].content == "hello world"
    assert 0 <= results[0].distance <= 2


@pytest.mark.asyncio
async def test_search_empty_facets_returns_empty(conn, backend):
    ctx = UserContext(user_id=1, facet_ids=[], group_ids=[])
    results = await backend.search(conn, ctx, [0.1]*1536, top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_wrong_dimension_raises(conn, backend):
    req = IngestRequest(
        document_id="22222222-2222-2222-2222-222222222222",
        facet="test_facet",
        chunks=[ChunkIn(content="x", embedding=[0.1]*10, chunk_index=0)],
    )
    with pytest.raises(ValidationError):
        await backend.ingest(conn, req)


@pytest.mark.asyncio
async def test_unknown_facet_raises(conn, backend):
    req = IngestRequest(
        document_id="33333333-3333-3333-3333-333333333333",
        facet="nonexistent_facet",
        chunks=[ChunkIn(content="x", embedding=[0.1]*1536, chunk_index=0)],
    )
    with pytest.raises(NotFoundError):
        await backend.ingest(conn, req)
