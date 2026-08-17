# Performance & Observability

Measured live on 2026-08-12 during the full QA pass (see
[docs/evaluation/README.md](../evaluation/README.md)), on localhost, SQLite, single dev
process — not production numbers.

## Measured latencies

| Operation | Latency | Notes |
|---|---|---|
| App startup (`Base.metadata.create_all` + FastAPI boot) | ~1-2s | From process start to "Application startup complete" in logs |
| `GET /api/health` | ~130ms | No DB write, trivial |
| `POST /api/auth/login` | ~760ms | Dominated by intentional `bcrypt` cost factor — this is correct, expected behavior, not a bug |
| Chat generation (`gemini-2.5-flash`, real call) | ~3-6s typical (e.g. 2.9s, 3.6s, 5.3s observed across several real calls) | Varies with response length and RAG/memory context size |
| Document upload (extract + chunk + embed, short `.txt`) | ~1-2s typical for short docs | One 13.6s outlier was actually a quota-retry delay on a concurrent call, not embedding latency itself |
| Semantic search / retrieval | Sub-second | Cosine similarity over chunk embeddings runs in-process with `numpy`; not a separate network call — the network-bound part is only the query embedding request |
| Memory retrieval (`get_context_memories`) | Sub-second | Plain indexed SQL query, no network call |

## Token usage & cost (real, from the dashboard)

Actual accumulated numbers from this QA session's live testing (`GET
/api/workspaces/{id}/dashboard`, `usage` block):

```json
{"total_input_tokens": 1475, "total_output_tokens": 339, "estimated_cost_usd": 0.0013}
```

Cost estimate comes from a hardcoded approximate pricing table
(`app/services/usage_service.py`) — directionally useful, not billing-accurate.

## Critical finding: Gemini free-tier quota

This is the single most important operational fact discovered during testing, and it
directly blocked further live LLM testing in this session:

- **`gemini-2.5-flash` free tier: 20 `generate_content` requests per day**, confirmed via a
  real `429 RESOURCE_EXHAUSTED` response with `quotaId:
  GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: '20'`. This is a **daily**
  cap, not the per-minute limit it might appear to be from a single error message — waiting
  60+ seconds did not clear it.
- **Update, 2026-08-17 (6 days later): re-tested and still blocked.** The original write-up
  assumed this would reset at the next UTC day boundary. It did not — an identical `429`
  with the same `quotaId` returned on a fresh request 6 days later, and the fallback
  provider path (`OPENAI_API_KEY`) was checked and found to hold the same placeholder value
  as the Gemini key, so there was no working alternate provider either. **This is now a
  confirmed persistent block on this specific API key/project**, not a transient daily
  limit — closing the remaining blocked evaluation scenarios/experiments needs a different
  API key or a paid tier, not more elapsed time.
- **`gemini-embedding-001` (used for document/query embeddings) is not subject to the same
  cap** — document uploads and RAG retrieval kept working correctly after the chat quota was
  exhausted. This means RAG ingestion/retrieval is far more resilient to free-tier limits
  than chat generation is.
- **This specific API key's account could not reach any other Gemini model** —
  `gemini-2.0-flash` is globally retired (`404`, "no longer available"), and
  `gemini-2.5-pro` / `gemini-2.5-flash-lite` both returned `404 "no longer available to new
  users"` (an account-specific restriction, not a global deprecation). `gemini-2.5-flash`
  was the only model this key could use at all.
- **Practical impact:** a single developer or small demo can exhaust the entire day's chat
  quota in a few minutes of active testing. This is a real production-readiness concern, not
  just a testing inconvenience — noted in Known Limitations.

## Logging

`app/core/logging_config.py` writes structured, timestamped logs to both console and
`logs/app.log`. Confirmed useful during this session: every LLM failure, quota error, and
skipped memory-extraction attempt was clearly visible with enough detail to diagnose root
cause, without ever logging secrets (verified via grep — see security review).
