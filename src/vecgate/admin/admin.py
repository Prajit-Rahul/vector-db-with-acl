# src/vecgate/admin/admin.py
from __future__ import annotations
import psycopg
from vecgate.acl.facet import create_facet_with_index
from vecgate.core.config import Settings
from vecgate.core.errors import NotFoundError


class AdminClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def create_facet(self, conn: psycopg.AsyncConnection,
                            name: str, description: str | None = None) -> int:
        return await create_facet_with_index(conn, name, description, self._settings)

    async def list_facets(self, conn: psycopg.AsyncConnection) -> list[dict]:
        cur = await conn.execute("SELECT id, name, description, created_at FROM facets ORDER BY name")
        rows = await cur.fetchall()
        return [dict(zip(("id", "name", "description", "created_at"), r)) for r in rows]

    async def create_role(self, conn: psycopg.AsyncConnection,
                          name: str, facets: list[str],
                          description: str | None = None) -> int:
        cur = await conn.execute(
            "INSERT INTO roles (name, description) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description RETURNING id",
            (name, description),
        )
        row = await cur.fetchone()
        role_id: int = row[0]
        for facet_name in facets:
            cur2 = await conn.execute("SELECT id FROM facets WHERE name = %s", (facet_name,))
            f = await cur2.fetchone()
            if f is None:
                raise NotFoundError(f"Facet '{facet_name}' not found")
            await conn.execute(
                "INSERT INTO role_facets (role_id, facet_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (role_id, f[0]),
            )
        return role_id

    async def list_roles(self, conn: psycopg.AsyncConnection) -> list[dict]:
        cur = await conn.execute("SELECT id, name, description FROM roles ORDER BY name")
        rows = await cur.fetchall()
        return [dict(zip(("id", "name", "description"), r)) for r in rows]

    async def assign_role(self, conn: psycopg.AsyncConnection,
                          user_id: int, role: str) -> None:
        cur = await conn.execute("SELECT id FROM roles WHERE name = %s", (role,))
        row = await cur.fetchone()
        if row is None:
            raise NotFoundError(f"Role '{role}' not found")
        await conn.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, row[0]),
        )

    async def create_group(self, conn: psycopg.AsyncConnection,
                           name: str, description: str | None = None) -> str:
        cur = await conn.execute(
            "INSERT INTO groups (name, description) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description RETURNING id::text",
            (name, description),
        )
        row = await cur.fetchone()
        return row[0]

    async def list_groups(self, conn: psycopg.AsyncConnection) -> list[dict]:
        cur = await conn.execute("SELECT id::text, name, description FROM groups ORDER BY name")
        rows = await cur.fetchall()
        return [dict(zip(("id", "name", "description"), r)) for r in rows]

    async def assign_group(self, conn: psycopg.AsyncConnection,
                           user_id: int, group: str) -> None:
        cur = await conn.execute("SELECT id FROM groups WHERE name = %s", (group,))
        row = await cur.fetchone()
        if row is None:
            raise NotFoundError(f"Group '{group}' not found")
        await conn.execute(
            "INSERT INTO user_groups (user_id, group_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, row[0]),
        )
