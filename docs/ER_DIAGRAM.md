# ER Diagram - ACL Semantic Search Schema

This diagram reflects the current DDL in `sql/001_schema.sql`.

```mermaid
erDiagram
    tenants {
        uuid tenant_id PK
        text name
        text external_key UK
        timestamptz created_at
    }

    app_users {
        uuid user_id PK
        uuid tenant_id FK
        text email
        text display_name
        boolean is_active
        timestamptz created_at
    }

    groups {
        uuid group_id PK
        uuid tenant_id FK
        text name
        text description
        timestamptz created_at
    }

    user_groups {
        uuid tenant_id PK,FK
        uuid user_id PK,FK
        uuid group_id PK,FK
        timestamptz created_at
    }

    documents {
        uuid document_id PK
        uuid tenant_id FK
        text title
        text source_uri
        jsonb metadata
        uuid created_by_user_id FK
        timestamptz created_at
    }

    document_chunks {
        bigint chunk_id PK
        uuid tenant_id FK
        uuid document_id FK
        int chunk_index
        text content
        vector_1536 embedding
        int token_count
        jsonb metadata
        timestamptz created_at
    }

    chunk_acl_groups {
        uuid tenant_id PK,FK
        bigint chunk_id PK,FK
        uuid group_id PK,FK
        boolean is_allowed
        timestamptz created_at
    }

    tenants ||--o{ app_users : contains
    tenants ||--o{ groups : contains
    tenants ||--o{ documents : owns

    app_users ||--o{ user_groups : membership
    groups ||--o{ user_groups : membership

    app_users ||--o{ documents : created_by_optional

    documents ||--o{ document_chunks : has

    document_chunks ||--o{ chunk_acl_groups : acl_assigned
    groups ||--o{ chunk_acl_groups : acl_principal
```

## Relationship Notes

- `user_groups` is the tenant-scoped many-to-many bridge between `app_users` and `groups`.
- `chunk_acl_groups` is the tenant-scoped many-to-many bridge between `document_chunks` and `groups`.
- `documents.created_by_user_id` is nullable, so a document may exist without a creator user (`ON DELETE SET NULL`).
- `document_chunks.embedding` stores dense vectors (`VECTOR(1536)` in PostgreSQL).

## Key Constraints (Important for Isolation)

- `app_users`: `UNIQUE (tenant_id, user_id)`, `UNIQUE (tenant_id, email)`
- `groups`: `UNIQUE (tenant_id, group_id)`, `UNIQUE (tenant_id, name)`
- `documents`: `UNIQUE (tenant_id, document_id)`
- `document_chunks`: `UNIQUE (tenant_id, chunk_id)`, `UNIQUE (tenant_id, document_id, chunk_index)`
- `user_groups`: `PRIMARY KEY (tenant_id, user_id, group_id)`
- `chunk_acl_groups`: `PRIMARY KEY (tenant_id, chunk_id, group_id)`

These composite keys and tenant-scoped foreign keys are what enforce clean multi-tenant boundaries.
