# Part 2 — Core AI Workspace

**Date:** 2026-08-10

## Decisions made and why

- **RAG storage: embeddings in SQL + Python cosine similarity, no vector DB.** Consistent
  with the Part 1 schema note that `Chunk.embedding` becomes `pgvector` later. Chroma
  (used in Week 2) was considered and rejected — extra service/dependency weight the
  brief explicitly warns against ("don't introduce unnecessary technologies").
- **One assistant per workspace, auto-created on workspace creation.** The DB model
  supports many assistants per workspace for future flexibility, but the API only exposes
  get-or-create-the-one-assistant, matching what the brief actually asked for.
- **Memory: manual pin + best-effort LLM auto-extraction after each turn.** Extraction runs
  synchronously today (no task queue exists yet) and is wrapped in try/except so a bad
  extraction never breaks the chat response the user is waiting on.
- **RAG relevance threshold (`RAG_MIN_SCORE=0.65`) added after live testing caught a real
  bug**: retrieval always injected top-k chunks regardless of relevance, so a message with
  nothing to do with the uploaded documents still got document snippets stuffed into the
  prompt, and the model produced a garbled, context-confused reply. Fixed by only injecting
  chunks that clear a minimum cosine similarity. The threshold value is a first pass, not
  calibrated against eval data — flagged for Part 3.
- **No streaming.** Chat is request/response, not token-streamed. Simpler and more reliable
  for this part; the brief's "excellent chat experience" was interpreted as UI polish
  (empty/loading states, citations, search) rather than a hard streaming requirement.

## What was tested live (not just mocked)

Real Gemini calls were used for: chat generation respecting per-assistant temperature/style/
system-prompt, document embedding on upload, query embedding + cosine retrieval producing
correctly-ranked citations, and LLM-based memory fact extraction. Verified: register/login,
workspace + assistant CRUD, multi-turn chat, document upload → cited Q&A, manual memory pin,
automatic memory extraction, data survives a full backend process restart (real DB
persistence, not just in-memory), and cross-user 404 isolation on every new workspace-scoped
endpoint (assistant, conversations, documents, memory).

## Known limitations for Part 3

- RAG relevance threshold is a heuristic guess, not tuned against real evaluation scenarios.
- No streaming responses.
- Memory retrieval for context injection is recency/pinned-first, not semantic — a memory
  embedding index would let "relevant to this specific message" beat "most recent."
- No automated frontend/browser test — verified via API-level testing and manual review of
  the built bundle; no headless browser tool is available in this environment.
