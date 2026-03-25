# KT (Knowledge Transfer)

## 1) Objective We Implemented

We built a production-oriented backend for **ACL-aware semantic retrieval** where:

- Data is stored in PostgreSQL using `pgvector`.
- Users belong to one or more groups.
- Chunks are granted to one or more groups.
- Search enforces **tenant isolation + ACL authorization in the same SQL query**.
- Unauthorized chunks are never returned and never post-filtered from broader vector results.

## 2) What Has Been Done So Far

### A. Data Model + SQL Layer

- Designed and implemented tenant-aware schema for:
  - tenants
  - users
  - groups
  - user_groups
  - documents
  - document_chunks (with `vector(1536)` embedding)
  - chunk_acl_groups
- Added `pgvector` extension setup.
- Added schema constraints and tenant-scoped foreign keys to prevent cross-tenant joins.
- Added vector and relational indexes for query performance.
- Added example SQL for insert, ACL assignment, and group resolution.
- Added canonical secure semantic search SQL in `sql/secure_search.sql`.
- Added optional RLS hardening sketch for future defense-in-depth.

### B. Backend Service (Python)

- Implemented FastAPI app with modular layers:
  - API layer
  - service layer
  - repository/data-access layer
  - auth context adapter
  - embedding provider abstraction
- Implemented required functions/methods:
  - `getUserContext(userId, tenantId)`
  - `ingestChunk(...)`
  - `assignChunkAcl(...)`
  - `replaceUserGroups(...)`
  - `replaceChunkAclGroups(...)`
  - `searchAuthorizedChunks(...)`
- Added an **atomic ingestion flow** (`ingestChunkWithAcl`) to avoid partial writes.
- Added strong validation for input shapes, dimensions, and numeric embedding quality.
- Enforced parameterized SQL only.

### C. API Surface

Implemented endpoints:

- `POST /ingest`
  - Inserts chunk embedding and assigns ACL groups in one transaction.
- `POST /search`
  - Accepts `query_embedding` or `query_text` (embedding generation stubbed).
  - Uses authenticated identity for scope.
  - Rejects payload/user mismatch if `user_id` is supplied and differs from auth user.
- `PUT /users/{user_id}/groups`
  - Replaces all group memberships for a user in the authenticated tenant.
  - Validates all target groups belong to the same tenant.
  - Supports empty list to remove all memberships.
- `PUT /chunks/{chunk_id}/acl-groups`
  - Replaces all ACL groups for a chunk in the authenticated tenant.
  - Validates chunk ownership + tenant-local group IDs.
  - Supports empty list to revoke all ACL grants.

### D. Security Controls Implemented

- Authorization and similarity are combined in one SQL statement.
- Tenant filtering is present on all critical paths.
- No trust in client-submitted tenant/user authorization scope.
- Pydantic models use `extra="forbid"` to block undeclared fields (e.g. arbitrary `chunk_ids` bypass attempts).
- SQL injection risk reduced using bound parameters (`%s`) in psycopg.

### E. Tests Added

Integration-style tests cover:

- User in one group.
- User in multiple groups.
- Chunk visible to multiple groups.
- Tenant isolation.
- User with no access.
- Attempted bypass with arbitrary chunk IDs.
- User-group replacement changes search visibility.
- Chunk ACL replacement changes search visibility.

Tests are designed to run with `TEST_DATABASE_URL` and skip safely if dependencies/DB are unavailable.

## 3) High-Level Runtime Flow

### Ingest Flow

1. API receives authenticated tenant/user context.
2. Validate request payload.
3. Insert chunk into tenant document.
4. Validate ACL groups belong to the same tenant.
5. Assign ACL grants to chunk.
6. Commit transaction.

### Search Flow

1. API receives authenticated tenant/user context.
2. Validate payload (`query_text` XOR `query_embedding`, bounded `top_k`).
3. Resolve embedding (direct or provider).
4. Service resolves user context (`group_ids`) once and fast-fails if invalid/inactive.
5. Repository executes secure SQL that:
   - filters by `tenant_id`
   - applies ACL authorization using `WHERE EXISTS` on `chunk_acl_groups` with `group_ids`
   - ranks only authorized chunks by vector distance
6. Return only authorized top-k results.

## 4) Security Design Rationale

Core non-negotiable rule implemented:

- **Never retrieve unauthorized vector candidates then filter in app code.**

How implemented:

- The authenticated user's `group_ids` are resolved into the `UserContext` at the service boundary.
- The `group_ids` are injected safely into a single parameterized `WHERE EXISTS` subquery against `chunk_acl_groups` in the main SQL.
- The ranked set dynamically restricts candidates via pgvector index pre-filtering before ordering/limit.
- Tenant checks exist in both the requester context validation and the `document_chunks` table lookup.

Why this matters:

- Prevents accidental leakage through logs, metrics, temporary caches, or bugs in post-filter logic.
- Keeps policy enforcement centralized in one query path.

## 5) Performance Decisions and Tradeoffs

### Vector Index

Default: HNSW (`vector_cosine_ops`)

- Pros: strong query-time speed/recall for read-heavy workloads.
- Cons: higher memory footprint and longer build/update cost.

Optional: IVFFlat

- Pros: lighter index build/memory.
- Cons: requires `ANALYZE` and probe tuning; recall more sensitive.

### ACL Join Cost

ACL joins can dominate at scale. Current mitigations:

- Pre-resolving the `group_ids` in the Application layer to avoid joining `app_users` and `user_groups` during the vector execution.
- Utilizing `WHERE EXISTS` to ensure `pgvector` can perform dynamic index pre-filtering (crucial for HNSW).
- Chunk tenant indexes for fast ownership lookup.

Future scaling options:

- Partition large tables by `tenant_id`.
- Precompute/materialize effective permissions for very large stable memberships.
- Two-phase candidate limiting strategy if needed (carefully preserving security semantics).

## 6) File-by-File Explanation

### Root Files

- `README.md`
  - Quick onboarding and run instructions.
  - Short architecture guarantees and directory overview.
- `KT.md`
  - This detailed transfer document.
- `.env.example`
  - Example runtime configuration values.
- `pyproject.toml`
  - Project metadata, dependencies, packaging, and pytest config.
- `docs/ER_DIAGRAM.md`
  - Mermaid ER diagram for schema relationships and tenant-isolation constraints.

### SQL Files (`/sql`)

- `sql/001_schema.sql`
  - Full schema DDL.
  - Includes extension setup (`pgcrypto`, `vector`).
  - Defines all core tables and constraints.
- `sql/002_indexes.sql`
  - Relational indexes for tenant and ACL joins.
  - HNSW vector index and optional IVFFlat alternative.
- `sql/003_examples.sql`
  - Parameterized SQL examples for:
    - chunk insert
    - ACL grant assignment
    - user effective group resolution
- `sql/secure_search.sql`
  - Canonical secure vector query enforcing requester + tenant + ACL in one statement.
- `sql/004_rls_future.sql`
  - Optional future RLS concept (not primary enforcement path).

### Python Package (`/src/acl_search`)

- `src/acl_search/__init__.py`
  - Exposes `create_app` for package-level use.
- `src/acl_search/main.py`
  - ASGI app entrypoint for Uvicorn.
- `src/acl_search/api/app.py`
  - FastAPI app assembly, dependency wiring, and endpoint definitions.
- `src/acl_search/service/search_service.py`
  - Transaction boundaries and business orchestration.
  - Implements required methods, top-k policy checks, and tenant-scoped ACL update flows.
- `src/acl_search/repository/search_repository.py`
  - All SQL operations:
    - user context resolution
    - chunk insert
    - ACL assignment
    - user-group replacement (full set)
    - chunk ACL-group replacement (full set)
    - secure authorized vector search
  - Embedding dimension/finite-number validation and vector literal conversion.
- `src/acl_search/auth/dependencies.py`
  - Auth context adapter.
  - Reads identity from middleware state or dev headers.
- `src/acl_search/embeddings/provider.py`
  - Embedding provider abstraction + stub implementation.
- `src/acl_search/core/config.py`
  - Settings via environment variables (`pydantic-settings`).
- `src/acl_search/core/db.py`
  - psycopg connection pool lifecycle (`init_pool`, `close_pool`, connection helper).
- `src/acl_search/core/errors.py`
  - Domain-specific exceptions (`NotFoundError`, `AuthorizationError`, `ValidationError`).
- `src/acl_search/core/schemas.py`
  - Pydantic request/response/domain models with strict validation.
  - Includes update-contract models for user-group and chunk-ACL replacement endpoints.
- `src/acl_search/config.py`, `src/acl_search/db.py`, `src/acl_search/errors.py`, `src/acl_search/schemas.py`
  - Backward-compatible re-export shims for older import paths.

### Tests (`/tests`)

- `tests/test_acl_search_service.py`
  - Integration-style scenario tests for ACL and tenant behavior.
  - Seeds test data and validates expected authorization outcomes, including update flows.

## 7) Key Query (Security-Critical)

The secure query is in `sql/secure_search.sql` and mirrored in repository constants.

Security properties:

- The Python service layer asserts an active requester has valid groups before running the vector query.
- The SQL strictly filters by `tenant_id` at the root query block.
- An inline `EXISTS` subquery dynamically tests chunk permissions against the `group_ids` during pgvector index scanning.
- Order by vector distance is evaluated exactly alongside the ACL checks (dynamic pre-filtering).

## 8) Operational Notes

- Required DB extension: `pgvector`.
- Ensure embeddings sent to ingest/search match configured dimensions.
- Connect real auth middleware and populate `request.state.auth_context` in production.
- Add RBAC/role checks before exposing user-group or chunk-ACL update endpoints publicly.
- If `query_text` is used, inject concrete embedding provider implementation.

## 9) Current Verification Status

- Python syntax compilation succeeded.
- Pytest is configured; integration tests require environment dependencies and test DB (`TEST_DATABASE_URL`).

## 10) Suggested Next Steps

- Wire real auth provider (JWT/OIDC middleware).
- Add migration tooling (e.g., Alembic) and migration pipeline.
- Add observability:
  - structured request logs (without sensitive payloads)
  - Add load testing and index tuning for target tenant/data scale.

## 11) UI + End-to-End Implementation (This Branch)

### What was added

- Built-in frontend served by FastAPI from `src/acl_search/ui/`.
- Root route now redirects to `/ui/index.html`.
- Added `GET /health` for runtime readiness checks.
- Added deterministic browser-side embedding generation in the UI for immediate ingest/search demos.
- Added deterministic server-side embedding provider (`DeterministicDemoEmbeddingProvider`) behind config flag.
- Added DB bootstrap and demo seeding scripts:
  - `scripts/init_db.py`
  - `scripts/seed_demo.py`
- Added containerized dev stack:
  - `Dockerfile`
  - `docker-compose.yml`

### Why deterministic embeddings were introduced

For true end-to-end local demos, users need to ingest and search without integrating an external embedding model first. Deterministic embeddings provide:

- stable vectors across runs
- consistent search behavior for demos/tests
- no external API dependency

This is controlled by `ACL_SEARCH_ENABLE_DEMO_EMBEDDINGS` and remains optional.

### UI responsibilities

The console supports:

- identity context editing (tenant/user IDs for auth headers)
- chunk ingest with ACL group assignment
- secure semantic search execution
- user group replacement (`PUT /users/{user_id}/groups`)
- chunk ACL replacement (`PUT /chunks/{chunk_id}/acl-groups`)
- result rendering and event logs

### End-to-end run flow

1. Start DB/API (local Python or Docker).
2. Apply schema/index scripts.
3. Seed demo tenant/users/groups/document/chunks.
4. Open UI at `/`.
5. Run ingest + search + ACL updates and validate behavior live.
