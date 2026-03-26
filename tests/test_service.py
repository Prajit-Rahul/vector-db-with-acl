# vecgate/tests/test_service.py
import pytest
from httpx import AsyncClient, ASGITransport
from vecgate.service.app import create_app
from vecgate.core.config import Settings
import os

DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost/vecgate_test")


@pytest.fixture
def app():
    return create_app(settings=Settings(database_url=DB_URL))


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    resp = await client.post("/search", json={"user_id": 1, "embedding": [0.1]*1536})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_with_valid_user(client):
    import psycopg
    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        await conn.execute("INSERT INTO users (username) VALUES ('svc_test_user') ON CONFLICT DO NOTHING")
        cur = await conn.execute("SELECT id FROM users WHERE username='svc_test_user'")
        row = await cur.fetchone()
        user_id = row[0]

    resp = await client.post(
        "/search",
        json={"user_id": user_id, "embedding": [0.1]*1536, "top_k": 5},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 200
    assert "results" in resp.json()


@pytest.mark.asyncio
async def test_create_facet_via_api(client):
    import psycopg
    async with await psycopg.AsyncConnection.connect(DB_URL) as conn:
        await conn.execute("INSERT INTO users (username) VALUES ('admin_svc') ON CONFLICT DO NOTHING")
        cur = await conn.execute("SELECT id FROM users WHERE username='admin_svc'")
        row = await cur.fetchone()
        user_id = row[0]

    resp = await client.post(
        "/admin/facets",
        json={"name": "svc_test_facet"},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "svc_test_facet"
