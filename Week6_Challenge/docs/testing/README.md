# Testing

This is a short index into how automated testing works in this project. For the
category-by-category PASS/FAIL matrix (which requirement maps to which test), see
[Section 13 of docs/evaluation/README.md](../evaluation/README.md#13-automated-testing) —
it is not duplicated here.

## Running the suite

```bash
cd Week5_Challenge/backend
python -m pytest tests/ -q
```

As of 2026-08-18: **55 tests, all passing**, in `backend/tests/` across three directories:

| Directory | Files | Purpose |
|---|---|---|
| `tests/api/` | `test_auth.py`, `test_assistant.py`, `test_conversations.py`, `test_memory.py`, `test_prompts.py`, `test_skills.py`, `test_pinned_messages.py`, `test_health.py` | One file per resource router, exercised through FastAPI's `TestClient` |
| `tests/integration/` | `test_workspace_isolation.py`, `test_workspace_rename_delete.py`, `test_documents_rag.py`, `test_dashboard.py` | Cross-cutting flows: ownership isolation, cascading deletes verified via direct DB queries, document ingestion + RAG retrieval end-to-end |
| `tests/unit/` | `test_security.py`, `test_rate_limit.py` | Pure functions (JWT/hashing) and the rate limiter in isolation |

## How the fixtures work (`tests/conftest.py`)

- **`client`** — a `TestClient` backed by a fresh in-memory SQLite DB per test (`db_session`
  fixture, `StaticPool` so the same connection persists for the test's duration). No test
  touches the real `app.db` file.
- **`mock_llm`** (autouse via `client`) — patches every LLM call site
  (`chat_service.generate_reply`, `skill_service.generate_reply`,
  `memory_service.generate_reply`, `rag.retrieval.embed_texts`) with deterministic fakes.
  The mock embedder assigns a keyword-count vector per text (`MOCK_VOCAB` in `conftest.py`),
  which is what lets `test_documents_rag.py` assert real ranking behavior (a chunk
  mentioning "refund" outranks one that doesn't) without any network call or real API key.
- **`_reset_rate_limiter`** (autouse) — disables `slowapi` for every test except
  `tests/unit/test_rate_limit.py`, which explicitly re-enables it to prove the limit
  actually engages. Without this, the shared-IP-key nature of `TestClient` would exhaust the
  login/register rate limits within a single pytest run and fail unrelated tests.

## What's deliberately not covered by this suite

- Real LLM output quality/content — the suite proves the *pipeline* works (retrieval,
  citation, memory injection, persistence) with mocked model output, not that a real Gemini
  response is good. Live-model behavior is covered separately and manually in
  [docs/experiments/README.md](../experiments/README.md) and
  [docs/evaluation/README.md](../evaluation/README.md), including real quota/error
  handling that can't be exercised against a mock.
- Frontend component/UI tests — none exist; frontend correctness in this project has been
  verified via API-level testing and code review, not a browser test runner (see the UI/UX
  section of the evaluation report for why: no headless browser tool available in this
  environment).
