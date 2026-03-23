-- 003_examples.sql
-- Parameterized examples to use from application code.

-- 1) Insert a document chunk with embedding
-- Inputs: tenant_id UUID, document_id UUID, chunk_index INT, content TEXT,
--         embedding VECTOR literal string (e.g. '[0.1,0.2,...]'), token_count INT, metadata JSONB
INSERT INTO document_chunks (
    tenant_id,
    document_id,
    chunk_index,
    content,
    embedding,
    token_count,
    metadata
)
VALUES (
    $1::uuid,
    $2::uuid,
    $3::int,
    $4::text,
    $5::vector,
    $6::int,
    COALESCE($7::jsonb, '{}'::jsonb)
)
RETURNING chunk_id;

-- 2) Assign ACL groups to a chunk (upsert grants)
-- Inputs: tenant_id UUID, chunk_id BIGINT, group_ids UUID[]
INSERT INTO chunk_acl_groups (tenant_id, chunk_id, group_id, is_allowed)
SELECT $1::uuid, $2::bigint, g.group_id, TRUE
FROM unnest($3::uuid[]) AS g(group_id)
ON CONFLICT (tenant_id, chunk_id, group_id)
DO UPDATE SET is_allowed = EXCLUDED.is_allowed;

-- 3) Resolve a user's effective groups
-- Inputs: tenant_id UUID, user_id UUID
SELECT ug.group_id
FROM user_groups ug
JOIN app_users u
  ON u.tenant_id = ug.tenant_id
 AND u.user_id = ug.user_id
WHERE ug.tenant_id = $1::uuid
  AND ug.user_id = $2::uuid
  AND u.is_active = TRUE;
