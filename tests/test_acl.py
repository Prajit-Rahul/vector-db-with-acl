# vecgate/tests/test_acl.py
import pytest
import psycopg
from vecgate.acl.resolver import resolve_user_context
from vecgate.core.models import UserContext
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
async def seed_user_with_role(conn):
    """Returns (user_id, facet_id)."""
    await conn.execute("INSERT INTO users (username) VALUES ('acl_test_user') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='acl_test_user'")
    user = await cur.fetchone()
    await conn.execute("INSERT INTO roles (name) VALUES ('acl_test_role') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM roles WHERE name='acl_test_role'")
    role = await cur.fetchone()
    await conn.execute("INSERT INTO facets (name) VALUES ('acl_test_facet') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM facets WHERE name='acl_test_facet'")
    facet = await cur.fetchone()
    await conn.execute(
        "INSERT INTO user_roles VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (user[0], role[0])
    )
    await conn.execute(
        "INSERT INTO role_facets VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (role[0], facet[0])
    )
    return user[0], facet[0]


@pytest.mark.asyncio
async def test_resolve_user_with_facets(conn, seed_user_with_role):
    user_id, facet_id = seed_user_with_role
    ctx = await resolve_user_context(conn, user_id)
    assert isinstance(ctx, UserContext)
    assert facet_id in ctx.facet_ids
    assert ctx.group_ids == []  # no groups assigned


@pytest.mark.asyncio
async def test_resolve_user_no_roles_empty_facets(conn):
    await conn.execute("INSERT INTO users (username) VALUES ('no_role_user') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='no_role_user'")
    row = await cur.fetchone()
    ctx = await resolve_user_context(conn, row[0])
    assert ctx.facet_ids == []
    assert ctx.group_ids == []


@pytest.mark.asyncio
async def test_resolve_returns_list_not_none(conn):
    """facet_ids and group_ids must never be None."""
    await conn.execute("INSERT INTO users (username) VALUES ('none_test_user') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='none_test_user'")
    row = await cur.fetchone()
    ctx = await resolve_user_context(conn, row[0])
    assert ctx.facet_ids is not None
    assert ctx.group_ids is not None
