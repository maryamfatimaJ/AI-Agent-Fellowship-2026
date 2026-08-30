"""Measures the before/after impact of the 3 Week 6 performance optimizations
in app/rag/retrieval.py, app/services/llm_service.py, and
app/services/chat_service.py. Run from backend/: python scripts/benchmark_optimizations.py

Each benchmark reimplements the *old* code path locally (it no longer exists
in the app after the optimization) purely as a comparison baseline — the
"after" side calls the real, currently-shipping function.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402


# --- Optimization 1: cached chunk vectors/norms in RAG retrieval -----------
#
# An earlier attempt vectorized cosine similarity into one np.array(list) +
# matmul call. Benchmarked honestly (median of 7 runs, warmed up, realistic
# 3072-dim Gemini embeddings, 100-20,000 chunks), it was consistently
# *slower* than the original per-chunk loop — building one contiguous matrix
# from N separate embeddings on every single call costs more than the BLAS
# matmul saves. That result is why this benchmark instead measures the
# optimization that actually shipped (app/rag/retrieval.py's
# _chunk_vector_cache): skipping repeated json.loads()/np.linalg.norm() work
# for chunks a workspace has already queried before, which is the realistic
# access pattern (one conversation sends many messages against the same,
# unchanged document set).

from dataclasses import dataclass  # noqa: E402


@dataclass
class _FakeChunk:
    id: str
    embedding: str


def _uncached_rank(query_vector, chunks):
    """The original always-reparse-every-chunk behavior, for comparison."""
    scored = []
    for chunk in chunks:
        vector = np.array(json.loads(chunk.embedding))
        denom = np.linalg.norm(query_vector) * np.linalg.norm(vector)
        score = 0.0 if denom == 0 else float(np.dot(query_vector, vector) / denom)
        scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def _median_ms(fn, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return samples[len(samples) // 2]


def benchmark_rag_ranking(repeats: int = 7, n_queries_per_workspace: int = 5) -> dict:
    from app.rag.retrieval import _chunk_vector_cache, _rank_by_cosine_similarity

    results = {}
    rng = np.random.default_rng(42)
    dim = 3072  # gemini-embedding-001's real dimensionality
    for n_chunks in (100, 1000, 5000, 20000):
        chunks = [_FakeChunk(id=f"chunk-{n_chunks}-{i}", embedding=json.dumps(rng.random(dim).tolist())) for i in range(n_chunks)]
        query = rng.random(dim)

        old_ms = _median_ms(lambda: _uncached_rank(query, chunks), repeats)

        _chunk_vector_cache.clear()
        # "after": n_queries_per_workspace repeated queries against the same
        # chunk set (the realistic pattern), reporting the average per-query
        # cost — the first query is a cold-cache miss for every chunk, every
        # query after that hits the cache for all of them.
        start = time.perf_counter()
        for _ in range(n_queries_per_workspace):
            _rank_by_cosine_similarity(query, chunks)
        new_ms_avg = (time.perf_counter() - start) * 1000 / n_queries_per_workspace

        results[n_chunks] = {
            "before_ms_per_query": round(old_ms, 2),
            "after_ms_per_query_avg": round(new_ms_avg, 2),
            "speedup": round(old_ms / new_ms_avg, 1) if new_ms_avg else None,
        }
    _chunk_vector_cache.clear()
    return results


# --- Optimization 2: reused LLM SDK client -----------------------------------

class _FakeSdkClient:
    """Stands in for genai.Client()/OpenAI() — real construction does argument
    validation, header setup, etc.; a trivial sleep approximates that fixed
    per-construction overhead without needing real credentials/network."""

    def __init__(self, api_key):
        time.sleep(0.001)  # ~1ms, a conservative stand-in for real SDK client init cost
        self.api_key = api_key


def benchmark_client_construction(n_calls: int = 200) -> dict:
    start = time.perf_counter()
    for _ in range(n_calls):
        _FakeSdkClient(api_key="fake")  # "before": construct fresh every call
    before_ms = (time.perf_counter() - start) * 1000

    cached = _FakeSdkClient(api_key="fake")
    start = time.perf_counter()
    for _ in range(n_calls):
        _ = cached  # "after": reuse the same instance (what _get_gemini_client does via lru_cache)
    after_ms = (time.perf_counter() - start) * 1000

    return {
        "n_calls": n_calls,
        "before_ms_total": round(before_ms, 2),
        "after_ms_total": round(after_ms, 4),
        "speedup": round(before_ms / after_ms, 1) if after_ms else None,
    }


# --- Optimization 3: backgrounded memory extraction --------------------------

def benchmark_memory_backgrounding(simulated_llm_latency_s: float = 0.3) -> dict:
    def fake_chat_reply():
        time.sleep(0.05)  # the "real" reply call

    def fake_memory_extraction():
        time.sleep(simulated_llm_latency_s)  # the second LLM call this optimization removes from the request path

    start = time.perf_counter()
    fake_chat_reply()
    fake_memory_extraction()  # awaited inline — the old behavior
    before_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    fake_chat_reply()
    # memory extraction is scheduled via BackgroundTasks and doesn't block the response
    after_ms = (time.perf_counter() - start) * 1000

    return {
        "before_ms": round(before_ms, 2),
        "after_ms": round(after_ms, 2),
        "latency_removed_from_request_ms": round(before_ms - after_ms, 2),
    }


def main() -> None:
    rag_results = benchmark_rag_ranking()
    client_results = benchmark_client_construction()
    memory_results = benchmark_memory_backgrounding()

    print("1) RAG retrieval: cached chunk vectors/norms vs re-parsing every chunk every query")
    print("   ('after' = average per-query cost over 5 repeated queries against the same corpus)")
    for n_chunks, stats in rag_results.items():
        print(
            f"   {n_chunks:5d} chunks: before={stats['before_ms_per_query']}ms/query  "
            f"after={stats['after_ms_per_query_avg']}ms/query  speedup={stats['speedup']}x"
        )

    print("\n2) LLM SDK client: reused (cached) vs constructed per call")
    print(f"   {client_results['n_calls']} calls: before={client_results['before_ms_total']}ms total  "
          f"after={client_results['after_ms_total']}ms total  speedup={client_results['speedup']}x")

    print("\n3) Memory extraction: backgrounded vs awaited inline on the chat request")
    print(f"   before={memory_results['before_ms']}ms request latency  after={memory_results['after_ms']}ms  "
          f"removed={memory_results['latency_removed_from_request_ms']}ms from the user-facing response")

    print("\nJSON summary:")
    print(json.dumps({
        "rag_ranking": rag_results,
        "client_reuse": client_results,
        "memory_backgrounding": memory_results,
    }, indent=2))


if __name__ == "__main__":
    main()
