# vecgate/tests/conftest.py
"""
Shared fixtures. Requires a real PostgreSQL + pgvector instance.
Set TEST_DATABASE_URL env var before running:
  export TEST_DATABASE_URL=postgresql://vecgate_admin:pass@localhost/vecgate_test
"""
import os
import pytest
import psycopg
from pathlib import Path

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/vecgate_test",
)

SQL_DIR = Path(__file__).parent.parent / "sql"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create schema once per test session."""
    with psycopg.connect(TEST_DB_URL) as conn:
        conn.autocommit = True
        for sql_file in ["001_schema.sql", "002_indexes.sql"]:
            conn.execute((SQL_DIR / sql_file).read_text())
    yield
    # Teardown: drop all data but keep schema for speed
    with psycopg.connect(TEST_DB_URL) as conn:
        conn.autocommit = True
        conn.execute("""
            TRUNCATE audit_log, chunk_acl_groups, user_groups, chunks,
                     documents, role_facets, user_roles, facets, roles,
                     users, groups RESTART IDENTITY CASCADE
        """)


@pytest.fixture
def db_url() -> str:
    return TEST_DB_URL
