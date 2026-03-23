from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest

pytest.importorskip("pydantic")
from pydantic import ValidationError as PydanticValidationError
psycopg = pytest.importorskip("psycopg")
from acl_search.repository import AclSearchRepository
from acl_search.schemas import SearchRequest

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "001_schema.sql"
INDEX_SQL = Path(__file__).resolve().parents[1] / "sql" / "002_indexes.sql"

TENANT_1 = UUID("11111111-1111-1111-1111-111111111111")
TENANT_2 = UUID("22222222-2222-2222-2222-222222222222")

USER_ONE_GROUP = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
USER_MULTI_GROUP = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
USER_NO_ACCESS = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
USER_TENANT_2 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1")

GROUP_A = UUID("cccccccc-cccc-cccc-cccc-ccccccccccc1")
GROUP_B = UUID("cccccccc-cccc-cccc-cccc-ccccccccccc2")
GROUP_TENANT_2 = UUID("dddddddd-dddd-dddd-dddd-ddddddddddd1")

DOC_TENANT_1 = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1")
DOC_TENANT_2 = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2")

CHUNK_1 = 101
CHUNK_2 = 102
CHUNK_3 = 103
CHUNK_4 = 201

EMBEDDING_DIMS = 1536


def _vector(seed: float) -> list[float]:
    # Keep vectors non-zero for cosine distance.
    vec = [0.001] * EMBEDDING_DIMS
    vec[0] = seed
    vec[1] = 1.0
    return vec


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(float(v), ".10g") for v in values) + "]"


def _test_db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run Postgres integration tests")
    return url


def _exec_sql_file(conn: psycopg.Connection, path: Path) -> None:
    conn.execute(path.read_text())


@pytest.fixture(scope="module")
def conn() -> psycopg.Connection:
    connection = psycopg.connect(_test_db_url())
    connection.autocommit = True

    try:
        _exec_sql_file(connection, SCHEMA_SQL)
        _exec_sql_file(connection, INDEX_SQL)
    except Exception as exc:  # pragma: no cover - env specific
        connection.close()
        pytest.skip(f"Unable to initialize pgvector schema for tests: {exc}")

    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def reset_and_seed(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        TRUNCATE TABLE
            chunk_acl_groups,
            document_chunks,
            documents,
            user_groups,
            groups,
            app_users,
            tenants
        RESTART IDENTITY CASCADE;
        """
    )

    conn.execute(
        "INSERT INTO tenants (tenant_id, name) VALUES (%s, %s), (%s, %s)",
        (TENANT_1, "Tenant One", TENANT_2, "Tenant Two"),
    )

    conn.execute(
        """
        INSERT INTO app_users (user_id, tenant_id, email, is_active)
        VALUES
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE)
        """,
        (
            USER_ONE_GROUP,
            TENANT_1,
            "u1@t1.test",
            USER_MULTI_GROUP,
            TENANT_1,
            "u2@t1.test",
            USER_NO_ACCESS,
            TENANT_1,
            "u3@t1.test",
            USER_TENANT_2,
            TENANT_2,
            "u4@t2.test",
        ),
    )

    conn.execute(
        """
        INSERT INTO groups (group_id, tenant_id, name)
        VALUES
            (%s, %s, %s),
            (%s, %s, %s),
            (%s, %s, %s)
        """,
        (
            GROUP_A,
            TENANT_1,
            "group-a",
            GROUP_B,
            TENANT_1,
            "group-b",
            GROUP_TENANT_2,
            TENANT_2,
            "group-x",
        ),
    )

    conn.execute(
        """
        INSERT INTO user_groups (tenant_id, user_id, group_id)
        VALUES
            (%s, %s, %s),
            (%s, %s, %s),
            (%s, %s, %s),
            (%s, %s, %s)
        """,
        (
            TENANT_1,
            USER_ONE_GROUP,
            GROUP_A,
            TENANT_1,
            USER_MULTI_GROUP,
            GROUP_A,
            TENANT_1,
            USER_MULTI_GROUP,
            GROUP_B,
            TENANT_2,
            USER_TENANT_2,
            GROUP_TENANT_2,
        ),
    )

    conn.execute(
        """
        INSERT INTO documents (document_id, tenant_id, title)
        VALUES
            (%s, %s, %s),
            (%s, %s, %s)
        """,
        (
            DOC_TENANT_1,
            TENANT_1,
            "Doc T1",
            DOC_TENANT_2,
            TENANT_2,
            "Doc T2",
        ),
    )

    conn.execute(
        """
        INSERT INTO document_chunks (
            chunk_id,
            tenant_id,
            document_id,
            chunk_index,
            content,
            embedding,
            metadata
        )
        OVERRIDING SYSTEM VALUE
        VALUES
            (%s, %s, %s, 0, %s, %s::vector, '{}'::jsonb),
            (%s, %s, %s, 1, %s, %s::vector, '{}'::jsonb),
            (%s, %s, %s, 2, %s, %s::vector, '{}'::jsonb),
            (%s, %s, %s, 0, %s, %s::vector, '{}'::jsonb)
        """,
        (
            CHUNK_1,
            TENANT_1,
            DOC_TENANT_1,
            "chunk one",
            _vector_literal(_vector(0.10)),
            CHUNK_2,
            TENANT_1,
            DOC_TENANT_1,
            "chunk two",
            _vector_literal(_vector(0.80)),
            CHUNK_3,
            TENANT_1,
            DOC_TENANT_1,
            "chunk three",
            _vector_literal(_vector(0.15)),
            CHUNK_4,
            TENANT_2,
            DOC_TENANT_2,
            "chunk four",
            _vector_literal(_vector(0.12)),
        ),
    )

    conn.execute(
        """
        INSERT INTO chunk_acl_groups (tenant_id, chunk_id, group_id, is_allowed)
        VALUES
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE),
            (%s, %s, %s, TRUE)
        """,
        (
            TENANT_1,
            CHUNK_1,
            GROUP_A,
            TENANT_1,
            CHUNK_2,
            GROUP_B,
            TENANT_1,
            CHUNK_3,
            GROUP_A,
            TENANT_1,
            CHUNK_3,
            GROUP_B,
            TENANT_2,
            CHUNK_4,
            GROUP_TENANT_2,
        ),
    )


def test_user_in_one_group(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)
    ctx = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_ONE_GROUP)
    results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx.group_ids,
        query_embedding=_vector(0.11),
        top_k=10,
    )

    assert {r.chunk_id for r in results} == {CHUNK_1, CHUNK_3}


def test_user_in_multiple_groups(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)
    ctx = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_MULTI_GROUP)
    results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx.group_ids,
        query_embedding=_vector(0.11),
        top_k=10,
    )

    assert {r.chunk_id for r in results} == {CHUNK_1, CHUNK_2, CHUNK_3}


def test_chunk_visible_to_multiple_groups(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)

    ctx1 = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_ONE_GROUP)
    u1_results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx1.group_ids,
        query_embedding=_vector(0.17),
        top_k=10,
    )

    ctx2 = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_MULTI_GROUP)
    u2_results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx2.group_ids,
        query_embedding=_vector(0.17),
        top_k=10,
    )

    assert CHUNK_3 in {r.chunk_id for r in u1_results}
    assert CHUNK_3 in {r.chunk_id for r in u2_results}


def test_tenant_isolation(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)

    ctx1 = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_MULTI_GROUP)
    tenant1_results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx1.group_ids,
        query_embedding=_vector(0.12),
        top_k=10,
    )
    assert CHUNK_4 not in {r.chunk_id for r in tenant1_results}

    ctx2 = repo.get_user_context(conn, tenant_id=TENANT_2, user_id=USER_TENANT_2)
    tenant2_results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_2,
        group_ids=ctx2.group_ids,
        query_embedding=_vector(0.12),
        top_k=10,
    )
    assert {r.chunk_id for r in tenant2_results} == {CHUNK_4}


def test_user_with_no_access(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)
    ctx = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_NO_ACCESS)
    results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=ctx.group_ids,
        query_embedding=_vector(0.12),
        top_k=10,
    )
    assert results == []


def test_replace_user_groups_updates_access(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)

    # Move user from group A only -> group B only.
    assigned = repo.replace_user_groups(
        conn,
        tenant_id=TENANT_1,
        user_id=USER_ONE_GROUP,
        group_ids=[GROUP_B],
    )
    conn.commit()
    assert assigned == [GROUP_B]

    updated_ctx = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_ONE_GROUP)
    results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=updated_ctx.group_ids,
        query_embedding=_vector(0.11),
        top_k=10,
    )

    assert {r.chunk_id for r in results} == {CHUNK_2, CHUNK_3}


def test_replace_chunk_acl_groups_updates_access(conn: psycopg.Connection) -> None:
    repo = AclSearchRepository(embedding_dimensions=EMBEDDING_DIMS)

    # Move chunk 1 visibility from group A -> group B.
    assigned = repo.replace_chunk_acl_groups(
        conn,
        tenant_id=TENANT_1,
        chunk_id=CHUNK_1,
        group_ids=[GROUP_B],
    )
    conn.commit()
    assert assigned == [GROUP_B]

    user_a_ctx = repo.get_user_context(conn, tenant_id=TENANT_1, user_id=USER_ONE_GROUP)
    user_a_results = repo.search_authorized_chunks(
        conn,
        tenant_id=TENANT_1,
        group_ids=user_a_ctx.group_ids,
        query_embedding=_vector(0.11),
        top_k=10,
    )

    assert CHUNK_1 not in {r.chunk_id for r in user_a_results}
    assert {r.chunk_id for r in user_a_results} == {CHUNK_3}


def test_attempted_bypass_with_arbitrary_chunk_ids_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        SearchRequest.model_validate(
            {
                "query_embedding": _vector(0.12),
                "top_k": 5,
                "chunk_ids": [CHUNK_4],
            }
        )
