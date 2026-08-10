# AI Workspace Platform

Week 5 of the AI Agent Fellowship 2026 — a simplified multi-user AI workspace platform
(ChatGPT Teams / Claude Projects style): users own workspaces, workspaces hold assistants,
conversations, documents, prompt templates, skills, and memory.

**Status: Part 2 — core platform is real and working end-to-end.** Auth, workspaces,
assistant configuration, persistent chat, document RAG, and long-term memory are all live
against a real database and a real LLM (Gemini by default). Prompt library, skills,
evaluation, experiments, and deployment are still ahead — see
[docs/architecture/overview.md](docs/architecture/overview.md).

## Problem statement

Individual AI chat tools don't give teams a shared, isolated place to organize assistants,
conversations, and knowledge per project. This platform provides per-user workspaces with
strict data isolation as the base for that.

## Features

- User registration/login (JWT-based auth), fully isolated per-user data
- Workspace creation and management, each with its own assistant, conversations, documents, and memory
- Assistant configuration: name, role, system prompt, personality, response style, model, temperature, max tokens
- Persistent multi-turn conversations: history, titles (auto + rename), delete, search across titles and message content
- Document knowledge base: PDF/DOCX/TXT/Markdown upload → text extraction → chunking → embeddings → cosine-similarity
  retrieval → cited answers
- Long-term memory: manually pinned facts plus automatic extraction of durable preferences/topics from chat,
  scoped per user per workspace

## Tech stack

- **Backend:** FastAPI, SQLAlchemy ORM, Pydantic v2, `pyjwt` + `bcrypt` for auth
- **Frontend:** React + Vite + TypeScript + Tailwind CSS
- **Database:** SQLite (local dev) — swappable to PostgreSQL/Supabase via `DATABASE_URL` alone
- **AI provider:** Gemini by default (`google-genai`, matching Weeks 1-3), OpenAI supported via `LLM_PROVIDER=openai`
- **RAG:** chunking + embeddings stored in SQL, cosine similarity in Python (no separate vector DB — see
  [docs/architecture/database-schema.md](docs/architecture/database-schema.md) for why)

## Architecture

```
User -> Frontend -> Backend API -> Auth -> Workspace Manager -> Conversation Manager -> AI Agent (LLMService)
         -> Memory (pin + auto-extract) -> Knowledge Base (RAG) -> LLM (Gemini/OpenAI) -> Database
```

Every layer in this diagram is now implemented. Full details in [docs/architecture/](docs/architecture/).

## Local setup

### Backend

```bash
cd backend
python -m venv .venv        # Python 3.11 recommended
./.venv/Scripts/activate    # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env        # fill in SECRET_KEY and GEMINI_API_KEY (or OPENAI_API_KEY)
uvicorn app.main:app --reload --port 8000
```

Runs at `http://localhost:8000`. Tables are created automatically on startup from the
SQLAlchemy models (no migration tool yet — this is fine while the schema is still moving).

Run tests (LLM calls are mocked, so no API key is needed to run the suite):

```bash
pytest
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Runs at `http://localhost:5173`.

## Environment variables

**Backend** (`backend/.env`, see `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string (SQLite by default) |
| `SECRET_KEY` | JWT signing secret — generate a real one, never commit it |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token config |
| `CORS_ALLOW_ORIGINS` | Comma-separated origins allowed to call the API |
| `LLM_PROVIDER` | `gemini` (default) or `openai` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | Required for the selected provider — chat, embeddings, and memory extraction all need this |
| `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` | Model overrides |
| `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RAG_TOP_K`, `RAG_MIN_SCORE` | RAG tuning |
| `MEMORY_CONTEXT_LIMIT`, `CONVERSATION_HISTORY_LIMIT` | How much memory/history gets fed into each chat turn |
| `MAX_UPLOAD_BYTES` | Document upload size cap |
| `LOG_LEVEL`, `LOG_DIR` | Logging config |

**Frontend** (`frontend/.env`, see `frontend/.env.example`):

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the backend API |

## Repository layout

```
Week5_Challenge/
├── backend/    FastAPI app (models, RAG, memory, LLM service, routers), tests
├── frontend/   React + Vite + TS app (chat UI, assistant/documents/memory panels)
└── docs/       architecture, research, evaluation, experiments, security, performance, builder-journal
```
