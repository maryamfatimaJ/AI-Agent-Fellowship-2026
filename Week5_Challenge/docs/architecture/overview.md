# Architecture Overview — Part 1 Foundation

## Layered flow

```
User
 -> Frontend (React + Vite + TS, Tailwind)
 -> Backend API (FastAPI)
 -> Authentication (JWT, bcrypt)
 -> Workspace Manager (ownership-scoped CRUD)
 -> Conversation Manager        [models only — Part 2]
 -> AI Agent                    [not built — later part]
 -> Memory                      [models only — later part]
 -> Knowledge Base (RAG)        [models only — later part]
 -> LLM (provider-agnostic)     [not wired — later part]
 -> Database (SQLAlchemy ORM, SQLite dev / Postgres-Supabase prod)
```

## What is functional in Part 1

- `auth`: register, login (JWT), `/me`
- `workspaces`: create/list/get/update/delete, all queries filtered by `owner_id == current_user.id`
- `health`: DB connectivity check

## What exists only as schema (no business logic yet)

Assistant, Conversation, Message, Document, Chunk, PromptTemplate, Skill, Memory,
WorkspaceSettings, Log, Usage — see [database-schema.md](database-schema.md).

## Why this split

The Part 1 brief explicitly excludes chat, RAG, memory, skills, evaluation, experiments,
and deployment. Building only auth + workspaces end-to-end proves the isolation model
(User -> Workspace ownership) that every other entity will inherit, without writing
functionality that has to be thrown away or reworked once the AI layer starts.
