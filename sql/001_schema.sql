-- 001_schema.sql
-- Core schema for multi-tenant ACL-aware semantic retrieval.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================
-- Tenancy + identity
-- =====================

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    external_key TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id),
    UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS groups (
    group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, group_id),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS user_groups (
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    group_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id, group_id),
    FOREIGN KEY (tenant_id, user_id)
        REFERENCES app_users(tenant_id, user_id)
        ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, group_id)
        REFERENCES groups(tenant_id, group_id)
        ON DELETE CASCADE
);

-- =====================
-- Documents + chunks
-- =====================

CREATE TABLE IF NOT EXISTS documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    source_uri TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, document_id),
    FOREIGN KEY (tenant_id, created_by_user_id)
        REFERENCES app_users(tenant_id, user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id UUID NOT NULL,
    document_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    token_count INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, chunk_id),
    UNIQUE (tenant_id, document_id, chunk_index),
    FOREIGN KEY (tenant_id, document_id)
        REFERENCES documents(tenant_id, document_id)
        ON DELETE CASCADE,
    CHECK (chunk_index >= 0)
);

-- Group-based ACL grants for chunks.
-- is_allowed is currently always TRUE in writes, but retained for
-- forward compatibility with deny semantics.
CREATE TABLE IF NOT EXISTS chunk_acl_groups (
    tenant_id UUID NOT NULL,
    chunk_id BIGINT NOT NULL,
    group_id UUID NOT NULL,
    is_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, chunk_id, group_id),
    FOREIGN KEY (tenant_id, chunk_id)
        REFERENCES document_chunks(tenant_id, chunk_id)
        ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, group_id)
        REFERENCES groups(tenant_id, group_id)
        ON DELETE CASCADE
);

-- Optional future extension (not used by current query path):
-- CREATE TABLE chunk_acl_users (... allow/deny per user ...);
