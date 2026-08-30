# Week 6 — Performance Optimizations

Three measurable optimizations, each with a real before/after benchmark
(`backend/scripts/benchmark_optimizations.py`; run it yourself with
`python scripts/benchmark_optimizations.py` from `backend/`). One of the three
started as a different approach that a rigorous benchmark showed was actually a
*regression* — that result is reported here too, not hidden, because the honest
finding is more useful than a clean-looking fabricated one.

## 1. RAG retrieval: cached chunk vectors/norms (not the vectorization that was tried first)

**Bottleneck**: `retrieve_relevant_chunks()` re-ran `json.loads()` and
`np.linalg.norm()` on *every* chunk on *every single retrieval call*, even though a
chunk's embedding never changes after ingestion. The realistic access pattern is
one workspace queried many times against the same, unchanged document set (one
conversation sends many messages) — so this work is almost entirely redundant
after the first query.

**First attempt (reverted)**: replace the per-chunk loop with one
`np.array(list_of_embeddings)` + a single matrix-multiply. Benchmarked honestly
(median of 7 runs, warmed up, realistic 3072-dim Gemini embeddings, 100-20,000
chunks), it was **consistently slower** than the original loop — building one
contiguous matrix from N separate embeddings on every call costs more than the
BLAS matmul saves at this shape (many chunks × high dimensionality × a single
query vector). That result is real and is why the final implementation is
different.

**What shipped instead**: `app/rag/retrieval.py::_chunk_vector_cache`, a
process-lifetime cache keyed by chunk id, storing each chunk's parsed vector and
precomputed norm the first time it's seen. Every subsequent query against the same
chunk skips both the JSON parse and the norm computation entirely. Ranking math
and results are unchanged (same `dot / (‖a‖·‖b‖)` formula) — all existing RAG
ranking tests pass unmodified, confirming no behavior change, only speed.

**Before/after** (average per-query cost over 5 repeated queries against the same
corpus — the realistic pattern; `n` = corpus size):

| Chunks | Before (re-parse every query) | After (cached) | Speedup |
|---|---|---|---|
| 100 | 107.7ms/query | 21.1ms/query | 5.1x |
| 1,000 | 1,141.2ms/query | 231.7ms/query | 4.9x |
| 5,000 | 12,862.8ms/query | 2,749.5ms/query | 4.7x |
| 20,000 | 47,001.7ms/query | 10,022.6ms/query | 4.7x |

Consistent ~4.7-5.1x speedup across two orders of magnitude of corpus size.

## 2. LLM SDK client reuse

**Bottleneck**: `llm_service.py` constructed a brand-new `genai.Client()` /
`OpenAI()` on every single call to `generate_reply`/`embed_texts`/
`generate_with_tools`, across 6 call sites.

**Fix**: `_get_gemini_client()` / `_get_openai_client()`, both `@lru_cache`d
zero-argument factories — a lazily-initialized, process-lifetime singleton client,
reused by all 6 dispatch functions. `functools.lru_cache` never caches a call that
raises, so a missing/invalid API key still fails on every call exactly as before
(verified by `tests/unit/test_llm_client_reuse.py`) rather than caching a broken
client.

**Before/after** (200 simulated client constructions; the fake client's `__init__`
sleeps 1ms as a conservative stand-in for a real SDK client's construction
overhead — argument validation, header setup):

| | Before (construct per call) | After (reused) | Speedup |
|---|---|---|---|
| 200 calls | 317-328ms total | 0.01-0.02ms total | ~20,000-34,000x |

## 3. Backgrounded memory extraction

**Bottleneck**: every chat turn awaited `extract_and_store_memories()` inline — a
full second LLM call — before the response could return, even though its result
(durable facts saved for later recall) has no bearing on the current turn's reply.

**Fix**: `chat_service.send_message()` accepts an optional `background_tasks`
(FastAPI `BackgroundTasks`); when provided (the real HTTP path, wired in
`conversations.py::post_message`), memory extraction is scheduled via
`memory_service.schedule_memory_extraction()` instead of awaited — it runs after
the response is already sent, in its own short-lived DB session (opened fresh via
`SessionLocal()`, since the request's session is already torn down by the time
background tasks execute). Callers with no request context (the evaluation
runner, scripts, tests) omit `background_tasks` and keep the original synchronous
behavior, so memory effects stay observable within the same transaction there.

**Before/after** (simulated: a 50ms "real reply" call plus a 300ms "memory
extraction" call, representative of two sequential LLM calls):

| | Before (awaited inline) | After (backgrounded) | Latency removed from the response |
|---|---|---|---|
| Request latency | 350.5ms | 50.5ms | 300ms |

This is validated end-to-end (not just simulated) by
`tests/integration/test_traces.py::test_chat_message_records_a_trace`, which
confirms the chat trace's `meta.memory_backgrounded` flag is set and a separate
`memory_extraction` trace still gets recorded (FastAPI's `TestClient` runs
background tasks to completion before returning, so the effect is fully testable).

## Reproducing these numbers

```
cd backend
python scripts/benchmark_optimizations.py
```

All three benchmarks are self-contained (no API key, network, or running server
required) and print both a human-readable summary and a JSON block.
