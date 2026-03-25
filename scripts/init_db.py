"""Initialize database schema/indexes for local UI + E2E runs.

Usage:
  ACL_SEARCH_DATABASE_URL=postgresql://... python scripts/init_db.py
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SQL_FILES = [
    ROOT / "sql" / "001_schema.sql",
    ROOT / "sql" / "002_indexes.sql",
]


def main() -> None:
    db_url = os.getenv("ACL_SEARCH_DATABASE_URL")
    if not db_url:
        raise SystemExit("ACL_SEARCH_DATABASE_URL is required")

    with psycopg.connect(db_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for sql_path in SQL_FILES:
                print(f"Applying {sql_path.name} ...")
                cur.execute(sql_path.read_text(encoding="utf-8"))

    print("Database initialization complete.")


if __name__ == "__main__":
    main()
