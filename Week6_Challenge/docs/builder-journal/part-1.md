# Part 1 — Audit, Architecture & Foundation

**Date:** 2026-08-10

## Decisions made and why

- **Frontend: React over Streamlit** — the platform needs real multi-user auth flows and
  persistent multi-page navigation (workspaces, later conversations); Streamlit's rerun model
  fights that. Continues Week 4's unwired React/Vite/Tailwind investment instead of duplicating it.
- **Database: SQLite now, Postgres/Supabase-ready** — zero-setup local dev, schema written to be
  portable (string-UUID PKs, no SQLite-only types) so the swap is a config change.
- **Backend Python 3.11, not the system default 3.14** — 3.14 is too new; risked missing wheels
  for `bcrypt`/`pydantic-core`. Confirmed 3.11 was already installed on the machine.
- **Auth: `pyjwt` + `bcrypt` directly, not `passlib`** — avoids passlib's known bcrypt-backend
  version friction.
- **Narrow Part 1 API surface** — only `auth` and `workspaces` got working endpoints. All other
  entities (assistants, conversations, messages, documents, chunks, prompt templates, skills,
  memory, settings, logs, usage) got ORM models + relationships only, per the stop condition.

## What was reused vs. built fresh

Nothing was copied from Weeks 1-4 directly (no prior week had auth, a real DB, or a workspace
concept), but the *shape* of Week 4's FastAPI layering (routers -> services -> models) and
Week 3's repository/schema-separation conventions carried over. See `docs/architecture/overview.md`.

## Flagged, not fixed

Week 2's committed `.env` contains real `GEMINI_API_KEY`/`SECRET_KEY` values. Not touched
(out of scope for Week 5), but should be rotated.
