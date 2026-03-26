-- vecgate/sql/002_indexes.sql
-- Relational indexes
CREATE INDEX IF NOT EXISTS idx_user_roles_user    ON user_roles   (user_id);
CREATE INDEX IF NOT EXISTS idx_role_facets_role   ON role_facets  (role_id);
CREATE INDEX IF NOT EXISTS idx_user_groups_user   ON user_groups  (user_id);
CREATE INDEX IF NOT EXISTS idx_chunk_acl_chunk    ON chunk_acl_groups (chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_facet       ON chunks       (facet_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document    ON chunks       (document_id);
CREATE INDEX IF NOT EXISTS idx_audit_user         ON audit_log    (user_id);

-- Note: per-facet HNSW indexes are created dynamically at runtime
-- when a new facet is created, using:
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_facet_{N}
--   ON chunks USING hnsw (embedding vector_cosine_ops)
--   WITH (m = {M}, ef_construction = {EF})
--   WHERE facet_id = {N};
