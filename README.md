# ACL-Aware Semantic Search (UI + End-to-End)

Production-ready backend for tenant-isolated, ACL-aware semantic retrieval on PostgreSQL + pgvector, now with a built-in web UI for end-to-end operation and verification.

## What You Get in This Branch

- Secure API with tenant + ACL enforcement in SQL (`WHERE EXISTS` pre-filter pattern).
- Built-in UI served by FastAPI at `/`.
- End-to-end demo scripts:
  - initialize schema/indexes
  - seed demo tenant/users/groups/document/chunks
- Docker-based local stack (`db` + `api`) for quick startup.

## Security Guarantees

- Authenticated identity is authoritative (`x-authenticated-user-id`, `x-authenticated-tenant-id` in dev).
- Payload user identity is not trusted for scope.
- Tenant isolation is enforced in every critical query path.
- ACL checks are in the same SQL statement as vector similarity search.
- All SQL uses bound parameters (no dynamic SQL concatenation).

## Architecture Notes

Search path uses:

- tenant predicate on `document_chunks`
- ACL authorization via `EXISTS` against `chunk_acl_groups`
- vector ranking only after authorization eligibility is satisfied

This keeps policy and retrieval in one query and avoids unauthorized candidate leakage.

## Prerequisites

- Python 3.11+ (`python3` command available)
- PostgreSQL with `pgvector` (for local non-Docker mode) or Docker Desktop
- Port `8000` available for API/UI
- Port `5433` available if using Docker DB mapping

## Quick Local Run (Without Docker)

1. Create env and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

2. Set env:

```bash
export ACL_SEARCH_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/acl_search'
export ACL_SEARCH_ENABLE_DEMO_EMBEDDINGS=true
```

3. Initialize DB:

```bash
python3 scripts/init_db.py
python3 scripts/seed_demo.py
```

4. Run API:

```bash
uvicorn acl_search.main:app --reload
```

5. Open UI:

- [http://localhost:8000/](http://localhost:8000/)

The UI loads demo IDs by default and can ingest/search/update ACLs immediately.

## Docker End-to-End Run

1. Start stack:

```bash
docker compose up --build -d
```

2. Initialize schema + seed demo data inside the API container:

```bash
docker compose exec api python scripts/init_db.py
docker compose exec api python scripts/seed_demo.py
```

3. Open UI:

- [http://localhost:8000/](http://localhost:8000/)

## Troubleshooting

- `Cannot connect to the Docker daemon`
  - Start Docker Desktop, wait until it is fully running, then rerun `docker compose up --build -d`.
- `bind: address already in use` for Postgres port
  - Another local Postgres is already using that port.
  - Stop the local Postgres process or change the host mapping in `docker-compose.yml` (for example `5434:5432`), then rerun compose.
- `python: command not found`
  - Use `python3` instead of `python`.
- `password authentication failed for user "postgres"`
  - You are likely connecting to a different local Postgres instance.
  - For Docker mode, run DB scripts via `docker compose exec api ...` so the container uses the internal DB URL.
- Clean reset for local Docker state
  - `docker compose down -v && docker compose up --build -d`

## UI Walkthrough (What To Do in the UI)

Use this flow to verify end-to-end ACL behavior quickly.

1. Open [http://localhost:8000/](http://localhost:8000/).
2. In **Identity Context**, click **Load Demo IDs** and then **Save Identity**.
3. Go to **Secure Search**, keep **Generate embedding from query text** enabled, enter:
   - Query text: `quarterly revenue growth`
   - Top K: `5`
   Then click **Run Secure Search**.
4. Expected (default demo user in finance group): results should include chunks with `chunk_index` `0` and `2` from seed data.
5. Change **Identity Context > User ID** to:
   - `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2` (operations user)
   Click **Save Identity**, then run search again.
6. Expected for operations user: results should include chunks with `chunk_index` `1` and `2`.
7. Go to **Access Control Updates > Replace Chunk ACL Groups**:
   - Chunk ID: take the `chunk_id` for the result row with `chunk_index=2`
   - Group IDs: `cccccccc-cccc-cccc-cccc-ccccccccccc1` (finance only)
   Click **Apply Chunk ACL**.
8. Search again as operations user.
9. Expected: shared chunk should disappear for operations user, proving ACL enforcement in search.
10. Switch back to finance user (`aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1`) and search again.
11. Expected: finance user still sees finance-authorized chunks, including the updated shared chunk.

Optional ingest validation:

1. In **Ingest Chunk**, enter content and finance group ID `cccccccc-cccc-cccc-cccc-ccccccccccc1`.
2. Click **Ingest Chunk** (auto-embedding stays enabled).
3. Search as operations user: new finance-only chunk should not appear.
4. Search as finance user: new chunk should appear if semantically relevant.

## API Endpoints

- `POST /ingest`
- `POST /search`
- `PUT /users/{user_id}/groups`
- `PUT /chunks/{chunk_id}/acl-groups`
- `GET /health`

## Project Structure

- `src/acl_search/api/app.py`: FastAPI app, routes, UI mount.
- `src/acl_search/repository/search_repository.py`: policy-critical SQL.
- `src/acl_search/service/search_service.py`: transaction + orchestration.
- `src/acl_search/ui/`: built-in frontend (`index.html`, `styles.css`, `app.js`).
- `scripts/init_db.py`: schema/index bootstrap.
- `scripts/seed_demo.py`: demo tenant/data seeding.
- `sql/`: schema, indexing, secure search SQL, examples.
- `docs/ER_DIAGRAM.md`: entity relationship diagram and tenant/ACL key notes.
- `KT.md`: detailed knowledge transfer.

## Configuration

Environment variables:

- `ACL_SEARCH_DATABASE_URL`
- `ACL_SEARCH_EMBEDDING_DIMENSIONS` (default `1536`)
- `ACL_SEARCH_MAX_TOP_K` (default `100`)
- `ACL_SEARCH_DB_POOL_MIN_SIZE` (default `2`)
- `ACL_SEARCH_DB_POOL_MAX_SIZE` (default `20`)
- `ACL_SEARCH_DB_POOL_MAX_IDLE_SECONDS` (default `60`)
- `ACL_SEARCH_ENABLE_DEMO_EMBEDDINGS` (default `false`)

## Tests

```bash
pytest -q
```

Integration tests use `TEST_DATABASE_URL`. If DB/dependencies are missing, tests skip by design.
