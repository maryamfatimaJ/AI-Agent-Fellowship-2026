# AI Workspace Platform — Project Document

This document describes what Week 5 actually is, how it's built, and how to run, test, and
deploy it. For day-to-day setup commands see [README.md](README.md); this file goes deeper
on architecture, feature scope, and deployment. Nothing below is aspirational — every
feature listed is implemented and covered by a passing test or was verified live against a
real LLM during development.

## Project Overview

A simplified multi-user AI workspace platform in the shape of ChatGPT Teams / Claude
Projects: users register, create isolated workspaces, configure a per-workspace AI
assistant, hold persistent multi-turn conversations, upload documents the assistant can
cite from, and build up long-term memory and a reusable prompt/skill library — all backed
by a real database and a real LLM (Gemini by default, OpenAI supported).

## Problem Statement

Individual AI chat tools don't give a team (or a single user managing multiple projects) a
shared, isolated place to organize assistants, conversations, and knowledge per project.
Nothing carries over between chat sessions unless the tool has real persistence and access
control. This platform provides per-user workspaces with strict data isolation, persistent
state, and a reusable-content layer (prompts, skills) as the foundation for that.

## Week 5 Objectives

Built incrementally across three parts:

1. **Foundation** — repo audit of Weeks 1-4, architecture/stack decisions, auth + workspace
   CRUD, full database schema.
2. **Core platform** — assistant configuration, persistent chat, document RAG, long-term
   memory, all wired to the real database and a real LLM.
3. **Platform depth** — prompt library, six reusable AI skills, a real-data dashboard, and
   four advanced features (export, pinned messages, multi-model support, dark mode).

## Main Features

- JWT auth (register/login/me) with strict per-user data isolation enforced at the ORM
  query level, not just route guards
- Multiple workspaces per user, each with its own assistant, conversations, documents,
  memory, prompts, and skills
- Configurable AI assistant per workspace: name, role, system prompt, personality,
  response style, provider, model, temperature, max tokens
- Persistent multi-turn conversations: auto + manual titles, rename, delete, search across
  titles and message content, survive logout/relogin and backend restarts
- Document knowledge base (PDF/DOCX/TXT/Markdown) with cited retrieval
- Long-term memory: manual pinning + automatic extraction from chat, never leaked between
  users or workspaces
- Prompt library with categories, seeded starter prompts, inserted straight into the chat
  composer
- Six reusable AI skills run through one generic execution engine, usable standalone or
  attached to a conversation
- Dashboard with real counts, real token usage, and estimated cost
- Conversation export to Markdown, pinned messages, a real model catalog picker, and a
  light/dark/system theme toggle

## Architecture

```
User
 -> Frontend (React + Vite + TS)
 -> Backend API (FastAPI)
 -> Auth (JWT)
 -> Workspace Manager (ownership-scoped at the ORM level)
 -> Conversation Manager
 -> AI Agent (provider-agnostic LLMService: Gemini / OpenAI)
 -> Memory (pinned + auto-extracted, injected into chat context)
 -> Knowledge Base (RAG: extract -> chunk -> embed -> cosine retrieval -> cite)
 -> Database (SQLAlchemy ORM; SQLite locally, Postgres/Supabase-ready)
```

Every layer above is implemented. Skills and the prompt library sit alongside the
Conversation Manager — a skill run either returns a standalone result or writes real
messages into a conversation, so it uses the same chat persistence path rather than a
side channel.

## Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Backend framework | FastAPI | async-ready, typed, matches Week 4's proven pattern |
| ORM | SQLAlchemy 2.0 | portable between SQLite and Postgres with no code changes |
| Auth | `pyjwt` + `bcrypt` | avoids `passlib`'s bcrypt-backend version friction |
| Validation | Pydantic v2 | request/response schemas separate from ORM models |
| LLM SDKs | `google-genai` (default), `openai` (optional) | matches Weeks 1-3's Gemini convention, OpenAI as a real alternative, not just a stub |
| RAG | `pypdf`, `python-docx`, `numpy` | lightweight extraction + cosine similarity; no separate vector DB service |
| Frontend | React 19 + Vite + TypeScript | fast dev loop, continues Week 4's frontend stack |
| Styling | Tailwind CSS v4 | CSS-variable theme tokens, used for the light/dark toggle |
| Routing | React Router v7 | nested layout routes for the workspace shell |

## Project Structure

```
Week5_Challenge/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, router registration, CORS, error handling
│   │   ├── core/               settings, JWT/password hashing, logging config
│   │   ├── database/           SQLAlchemy base, session, get_db dependency
│   │   ├── models/              ORM models: user, workspace, assistant, conversation,
│   │   │                        message, document, chunk, prompt_template, skill,
│   │   │                        memory, settings, log, usage
│   │   ├── schemas/             Pydantic request/response schemas
│   │   ├── services/            llm_service, chat_service, skill_service, usage_service
│   │   ├── rag/                 extraction, chunking, embedding + retrieval
│   │   ├── memory/               memory_service (pin, auto-extract, context retrieval)
│   │   ├── prompts/, skills/     default seed data
│   │   └── api/
│   │       ├── deps.py          get_current_user, get_owned_workspace
│   │       └── routers/         health, auth, workspaces, assistants, conversations,
│   │                            documents, memory, prompts, skills, dashboard, models
│   └── tests/                   unit/, api/, integration/ — 40 tests
├── frontend/
│   └── src/
│       ├── lib/                 api client, auth/theme context, helpers
│       ├── components/          shared UI + chat-specific components
│       └── pages/                auth pages, workspace list, and the workspace shell's
│                                  dashboard/chat/assistant/knowledge/memory/prompts/skills pages
└── docs/                        architecture, builder-journal, and placeholders for
                                  research/evaluation/experiments/security/performance
```

## Authentication

JWT bearer tokens (`pyjwt`), passwords hashed with `bcrypt`. `POST /api/auth/register`,
`POST /api/auth/login`, `GET /api/auth/me`. No refresh tokens or email verification —
tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) and the frontend stores the
token in `localStorage`, clearing it on logout. Every other endpoint depends on
`get_current_user`, and every workspace-scoped endpoint additionally depends on
`get_owned_workspace`, which filters by `owner_id == current_user.id` at the query level —
a guessed or enumerated workspace ID returns 404, not a permissions error, so it can't be
used to probe for existence.

## Workspaces

A workspace is the unit of isolation: one owner, and everything else (assistant,
conversations, documents, memory, prompts, skills, settings) hangs off `workspace_id` with
cascading deletes. Creating a workspace auto-provisions a default assistant, empty
settings row, four starter prompts, and the six default skills.

## AI Assistant Configuration

One assistant per workspace (the schema supports more, but the API only exposes
get-or-create-the-one-assistant, matching what was actually asked for). Configurable:
`name`, `role`, `system_prompt`, `personality`, `response_style`, `model_provider`
(gemini/openai), `model_name` (from a real catalog or left as provider default),
`temperature`, `max_tokens`. Changes take effect on the next message in that workspace.

## Persistent Conversations

Conversations and messages are real database rows (`conversations`, `messages` tables).
Titles default to the first ~60 characters of the first message and can be renamed.
Search (`GET /api/workspaces/{id}/conversations?q=`) matches title OR message content.
Deleting a conversation cascades its messages. Verified to survive logout/login and a full
backend process restart (tested live, not just asserted).

## Knowledge Base / RAG

Upload PDF, DOCX, TXT, or Markdown. Pipeline: extract text → chunk (character sliding
window, configurable size/overlap) → embed each chunk (Gemini `gemini-embedding-001` or
OpenAI `text-embedding-3-small`) → store the embedding alongside the chunk row → at query
time, embed the user's message and rank chunks by cosine similarity, computed in Python
with `numpy`. Chunks scoring below `RAG_MIN_SCORE` (default 0.65) are excluded so an
unrelated question doesn't get irrelevant document snippets stuffed into the prompt — this
threshold was added after a real bug was found during live testing (documented in
`docs/builder-journal/part-2.md`). Matching chunks are returned as citations
(`filename`, `chunk_index`, `snippet`, `score`) alongside the assistant's reply. No
separate vector database — embeddings live in the same SQL row as the chunk text, which
also means there's no local file dependency for document storage (the raw upload is never
written to disk; only extracted text is persisted).

## Long-Term Memory

Two paths into the same `memory` table: manual pinning (`POST /api/workspaces/{id}/memory`)
and best-effort automatic extraction after each chat turn (a small LLM call asks "what's
worth remembering from this exchange," wrapped in try/except so a bad extraction never
breaks the chat response). Memory is scoped by `workspace_id` + `user_id` — retrieval
(`get_context_memories`) only returns rows belonging to the requesting user, verified by a
dedicated isolation test.

## Prompt Library

CRUD (`/api/workspaces/{id}/prompts`) with six categories (writing, programming, research,
business, education, custom). Every new workspace is seeded with four starter prompts.
Integrated into the chat composer via a "Prompts" picker that inserts a prompt's content
directly into the message box, rather than living on an isolated page.

## AI Skills

Six seeded skills — Summarize, Write an email, Generate a report, Meeting notes, Generate
ideas, SWOT analysis — run through **one generic execution engine**
(`app/services/skill_service.py`) driven by each skill's stored `config.prompt_template`,
not six hardcoded endpoints. A skill can run standalone (`POST
/api/workspaces/{id}/skills/{skill_id}/run` with just `input`) or attached to a
conversation (`conversation_id` in the same request), in which case its output is written
as real `user`/`assistant` messages in that conversation — so it shows up in history,
search, export, and pinning like any other exchange. Reachable from both the dedicated
Skills page and directly from the chat composer's skill picker.

## Dashboard

`GET /api/workspaces/{id}/dashboard` aggregates real data: counts (conversations, messages,
documents, memory items, prompt templates, skills), token usage and an estimated cost
(summed from a `usage` table populated by every LLM call — chat, memory extraction, and
skills alike), and a merged recent-activity feed (recent conversations, documents, and
memory updates, most recent first). No decorative or placeholder charts.

## Advanced Features

- **Conversation export** — client-side Markdown export of a full conversation (including
  citations), triggered as a browser download.
- **Pinned messages** — any message can be pinned/unpinned; a conversation's pinned view
  is a filtered slice of the same message list.
- **Multi-model support** — `GET /api/models` backs a real provider/model dropdown in the
  assistant settings UI (Gemini and OpenAI paths are both functional, not just one wired up).
- **Dark mode** — a manual light/dark/system toggle (not just OS-detection), persisted in
  `localStorage`, implemented via CSS custom-property overrides on `:root[data-theme]`.

## Database

SQLAlchemy ORM, SQLite for local development, string-UUID primary keys throughout (portable
— no SQLite-only types anywhere in the schema, so moving to Postgres is a `DATABASE_URL`
change, not a rewrite). Tables: `users`, `workspaces`, `assistants`, `conversations`,
`messages`, `documents`, `chunks`, `prompt_templates`, `skills`, `memory`, `settings`,
`logs`, `usage`. Full ERD in
[docs/architecture/database-schema.md](docs/architecture/database-schema.md). Schema is
created via `Base.metadata.create_all()` on startup — there is no migration tool yet
(Alembic would be the next step once the schema stabilizes and holds real user data).

## API Overview

All routes are prefixed `/api`. Selected endpoints (see FastAPI's auto-generated docs at
`/docs` for the full list with request/response schemas):

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Workspaces | `GET/POST /workspaces`, `GET/PATCH/DELETE /workspaces/{id}` |
| Assistant | `GET/PATCH /workspaces/{id}/assistant` |
| Conversations | `GET/POST /workspaces/{id}/conversations`, `GET/PATCH/DELETE .../{id}`, `POST .../{id}/messages`, `PATCH .../{id}/messages/{message_id}` (pin), `GET .../{id}/pinned-messages` |
| Documents | `GET/POST /workspaces/{id}/documents`, `DELETE .../{id}` |
| Memory | `GET/POST /workspaces/{id}/memory`, `PATCH/DELETE .../{id}` |
| Prompts | `GET/POST /workspaces/{id}/prompts`, `PATCH/DELETE .../{id}` |
| Skills | `GET /workspaces/{id}/skills`, `POST .../{skill_id}/run` |
| Dashboard | `GET /workspaces/{id}/dashboard` |
| Models | `GET /models` |
| Health | `GET /health` |

## Local Installation

See [README.md](README.md#local-setup) for the exact commands. Short version: Python 3.11
+ `pip install -r backend/requirements.txt`, Node 18+ + `npm install` in `frontend/`, copy
both `.env.example` files to `.env` and fill in `SECRET_KEY` + `GEMINI_API_KEY` (or
`OPENAI_API_KEY` with `LLM_PROVIDER=openai`).

## Environment Variables

See [README.md](README.md#environment-variables) for the full table. The only variables
that must be real (not placeholders) to run live are `SECRET_KEY` (generate one — never use
the default) and `GEMINI_API_KEY` or `OPENAI_API_KEY` depending on `LLM_PROVIDER`.

## How to Run Backend

```bash
cd Week5_Challenge/backend
python -m venv .venv && ./.venv/Scripts/activate   # Python 3.11 recommended
pip install -r requirements.txt
cp .env.example .env   # fill in SECRET_KEY and GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

## How to Run Frontend

```bash
cd Week5_Challenge/frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

## How to Run Tests

```bash
cd Week5_Challenge/backend
pytest
```

40 tests, all LLM calls mocked (deterministic fake embeddings + canned replies), so this
runs with no API key and no network access. Frontend has no automated test suite yet —
verified via `npm run build` (TypeScript compiles clean) and manual/API-level testing; no
headless browser tool was available in the development environment to add real UI tests.

## Deployment

**Architecture suitability, checked before deploying anything:**

- **Frontend** — a static Vite/React build (`npm run build` → `dist/`). This is exactly
  what Vercel is for: no server-side rendering, no long-running process, just static assets
  behind a CDN. **Suitable for Vercel, deployed there.**
- **Backend — not suitable for Vercel.** Vercel's Python support is serverless functions:
  stateless, ephemeral filesystem, execution-time limits. This backend (a) uses SQLite, a
  file on disk — on a serverless platform every invocation can get a fresh, empty
  filesystem, so the database would not reliably persist between requests; (b) runs
  `Base.metadata.create_all()` and loads settings at import time, patterns built for a
  long-lived process, not a cold-started function; (c) LLM calls (chat generation,
  embeddings, memory extraction) can take several seconds each, which is workable on a
  normal server but risks hitting serverless execution-time limits under load. **Deployed
  instead to a platform built for a persistent process** (Render/Railway-style web
  service).
- **Document storage** — a genuine plus for portability here: uploaded files are never
  written to disk. Extraction happens in memory and only the extracted text + embeddings
  are persisted (in the database). This removes what would otherwise be a hard blocker for
  any serverless-style deployment.
- **Database in production** — SQLite is fine for this development/demo deployment, but on
  most backend hosts (including Render's free tier) the filesystem is not guaranteed to
  survive a redeploy or restart. For anything beyond a demo, `DATABASE_URL` should point at
  a hosted Postgres (Render Postgres, Neon, or Supabase all have free tiers) — no code
  change is required, only the connection string, per the schema's original design goal.
- **CORS** — `CORS_ALLOW_ORIGINS` must be set to the deployed frontend's real origin, not
  `localhost`.
- **Frontend → backend URL** — `VITE_API_BASE_URL` is baked into the frontend bundle at
  build time, so it must be set as a build-time environment variable on Vercel, pointing at
  the deployed backend's URL.

## Live URL

*Not yet deployed as of this document's writing.* See the note at the end of this document
for the current status and what deployment requires next.

## GitHub Repository

https://github.com/maryamfatimaJ/AI-Agent-Fellowship-2026

Week 5 code lives under `Week5_Challenge/` on the `main` branch.

## Known Limitations

- No database migration tool (Alembic) — schema changes require recreating the database,
  acceptable pre-launch but not once real user data exists.
- Usage/cost figures on the dashboard are estimates from a hardcoded pricing table, not
  billing-accurate.
- RAG relevance threshold (`RAG_MIN_SCORE`) is a first-pass heuristic, not tuned against a
  real evaluation set.
- Memory retrieval for chat context is recency/pinned-first, not semantic.
- Skills are user-invoked (composer picker or Skills page), not autonomously triggered by
  the assistant via function-calling.
- No automated frontend test suite or CI pipeline yet.
- Single assistant per workspace via the API, though the schema supports more.

## Future Improvements

- Alembic migrations once the schema is stable against real data.
- Semantic memory retrieval (embed memories, rank by relevance to the current message).
- Real LLM tool-calling so the assistant can decide when to invoke a skill mid-conversation.
- Evaluation framework and scenario suite (planned for a later part of this fellowship).
- CI (lint + test) on push, and a frontend test suite.
- Streaming chat responses instead of request/response.

---

**Deployment status note:** the platform is fully built, tested, and runs locally end to
end (see [README.md](README.md) for local URLs verified during development). Actually
publishing it requires either an account/API token for a hosting platform (Vercel for the
frontend, Render/Railway for the backend) or the user completing the platform's own
browser-based sign-in — neither of which was available in the development environment.
This section will be updated with real URLs once deployment is completed; no URL is listed
above because none exists yet.
