# src/vecgate/acl/resolver.py
from __future__ import annotations
import psycopg
from vecgate.core.models import UserContext


async def resolve_user_context(conn: psycopg.AsyncConnection, user_id: int) -> UserContext:
    """Resolve a user's authorized facet_ids and group_ids in two queries.

    Always returns lists (never None). Empty list = no access / no groups.
    """
    cur = await conn.execute(
        """
        SELECT DISTINCT rf.facet_id
        FROM user_roles ur
        JOIN role_facets rf ON rf.role_id = ur.role_id
        WHERE ur.user_id = %s
        """,
        (user_id,),
    )
    facet_rows = await cur.fetchall()
    facet_ids: list[int] = [row[0] for row in facet_rows]

    cur = await conn.execute(
        "SELECT group_id::text FROM user_groups WHERE user_id = %s",
        (user_id,),
    )
    group_rows = await cur.fetchall()
    group_ids: list[str] = [row[0] for row in group_rows]

    return UserContext(user_id=user_id, facet_ids=facet_ids, group_ids=group_ids)
