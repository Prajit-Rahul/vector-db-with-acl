# vecgate/tests/test_search.py
import pytest
import psycopg
from vecgate.acl.resolver import resolve_user_context
from vecgate.search.engine import fan_out_search
from vecgate.ingest.ingest import ingest_chunks
from vecgate.core.models import IngestRequest, ChunkIn, UserContext
from vecgate.core.errors import ValidationError
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
async def seeded(conn):
    """Seed: user1 has sales_facet; user2 has hr_facet. A chunk restricted to legal_group."""
    await conn.execute("INSERT INTO facets (name) VALUES ('sales_facet'),('hr_facet') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM facets WHERE name='sales_facet'")
    sf = await cur.fetchone()
    cur = await conn.execute("SELECT id FROM facets WHERE name='hr_facet'")
    hf = await cur.fetchone()

    await conn.execute("INSERT INTO roles (name) VALUES ('sales_r'),('hr_r') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM roles WHERE name='sales_r'")
    sr = await cur.fetchone()
    cur = await conn.execute("SELECT id FROM roles WHERE name='hr_r'")
    hr = await cur.fetchone()

    await conn.execute("INSERT INTO role_facets VALUES (%s,%s),(%s,%s) ON CONFLICT DO NOTHING",
                       (sr[0], sf[0], hr[0], hf[0]))

    await conn.execute("INSERT INTO users (username) VALUES ('u_sales'),('u_hr') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='u_sales'")
    us = await cur.fetchone()
    cur = await conn.execute("SELECT id FROM users WHERE username='u_hr'")
    uh = await cur.fetchone()

    await conn.execute("INSERT INTO user_roles VALUES (%s,%s),(%s,%s) ON CONFLICT DO NOTHING",
                       (us[0], sr[0], uh[0], hr[0]))

    await conn.execute("INSERT INTO groups (name) VALUES ('legal_grp') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM groups WHERE name='legal_grp'")
    grp = await cur.fetchone()

    return {"user_sales": us[0], "user_hr": uh[0],
            "facet_sales": sf[0], "facet_hr": hf[0], "group_legal": grp[0]}


@pytest.mark.asyncio
async def test_user_sees_only_own_facet(conn, seeded):
    emb = [0.1] * 1536
    req = IngestRequest(
        document_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", facet="sales_facet",
        chunks=[ChunkIn(content="sales doc", embedding=emb, chunk_index=0)]
    )
    await ingest_chunks(conn, req)

    ctx = await resolve_user_context(conn, seeded["user_sales"])
    results = await fan_out_search(conn, ctx, emb, top_k=5)
    assert all(r.content == "sales doc" for r in results)


@pytest.mark.asyncio
async def test_user_no_facets_returns_empty(conn):
    await conn.execute("INSERT INTO users (username) VALUES ('no_facet_usr') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='no_facet_usr'")
    u = await cur.fetchone()
    ctx = await resolve_user_context(conn, u[0])
    results = await fan_out_search(conn, ctx, [0.1]*1536, top_k=5)
    assert results == []


@pytest.mark.asyncio
async def test_chunk_acl_restricts_access(conn, seeded):
    emb = [0.2] * 1536
    # Ingest a chunk restricted to legal_grp
    req = IngestRequest(
        document_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", facet="sales_facet",
        chunks=[ChunkIn(content="confidential", embedding=emb, chunk_index=0,
                        acl_groups=["legal_grp"])]
    )
    await ingest_chunks(conn, req)

    # sales user NOT in legal_grp — should NOT see restricted chunk
    ctx_no_group = await resolve_user_context(conn, seeded["user_sales"])
    results = await fan_out_search(conn, ctx_no_group, emb, top_k=5)
    assert not any(r.content == "confidential" for r in results)

    # Now add sales user to legal_grp
    await conn.execute(
        "INSERT INTO user_groups VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (seeded["user_sales"], seeded["group_legal"])
    )
    ctx_with_group = await resolve_user_context(conn, seeded["user_sales"])
    results = await fan_out_search(conn, ctx_with_group, emb, top_k=5)
    assert any(r.content == "confidential" for r in results)


@pytest.mark.asyncio
async def test_wrong_embedding_dimension_raises(conn, seeded):
    ctx = UserContext(user_id=seeded["user_sales"],
                      facet_ids=[seeded["facet_sales"]], group_ids=[])
    with pytest.raises(ValidationError):
        await fan_out_search(conn, ctx, [0.1]*10, top_k=5)
