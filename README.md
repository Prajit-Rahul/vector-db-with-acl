# ACL-Aware Semantic Search Backend

Production-grade Python backend for tenant-isolated, ACL-aware semantic search on PostgreSQL + pgvector.

## Overview

This service ensures users can only semantic-search chunks they are authorized to access.
Authorization is enforced inside the SQL search query, not as post-filtering in application code.

## Core Keywords

`Python` `FastAPI` `PostgreSQL` `pgvector` `Vector Database` `Semantic Search` `ACL` `RBAC`
`Multi-Tenant Architecture` `Secure Backend` `SQL Optimization` `HNSW` `REST API`
`Pydantic v2` `psycopg3` `Transaction Safety` `Production-Grade API`

## Impact Highlights

- Built a tenant-isolated, ACL-aware semantic search backend for secure retrieval at scale.
- Enforced authorization directly in SQL query execution to prevent data leakage paths.
- Improved query efficiency with tenant pre-filtering + ACL `EXISTS` checks for ANN compatibility.
- Added strict schema validation, parameterized SQL, and integration-style security tests.

## Recent Architecture Update

Search authorization was optimized to use tenant pre-filtering plus `WHERE EXISTS` ACL checks against `chunk_acl_groups`.

Current secure search pattern:
- Resolve requester groups once in service (`getUserContext`).
- Pass `group_ids` into repository as a bound SQL parameter.
- Execute vector ranking only on chunks where ACL `EXISTS` for at least one user group.

This avoids expensive CTE-heavy joins in the hot search path and improves compatibility with pgvector ANN index pre-filtering.

## Security Contract

- Authenticated identity is authoritative (middleware / trusted auth context).
- Request body `user_id` is only a consistency check, not a source of truth.
- Tenant isolation is always enforced in SQL predicates.
- ACL checks are evaluated in the same SQL statement as vector similarity.
- All SQL is parameterized (`psycopg` bound parameters), avoiding SQL injection by dynamic concatenation.
- Pydantic schemas use strict validation (`extra="forbid"`) to reject undeclared/bypass fields.

## Tech Stack

- Python 3.11+
- FastAPI
- psycopg3 + psycopg_pool
- PostgreSQL + pgvector
- Pydantic v2

## Project Structure

- `sql/001_schema.sql`: full schema + pgvector extension setup.
- `sql/002_indexes.sql`: tenant/ACL/vector indexing strategy.
- `sql/003_examples.sql`: parameterized SQL examples.
- `sql/secure_search.sql`: canonical secure search SQL.
- `sql/004_rls_future.sql`: optional future RLS defense-in-depth sketch.
- `src/acl_search/api/`: FastAPI app composition and route handlers.
- `src/acl_search/service/`: business orchestration and transaction boundaries.
- `src/acl_search/repository/`: SQL/data-access layer.
- `src/acl_search/auth/`: auth context adapter/dependencies.
- `src/acl_search/embeddings/`: embedding provider abstraction + implementations.
- `src/acl_search/core/`: shared config, DB lifecycle, errors, schemas.
- `src/acl_search/main.py`: ASGI entrypoint.
- `src/acl_search/config.py`, `db.py`, `errors.py`, `schemas.py`: backward-compatible re-export shims.
- `tests/test_acl_search_service.py`: integration-style ACL + tenant tests.
- `KT.md`: detailed knowledge transfer and full design rationale.

## Prerequisites

- PostgreSQL with `pgvector` available.
- Python 3.11+.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Database Bootstrap

Run schema and indexes in order:

```bash
psql "$ACL_SEARCH_DATABASE_URL" -f sql/001_schema.sql
psql "$ACL_SEARCH_DATABASE_URL" -f sql/002_indexes.sql
```

## Run the API

```bash
uvicorn acl_search.main:app --reload
```

## Environment Variables

| Variable | Required | Default | What it means | DB impact |
| --- | --- | --- | --- | --- |
| `ACL_SEARCH_DATABASE_URL` | Yes | `postgresql://postgres:postgres@localhost:5432/acl_search` | Connection string used by the app to reach PostgreSQL. | Points the app to the target DB server, database name, user, and password. |
| `ACL_SEARCH_EMBEDDING_DIMENSIONS` | No | `1536` | Expected vector length for ingest/search embeddings. | Must match the schema vector size (`document_chunks.embedding VECTOR(1536)`) unless you update schema + app together. |
| `ACL_SEARCH_MAX_TOP_K` | No | `100` | Maximum allowed `top_k` per search request. | Limits result set size and protects DB from very heavy queries. |
| `ACL_SEARCH_DB_POOL_MIN_SIZE` | No | `2` | Minimum open connections kept in the connection pool. | Keeps a baseline number of active DB connections ready. |
| `ACL_SEARCH_DB_POOL_MAX_SIZE` | No | `20` | Maximum connections pool can open. | Upper cap on concurrent DB connections from this service instance. |
| `ACL_SEARCH_DB_POOL_MAX_IDLE_SECONDS` | No | `60` | Idle timeout for pooled connections. | Closes unused DB connections after this period to reduce resource usage. |

A sample file is provided at `.env.example`.

## API

Auth scope is expected from middleware. For local/dev you can pass:
- `x-authenticated-user-id`
- `x-authenticated-tenant-id`

### API Parameter Reference

All IDs are UUID strings unless noted otherwise.

Common headers:

| Header | Required | Description |
| --- | --- | --- |
| `content-type: application/json` | Yes | Request body is JSON. |
| `x-authenticated-user-id` | Yes (dev mode) | Authenticated user identity. |
| `x-authenticated-tenant-id` | Yes (dev mode) | Authenticated tenant scope. |

Notes:
- In production, auth middleware should set `request.state.auth_context` instead of using dev headers.
- API does not trust request body for authorization scope.
- Role-based admin authorization for management endpoints is not implemented yet; add RBAC before exposing publicly.

### POST /ingest

Example:

```bash
curl -X POST http://localhost:8000/ingest \
  -H 'content-type: application/json' \
  -H 'x-authenticated-user-id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' \
  -H 'x-authenticated-tenant-id: 11111111-1111-1111-1111-111111111111' \
  -d '{
    "document_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1",
    "chunk_index": 0,
    "content": "Quarterly revenue increased 18%.",
    "embedding": [0.1, 0.2, 0.3],
    "token_count": 6,
    "metadata": {"source": "q4-report"},
    "acl_group_ids": ["cccccccc-cccc-cccc-cccc-ccccccccccc1"]
  }'
```

Note: example embedding is shortened for readability; production length must equal `ACL_SEARCH_EMBEDDING_DIMENSIONS`.

Request body parameters:

| Field | Type | Required | Validation / meaning |
| --- | --- | --- | --- |
| `document_id` | UUID | Yes | Document that owns the chunk. Must exist in same tenant. |
| `chunk_index` | integer | Yes | `>= 0`; order of chunk within document. |
| `content` | string | Yes | Length `1..100000`; raw chunk text. |
| `embedding` | array of numbers | Yes | Length must equal `ACL_SEARCH_EMBEDDING_DIMENSIONS`; all values must be finite numbers. |
| `token_count` | integer or null | No | `>= 0`; optional token count metadata. |
| `metadata` | object | No | Extra JSON metadata (default `{}`). |
| `acl_group_ids` | array of UUID | Yes | At least one group; each group must exist in same tenant. |

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `chunk_id` | integer | New DB chunk primary key. |
| `assigned_group_ids` | array of UUID | ACL groups assigned to this chunk. |

### POST /search

Example (`query_embedding`):

```bash
curl -X POST http://localhost:8000/search \
  -H 'content-type: application/json' \
  -H 'x-authenticated-user-id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' \
  -H 'x-authenticated-tenant-id: 11111111-1111-1111-1111-111111111111' \
  -d '{
    "query_embedding": [0.1, 0.2, 0.3],
    "top_k": 5
  }'
```

Example (`query_text`):

```bash
curl -X POST http://localhost:8000/search \
  -H 'content-type: application/json' \
  -H 'x-authenticated-user-id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' \
  -H 'x-authenticated-tenant-id: 11111111-1111-1111-1111-111111111111' \
  -d '{
    "query_text": "quarterly growth",
    "top_k": 5
  }'
```

Current behavior: `query_text` requires a real embedding provider to be injected; default stub returns `501 Not Implemented`.

Request body parameters:

| Field | Type | Required | Validation / meaning |
| --- | --- | --- | --- |
| `user_id` | UUID or null | No | Optional consistency check only. If present and mismatched with auth user, request is rejected (`403`). |
| `query_text` | string or null | Exactly one of `query_text` or `query_embedding` | Length `1..10000`; converted to embedding using provider. |
| `query_embedding` | array of numbers or null | Exactly one of `query_text` or `query_embedding` | Used directly for vector search. |
| `top_k` | integer | No | Default `10`; allowed range `1..100` and also capped by `ACL_SEARCH_MAX_TOP_K`. |

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `user_id` | UUID | Authenticated user used for search. |
| `tenant_id` | UUID | Authenticated tenant used for search. |
| `top_k` | integer | Requested/accepted limit. |
| `results` | array | Authorized similar chunks only. |

Each item in `results`:

| Field | Type | Description |
| --- | --- | --- |
| `chunk_id` | integer | Chunk primary key. |
| `document_id` | UUID | Parent document ID. |
| `chunk_index` | integer | Chunk position in document. |
| `content` | string | Chunk text content. |
| `metadata` | object | Stored JSON metadata. |
| `similarity` | float | Similarity score derived from cosine distance. |

### PUT /users/{user_id}/groups

Replace all group memberships for a user in the authenticated tenant.

Example:

```bash
curl -X PUT http://localhost:8000/users/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1/groups \
  -H 'content-type: application/json' \
  -H 'x-authenticated-user-id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2' \
  -H 'x-authenticated-tenant-id: 11111111-1111-1111-1111-111111111111' \
  -d '{
    "group_ids": [
      "cccccccc-cccc-cccc-cccc-ccccccccccc1",
      "cccccccc-cccc-cccc-cccc-ccccccccccc2"
    ]
  }'
```

Request body parameters:

| Field | Type | Required | Validation / meaning |
| --- | --- | --- | --- |
| `group_ids` | array of UUID | No | Full replacement list for user memberships. Empty array is allowed and removes all memberships. |

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `user_id` | UUID | User whose memberships were updated. |
| `tenant_id` | UUID | Tenant scope used for the update. |
| `group_ids` | array of UUID | Final assigned group IDs. |

### PUT /chunks/{chunk_id}/acl-groups

Replace all ACL group grants for one chunk in the authenticated tenant.

Example:

```bash
curl -X PUT http://localhost:8000/chunks/101/acl-groups \
  -H 'content-type: application/json' \
  -H 'x-authenticated-user-id: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2' \
  -H 'x-authenticated-tenant-id: 11111111-1111-1111-1111-111111111111' \
  -d '{
    "group_ids": [
      "cccccccc-cccc-cccc-cccc-ccccccccccc2"
    ]
  }'
```

Request body parameters:

| Field | Type | Required | Validation / meaning |
| --- | --- | --- | --- |
| `group_ids` | array of UUID | No | Full replacement list for chunk ACL groups. Empty array is allowed and removes all ACL grants for the chunk. |

Response fields:

| Field | Type | Description |
| --- | --- | --- |
| `chunk_id` | integer | Chunk whose ACL groups were updated. |
| `tenant_id` | UUID | Tenant scope used for the update. |
| `assigned_group_ids` | array of UUID | Final ACL groups assigned to the chunk. |

## Testing

Run:

```bash
pytest -q
```

For integration tests, set:

- `TEST_DATABASE_URL`

If required test dependencies or DB are missing, tests are skipped by design.

## Performance Notes

- Default ANN index in this project is HNSW (`vector_cosine_ops`).
- Optional IVFFlat is documented in `sql/002_indexes.sql`.
- ACL joins are optimized with tenant + group composite indexes.
- For very large datasets, consider tenant partitioning and materialized permission maps.

## Further Reading

For full implementation transfer and file-by-file responsibilities, see `KT.md`.
