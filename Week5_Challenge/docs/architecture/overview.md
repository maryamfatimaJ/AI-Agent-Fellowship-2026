# Architecture Overview

*Updated 2026-08-18 to reflect the current implementation. The earlier version of this
document (Part 1 only) described Conversation Manager, AI Agent, Memory, Knowledge Base,
and LLM integration as "not built yet" — all five have since been built, tested, and
verified live. This document now describes what actually exists. For deeper per-feature
detail see [`PROJECT.md`](../../PROJECT.md); this file is the architectural map.*

## Layered flow

```
User
 -> Frontend (React + Vite + TS, Tailwind) — see Frontend Architecture below
 -> Backend API (FastAPI)
 -> Authentication (JWT, bcrypt)
 -> Workspace Manager (ownership-scoped CRUD, cascading delete)
 -> Conversation Manager (persistent chat, search, rename, pinning)
 -> AI Agent (provider-agnostic LLMService: Gemini default, OpenAI supported)
 -> Memory (pinned + auto-extracted, injected into chat context, scoped per user+workspace)
 -> Knowledge Base (RAG: extract -> chunk -> embed -> cosine retrieval -> cite)
 -> LLM (Gemini `google-genai` / OpenAI `openai`)
 -> Database (SQLAlchemy ORM, SQLite dev / Postgres-Supabase-ready)
```

Every layer above is implemented and covered by automated tests (46 passing,
`backend/tests/`) plus live testing against a real LLM during development
(`docs/evaluation/README.md`).

## Backend module map

| Layer | Module(s) | Responsibility |
|---|---|---|
| Auth | `app/core/security.py`, `app/api/routers/auth.py` | JWT issuance, bcrypt hashing, register/login/me |
| Workspace | `app/api/routers/workspaces.py`, `app/api/deps.py` | Ownership-scoped CRUD; `get_owned_workspace` is the single isolation choke point reused by every other workspace-scoped router |
| Assistant | `app/api/routers/assistants.py`, `app/models/assistant.py` | Per-workspace persona/config (role, system prompt, model, temperature, max tokens) |
| Conversation | `app/api/routers/conversations.py`, `app/services/chat_service.py` | Message persistence, search, rename, pinning, and the actual chat turn (builds context from memory + RAG, calls the LLM, records usage) |
| Knowledge Base | `app/rag/` (`extraction.py`, `chunking.py`, `retrieval.py`), `app/api/routers/documents.py` | Upload -> extract -> chunk -> embed -> cosine-similarity retrieval with a relevance floor -> cited answers |
| Memory | `app/memory/memory_service.py`, `app/api/routers/memory.py` | Manual pinning + best-effort LLM-based fact extraction after each turn, scoped by workspace+user |
| Prompts / Skills | `app/prompts/`, `app/skills/`, `app/services/skill_service.py` | Reusable content: prompt templates inserted into the composer; skills run through one generic execution engine driven by stored config, not per-skill code |
| Database | `app/database/`, `app/models/` | SQLAlchemy base/session; one model file per entity; string-UUID PKs, no SQLite-only types (see [`database-schema.md`](database-schema.md)) |
| API | `app/api/routers/*.py`, `app/main.py` | One router per resource, consistent `/api/workspaces/{id}/...` prefix pattern, centralized CORS + exception handling |

## Frontend architecture

The frontend (`frontend/src/`) is a single-page React app; this section was missing from
the original architecture documentation and is added here to close that gap.

- **Routing** (`react-router-dom` v7, `App.tsx`): a flat public route pair
  (`/login`, `/register`) plus a protected tree gated by `ProtectedRoute`. Inside the
  protected tree, `/workspaces` lists the user's workspaces (`WorkspacesPage.tsx`), and
  `/workspaces/:workspaceId/*` mounts `WorkspaceShell.tsx` — a layout route whose sidebar
  (conversation list, nav to Dashboard/Prompts/Skills/Assistant/Knowledge/Memory) persists
  across nested pages rendered through its `<Outlet>`.
- **State management**: no global store (Redux/Zustand) — state is local `useState`/`useEffect`
  per page, plus two React Context providers for genuinely cross-cutting concerns:
  `AuthContext` (`lib/AuthContext.tsx`, current user + token lifecycle) and `ThemeContext`
  (`lib/ThemeContext.tsx`, light/dark/system preference persisted to `localStorage`). This
  was a deliberate choice, not an oversight — the app's state is mostly page-local
  (a conversation's messages don't need to be visible outside the chat page), so a global
  store would add indirection without solving a real problem here.
- **API layer** (`lib/api.ts`): a single typed client wrapping `fetch`, attaching the JWT
  from `localStorage` to every request and normalizing errors into a typed `ApiError`. Every
  backend resource has a matching typed function here (e.g. `renameWorkspace`,
  `runSkill`) — there is no direct `fetch()` call anywhere else in the codebase, which keeps
  the API surface auditable from one file.
- **Component structure**: `components/` holds cross-page primitives (`EmptyState`,
  `ConfirmDialog`, `ThemeToggle`) and a `components/chat/` subfolder for chat-specific pieces
  (`MessageBubble`, `Composer`, `PromptPicker`, `SkillPicker`); `pages/workspace/` holds one
  file per workspace-scoped page (Chat, Dashboard, Assistant, Documents, Memory, Prompts,
  Skills), each independently data-fetching via the shared API client.
- **Styling**: Tailwind CSS v4 with CSS custom-property theme tokens (`index.css`) rather
  than a component library — chosen so the "calm, editorial, no-generic-AI-SaaS-styling"
  design direction could be expressed directly as design tokens (`--color-accent`,
  `--color-canvas`, etc.) instead of overriding a third-party component library's defaults.

## User isolation

Every workspace-scoped query filters by `Workspace.owner_id == current_user.id` at the ORM
level (not just via a route guard), so a guessed/enumerated ID returns 404, not a
permissions error — it can't be used to probe for a resource's existence. See
`app/api/deps.py::get_owned_workspace` and its coverage in
`tests/integration/test_workspace_isolation.py` and
`tests/integration/test_workspace_rename_delete.py`. This was also verified live: a second
account's GET/PATCH/DELETE attempts against every resource type in another user's workspace
returned 404 in every case (see `docs/evaluation/README.md`, Section 1.06 and Section 14).

## Known documentation/implementation gaps (from the 2026-08-17 audit)

- No server-side session revocation (stateless JWT, client-side-only "logout").
- No application-level rate limiting (see `docs/security/README.md`).
- `WorkspaceSettings` has a DB table and is auto-created per workspace, but no API endpoint
  reads or writes it — dead feature surface, not wired to anything.
- The `Log` DB table is defined but never written to (Python-level file/console logging is
  the only logging that actually happens).
