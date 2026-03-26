# vecgate/tests/test_admin.py
import pytest
import psycopg
from vecgate.admin.admin import AdminClient
from vecgate.core.errors import NotFoundError
from vecgate.core.config import Settings
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
def admin():
    return AdminClient(Settings(database_url=TEST_DB_URL))


@pytest.mark.asyncio
async def test_create_and_list_facets(conn, admin):
    await admin.create_facet(conn, "admin_test_facet")
    facets = await admin.list_facets(conn)
    names = [f["name"] for f in facets]
    assert "admin_test_facet" in names


@pytest.mark.asyncio
async def test_create_role_with_facets(conn, admin):
    await admin.create_facet(conn, "role_test_facet")
    await admin.create_role(conn, "role_test_role", facets=["role_test_facet"])
    roles = await admin.list_roles(conn)
    assert any(r["name"] == "role_test_role" for r in roles)


@pytest.mark.asyncio
async def test_assign_role_to_user(conn, admin):
    await conn.execute("INSERT INTO users (username) VALUES ('admin_test_user') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='admin_test_user'")
    user = await cur.fetchone()
    await admin.create_role(conn, "assign_test_role", facets=[])
    await admin.assign_role(conn, user_id=user[0], role="assign_test_role")
    cur2 = await conn.execute(
        "SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id "
        "WHERE ur.user_id=%s AND r.name='assign_test_role'", (user[0],)
    )
    row = await cur2.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_assign_nonexistent_role_raises(conn, admin):
    await conn.execute("INSERT INTO users (username) VALUES ('admin_test_user2') ON CONFLICT DO NOTHING")
    cur = await conn.execute("SELECT id FROM users WHERE username='admin_test_user2'")
    user = await cur.fetchone()
    with pytest.raises(NotFoundError):
        await admin.assign_role(conn, user_id=user[0], role="nonexistent_role")
