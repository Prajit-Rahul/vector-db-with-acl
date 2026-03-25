"""Seed deterministic demo data for UI end-to-end flow.

Usage:
  ACL_SEARCH_DATABASE_URL=postgresql://... python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acl_search.embeddings import build_deterministic_embedding  # noqa: E402

EMBEDDING_DIMS = int(os.getenv("ACL_SEARCH_EMBEDDING_DIMENSIONS", "1536"))

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
PRIMARY_USER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
SECONDARY_USER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
GROUP_A = UUID("cccccccc-cccc-cccc-cccc-ccccccccccc1")
GROUP_B = UUID("cccccccc-cccc-cccc-cccc-ccccccccccc2")
DOCUMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1")

CHUNKS = [
    (0, "Q4 revenue grew 18 percent year over year in the enterprise segment."),
    (1, "Customer support backlog decreased by 27 percent after workflow automation."),
    (2, "Operating margin improved as onboarding costs dropped and retention increased."),
]


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(v, ".10g") for v in values) + "]"


def main() -> None:
    db_url = os.getenv("ACL_SEARCH_DATABASE_URL")
    if not db_url:
        raise SystemExit("ACL_SEARCH_DATABASE_URL is required")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (tenant_id, name, external_key)
                VALUES (%s, %s, %s)
                ON CONFLICT (tenant_id)
                DO UPDATE SET name = EXCLUDED.name, external_key = EXCLUDED.external_key
                """,
                (TENANT_ID, "Demo Tenant", "demo-tenant"),
            )

            cur.execute(
                """
                INSERT INTO app_users (user_id, tenant_id, email, display_name, is_active)
                VALUES
                    (%s, %s, %s, %s, TRUE),
                    (%s, %s, %s, %s, TRUE)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    is_active = EXCLUDED.is_active
                """,
                (
                    PRIMARY_USER_ID,
                    TENANT_ID,
                    "demo-user-a@example.com",
                    "Demo User A",
                    SECONDARY_USER_ID,
                    TENANT_ID,
                    "demo-user-b@example.com",
                    "Demo User B",
                ),
            )

            cur.execute(
                """
                INSERT INTO groups (group_id, tenant_id, name, description)
                VALUES
                    (%s, %s, %s, %s),
                    (%s, %s, %s, %s)
                ON CONFLICT (group_id)
                DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    name = EXCLUDED.name,
                    description = EXCLUDED.description
                """,
                (
                    GROUP_A,
                    TENANT_ID,
                    "finance",
                    "Finance team",
                    GROUP_B,
                    TENANT_ID,
                    "operations",
                    "Operations team",
                ),
            )

            cur.execute(
                "DELETE FROM user_groups WHERE tenant_id = %s AND user_id IN (%s, %s)",
                (TENANT_ID, PRIMARY_USER_ID, SECONDARY_USER_ID),
            )
            cur.execute(
                """
                INSERT INTO user_groups (tenant_id, user_id, group_id)
                VALUES
                    (%s, %s, %s),
                    (%s, %s, %s)
                """,
                (
                    TENANT_ID,
                    PRIMARY_USER_ID,
                    GROUP_A,
                    TENANT_ID,
                    SECONDARY_USER_ID,
                    GROUP_B,
                ),
            )

            cur.execute(
                """
                INSERT INTO documents (document_id, tenant_id, title, source_uri, metadata)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (document_id)
                DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    title = EXCLUDED.title,
                    source_uri = EXCLUDED.source_uri,
                    metadata = EXCLUDED.metadata
                """,
                (
                    DOCUMENT_ID,
                    TENANT_ID,
                    "Demo Knowledge Base",
                    "demo://knowledge-base",
                    '{"seed":"ui-e2e"}',
                ),
            )

            chunk_id_by_index: dict[int, int] = {}
            for chunk_index, text in CHUNKS:
                embedding = build_deterministic_embedding(text, EMBEDDING_DIMS)
                cur.execute(
                    """
                    INSERT INTO document_chunks (
                        tenant_id,
                        document_id,
                        chunk_index,
                        content,
                        embedding,
                        token_count,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s::vector, %s, %s::jsonb)
                    ON CONFLICT (tenant_id, document_id, chunk_index)
                    DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        token_count = EXCLUDED.token_count,
                        metadata = EXCLUDED.metadata
                    RETURNING chunk_id
                    """,
                    (
                        TENANT_ID,
                        DOCUMENT_ID,
                        chunk_index,
                        text,
                        vector_literal(embedding),
                        max(len(text.split()), 1),
                        '{"seed":"ui-e2e"}',
                    ),
                )
                row = cur.fetchone()
                assert row is not None
                chunk_id_by_index[chunk_index] = int(row[0])

            for chunk_id in chunk_id_by_index.values():
                cur.execute(
                    "DELETE FROM chunk_acl_groups WHERE tenant_id = %s AND chunk_id = %s",
                    (TENANT_ID, chunk_id),
                )

            cur.execute(
                """
                INSERT INTO chunk_acl_groups (tenant_id, chunk_id, group_id, is_allowed)
                VALUES
                    (%s, %s, %s, TRUE),
                    (%s, %s, %s, TRUE),
                    (%s, %s, %s, TRUE),
                    (%s, %s, %s, TRUE)
                """,
                (
                    TENANT_ID,
                    chunk_id_by_index[0],
                    GROUP_A,
                    TENANT_ID,
                    chunk_id_by_index[1],
                    GROUP_B,
                    TENANT_ID,
                    chunk_id_by_index[2],
                    GROUP_A,
                    TENANT_ID,
                    chunk_id_by_index[2],
                    GROUP_B,
                ),
            )

        conn.commit()

    print("Demo seed complete.")
    print(f"Tenant ID: {TENANT_ID}")
    print(f"Primary User ID (group finance): {PRIMARY_USER_ID}")
    print(f"Secondary User ID (group operations): {SECONDARY_USER_ID}")
    print(f"Group A (finance): {GROUP_A}")
    print(f"Group B (operations): {GROUP_B}")
    print(f"Document ID: {DOCUMENT_ID}")


if __name__ == "__main__":
    main()
