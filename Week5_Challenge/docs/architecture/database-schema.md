# Database Schema — Part 1

All primary keys are string UUIDs (portable across SQLite and Postgres). All tables have
`created_at`/`updated_at`. Foreign keys cascade delete downward from `workspaces` unless noted.

## ERD

```mermaid
erDiagram
    USERS ||--o{ WORKSPACES : owns
    WORKSPACES ||--o{ ASSISTANTS : contains
    WORKSPACES ||--o{ CONVERSATIONS : contains
    WORKSPACES ||--o{ DOCUMENTS : contains
    WORKSPACES ||--o{ PROMPT_TEMPLATES : contains
    WORKSPACES ||--o{ SKILLS : contains
    WORKSPACES ||--o{ MEMORY : contains
    WORKSPACES ||--|| SETTINGS : has
    ASSISTANTS ||--o{ CONVERSATIONS : used_by
    CONVERSATIONS ||--o{ MESSAGES : contains
    DOCUMENTS ||--o{ CHUNKS : split_into
    USERS ||--o{ CONVERSATIONS : creates
    USERS ||--o{ DOCUMENTS : uploads
    USERS ||--o{ LOGS : generates
    USERS ||--o{ USAGE : generates
    WORKSPACES ||--o{ LOGS : scoped_to
    WORKSPACES ||--o{ USAGE : scoped_to

    USERS {
        string id PK
        string email
        string hashed_password
        string full_name
        bool is_active
    }
    WORKSPACES {
        string id PK
        string owner_id FK
        string name
        string description
    }
    ASSISTANTS {
        string id PK
        string workspace_id FK
        string name
        string system_prompt
        string model_provider
        string model_name
    }
    CONVERSATIONS {
        string id PK
        string workspace_id FK
        string assistant_id FK
        string created_by FK
        string title
    }
    MESSAGES {
        string id PK
        string conversation_id FK
        string role
        string content
    }
    DOCUMENTS {
        string id PK
        string workspace_id FK
        string uploaded_by FK
        string filename
        string status
    }
    CHUNKS {
        string id PK
        string document_id FK
        int chunk_index
        string content
        string embedding
    }
    PROMPT_TEMPLATES {
        string id PK
        string workspace_id FK
        string created_by FK
        string name
        string content
    }
    SKILLS {
        string id PK
        string workspace_id FK
        string name
        json config
        bool enabled
    }
    MEMORY {
        string id PK
        string workspace_id FK
        string conversation_id FK
        string user_id FK
        string memory_type
        string key
        string value
    }
    SETTINGS {
        string id PK
        string workspace_id FK
        json data
    }
    LOGS {
        string id PK
        string user_id FK
        string workspace_id FK
        string level
        string event_type
        string message
    }
    USAGE {
        string id PK
        string user_id FK
        string workspace_id FK
        string provider
        string model
        int input_tokens
        int output_tokens
        float cost_usd
    }
```

## Isolation rule

Every workspace-scoped query filters by `Workspace.owner_id == current_user.id` at the ORM
level (not just via a route guard), so a guessed/enumerated ID can't leak another user's row.
See `app/api/routers/workspaces.py::_get_owned_workspace_or_404` and its test coverage in
`tests/integration/test_workspace_isolation.py`.

## SQLite -> Postgres/Supabase migration path

`Chunk.embedding` is `Text` (JSON-encoded) for now; it becomes a `pgvector` column with the
same name once `DATABASE_URL` points at Postgres — no other model changes required. No
SQLite-only types (native UUID, arrays) are used anywhere in the schema.
