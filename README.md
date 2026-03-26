# VecGate

ACL-controlled vector search for pgvector. Two-layer RBAC in one SQL query.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

## Overview

VecGate adds enterprise-grade access control to PostgreSQL + pgvector:

- **Facet-level RBAC** — users only query datasets (facets) their roles permit
- **Chunk-level group ACL** — individual chunks further restricted to named groups
- **Two-layer enforcement** — both checks happen inside a single SQL query
- **Per-facet HNSW indexes** — partial indexes ensure the vector search hits only authorized data
- **Three surfaces** — Python SDK, CLI, and HTTP service share the same core

## Install

```bash
pip install vecgate          # SDK only
pip install vecgate[cli]     # + CLI tools
pip install vecgate[service] # + HTTP service
pip install vecgate[all]     # everything
```

## Quick Start

> **Note:** The SDK entry points (`VecGate`, `AsyncVecGate`) are available once the package is fully installed.

### SDK

```python
from vecgate import VecGate

vg = VecGate(db_url="postgresql://vecgate_admin:pass@localhost/vecgate")
vg.init()  # bootstrap schema (idempotent)

# Setup
vg.create_facet("sales_data")
vg.create_role("sales_team", facets=["sales_data"])
vg.assign_role(user_id=1, role="sales_team")

# Ingest
from vecgate.core.models import ChunkIn
vg.ingest(
    document_id="550e8400-e29b-41d4-a716-446655440000",
    facet="sales_data",
    chunks=[ChunkIn(content="Q3 revenue up 12%", embedding=[...], chunk_index=0)],
)

# Search (user sees only authorized facets)
results = vg.search(user_id=1, embedding=[...], top_k=10)
for r in results:
    print(r.content, r.distance)
```

### CLI

```bash
export VECGATE_DATABASE_URL=postgresql://vecgate_admin:pass@localhost/vecgate

vecgate init
vecgate facet create sales_data
vecgate role create sales_team --facets sales_data
vecgate status
```

### Docker

```bash
cd docker/
docker compose up
# VecGate service available at http://localhost:8000
curl http://localhost:8000/health
```

## SDK Reference

### `VecGate` / `AsyncVecGate`

| Method | Description |
|---|---|
| `init(enable_rls=None)` | Bootstrap schema. Idempotent. |
| `create_facet(name, description=None)` | Create a dataset facet. Returns facet_id. |
| `create_role(name, facets, description=None)` | Create role with facet permissions. |
| `assign_role(user_id, role)` | Assign role to user. |
| `create_group(name, description=None)` | Create a chunk-level ACL group. |
| `assign_group(user_id, group)` | Add user to group. |
| `ingest(document_id, facet, chunks)` | Ingest chunks with ACL. |
| `search(user_id, embedding=None, query_text=None, top_k=10)` | ACL-filtered search. |

## CLI Reference

```
vecgate init          Bootstrap schema
vecgate facet create  Create facet
vecgate facet list    List facets
vecgate role create   Create role
vecgate role assign   Assign role to user
vecgate group create  Create group
vecgate group assign  Assign group to user
vecgate status        Show DB status
vecgate serve         Start HTTP service
```

## HTTP API

All endpoints require `X-User-Id: <int>` header (dev mode). Replace with real auth middleware in production.

| Method | Path | Description |
|---|---|---|
| GET | /health | Health check |
| POST | /search | Vector search |
| POST | /ingest | Ingest chunks |
| GET | /admin/facets | List facets |
| POST | /admin/facets | Create facet |
| GET | /admin/roles | List roles |
| POST | /admin/roles | Create role |
| POST | /admin/roles/{id}/assign-user | Assign user to role |
| GET | /admin/groups | List groups |
| POST | /admin/groups | Create group |
| POST | /admin/groups/{id}/assign-user | Assign user to group |

## Configuration

All settings are environment variables with `VECGATE_` prefix:

| Variable | Default | Description |
|---|---|---|
| `VECGATE_DATABASE_URL` | (required) | PostgreSQL connection string |
| `VECGATE_ADMIN_DATABASE_URL` | (same as above) | Admin connection for schema init |
| `VECGATE_EMBEDDING_DIMENSIONS` | 1536 | Vector dimensions |
| `VECGATE_MAX_TOP_K` | 100 | Maximum results per search |
| `VECGATE_ENABLE_RLS` | false | Enable PostgreSQL RLS backstop |
| `VECGATE_HNSW_M` | 16 | HNSW index M parameter |
| `VECGATE_HNSW_EF_CONSTRUCTION` | 200 | HNSW ef_construction parameter |

## Architecture

```
User request → Facet ACL (RBAC) → Chunk ACL (group) → vector search
               └── role_facets     └── chunk_acl_groups
```

Two-layer enforcement in one SQL query per authorized facet:
1. `WHERE facet_id = %s` — uses partial HNSW index
2. `NOT EXISTS (chunk_acl_groups)` OR `EXISTS (matching group)` — chunk-level filter

## Contributing

1. Fork the repo
2. Create a feature branch
3. Run tests: `pytest tests/ -v`
4. Submit a PR

Tests require PostgreSQL + pgvector. Set `TEST_DATABASE_URL` before running.

## License

MIT
