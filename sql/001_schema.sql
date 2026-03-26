-- vecgate/sql/001_schema.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(255) UNIQUE NOT NULL,
    email         VARCHAR(255),
    password_hash VARCHAR(255),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INT REFERENCES users ON DELETE CASCADE,
    role_id INT REFERENCES roles ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS facets (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_facets (
    role_id  INT REFERENCES roles  ON DELETE CASCADE,
    facet_id INT REFERENCES facets ON DELETE RESTRICT,
    PRIMARY KEY (role_id, facet_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT,
    source_uri TEXT,
    facet_id   INT REFERENCES facets ON DELETE RESTRICT NOT NULL,
    metadata   JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id UUID REFERENCES documents ON DELETE CASCADE NOT NULL,
    facet_id    INT  REFERENCES facets    ON DELETE RESTRICT NOT NULL,
    chunk_index INT  NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536) NOT NULL,
    token_count INT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id  INT  REFERENCES users  ON DELETE CASCADE,
    group_id UUID REFERENCES groups ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

-- chunk_acl_groups: v1 always sets is_allowed=TRUE; FALSE reserved for v2 deny semantics
CREATE TABLE IF NOT EXISTS chunk_acl_groups (
    chunk_id   BIGINT REFERENCES chunks ON DELETE CASCADE,
    group_id   UUID   REFERENCES groups ON DELETE CASCADE,
    is_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (chunk_id, group_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            SERIAL PRIMARY KEY,
    user_id       INT REFERENCES users,
    action        VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id   TEXT,
    ip_address    INET,
    details       JSONB,
    timestamp     TIMESTAMPTZ DEFAULT now()
);
