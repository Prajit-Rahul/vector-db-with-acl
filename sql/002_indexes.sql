-- 002_indexes.sql
-- Index strategy for tenant isolation, ACL joins, and vector similarity.

-- Tenant and identity lookups.
CREATE INDEX IF NOT EXISTS idx_app_users_tenant_user_active
    ON app_users (tenant_id, user_id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_user_groups_tenant_user
    ON user_groups (tenant_id, user_id, group_id);

CREATE INDEX IF NOT EXISTS idx_user_groups_tenant_group
    ON user_groups (tenant_id, group_id, user_id);

-- Chunk ownership and tenant pre-filter.
CREATE INDEX IF NOT EXISTS idx_document_chunks_tenant_chunk
    ON document_chunks (tenant_id, chunk_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_tenant_document
    ON document_chunks (tenant_id, document_id, chunk_index);

-- ACL join path (effective groups -> chunk grants).
CREATE INDEX IF NOT EXISTS idx_chunk_acl_groups_tenant_group_chunk
    ON chunk_acl_groups (tenant_id, group_id, chunk_id)
    WHERE is_allowed = TRUE;

CREATE INDEX IF NOT EXISTS idx_chunk_acl_groups_tenant_chunk
    ON chunk_acl_groups (tenant_id, chunk_id);

-- Recommended default ANN index for high-recall production search.
-- HNSW tradeoff: more memory + slower build, faster and usually better recall at query time.
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Optional alternative index (use instead of HNSW if bulk-refresh heavy).
-- IVFFlat tradeoff: faster build / lower memory, but requires ANALYZE and query-time probes tuning.
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_ivfflat
--     ON document_chunks
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 200);

-- If you enable IVFFlat, tune per session/request:
-- SET ivfflat.probes = 10;  -- higher probes => higher recall, more latency
