# vecgate/tests/test_sdk.py
import pytest
from vecgate import VecGate, AsyncVecGate
from vecgate.core.models import ChunkIn
import os

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/vecgate_test",
)


@pytest.mark.asyncio
async def test_async_sdk_full_flow():
    vg = AsyncVecGate(db_url=TEST_DB_URL)
    await vg.create_facet("sdk_facet")
    await vg.create_role("sdk_role", facets=["sdk_facet"])

    # create user in DB directly for this test
    import psycopg
    async with await psycopg.AsyncConnection.connect(TEST_DB_URL) as conn:
        await conn.execute("INSERT INTO users (username) VALUES ('sdk_user') ON CONFLICT DO NOTHING")
        cur = await conn.execute("SELECT id FROM users WHERE username='sdk_user'")
        row = await cur.fetchone()
        user_id = row[0]

    await vg.assign_role(user_id, "sdk_role")
    resp = await vg.ingest(
        document_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        facet="sdk_facet",
        chunks=[ChunkIn(content="sdk test doc", embedding=[0.5]*1536, chunk_index=0)],
    )
    assert len(resp.chunk_ids) == 1

    results = await vg.search(user_id=user_id, embedding=[0.5]*1536, top_k=5)
    assert any(r.content == "sdk test doc" for r in results)


def test_vecgate_raises_without_db_url():
    """VecGate should raise ConfigError if no DB URL provided."""
    import os
    from vecgate.core.errors import ConfigError
    # Remove env var if set
    old = os.environ.pop("VECGATE_DATABASE_URL", None)
    try:
        with pytest.raises(ConfigError):
            VecGate()
    finally:
        if old:
            os.environ["VECGATE_DATABASE_URL"] = old
