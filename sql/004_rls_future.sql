-- 004_rls_future.sql
-- Optional future hardening (not required for main implementation).
-- Keep application-level secure SQL in place; RLS is defense-in-depth.

-- Example context keys (set per request by the DB session wrapper):
--   SET app.current_tenant_id = '<tenant_uuid>';
--   SET app.current_user_id = '<user_uuid>';

-- ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chunk_acl_groups ENABLE ROW LEVEL SECURITY;

-- Example tenant guard for chunks:
-- CREATE POLICY document_chunks_tenant_isolation
-- ON document_chunks
-- USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Example ACL-aware guard can be added, but will increase policy complexity.
-- In many systems, keeping authorization in explicit SQL CTEs (current design)
-- and adding tenant-only RLS as a second layer is the best balance.
