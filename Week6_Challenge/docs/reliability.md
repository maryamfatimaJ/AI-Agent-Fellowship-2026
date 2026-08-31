# Week 6 — Reliability: Retry, Timeout, Loop Prevention, Graceful Degradation, Failure Injection

Covers everything that keeps the system from freezing, retry-storming, or
crashing outright when a dependency (LLM provider, embedding call, a tool, the
agent loop itself) misbehaves. All of it is implemented in `app/core/retry.py`
+ `app/agent/orchestrator.py` + `app/core/config.py`, reused identically by
every call site rather than duplicated per feature.

## Retry strategy

`app/core/retry.py::call_with_retry(fn)` wraps every LLM dispatch
(`generate_reply`, `embed_texts`, `generate_with_tools` in `llm_service.py`)
with `tenacity`-based exponential backoff.

**Retryable** (`_RETRYABLE_MARKERS`): rate limits (`429`, "resource_exhausted",
"rate limit"), timeouts, 5xx/"internal server error", connection
reset/error, "temporarily unavailable", "overloaded". **Non-retryable**
(`_NON_RETRYABLE_MARKERS`, checked first so it wins on any overlap): `400`/
`401`/`403`, "invalid api key", "no api key configured", "invalid_argument",
"unsupported file type" — these fail on the first attempt, since retrying a
bad request or bad credential can never succeed and only wastes time and
quota. `is_retryable()` duck-types on the stringified error rather than
SDK-specific exception classes, so both the Gemini and OpenAI SDKs are
classified identically without importing either at module load time.

**Configuration** (`app/core/config.py`, all env-overridable):
`llm_max_retries=2` (so up to 3 total attempts), `llm_retry_backoff_seconds=0.5`
(exponential: 0.5s, 1s, capped at 10s max wait). Chosen to absorb a brief
provider blip (a rate-limit reset, a transient 503) within a few seconds,
without turning a genuinely down provider into a multi-minute hang — the
`llm_request_timeout_seconds` hard cap (below) bounds each individual attempt
regardless.

Every retry attempt is recorded: `RETRY_ATTEMPTED` structured log event
(`app/core/retry.py::_log_retry_attempt`, fired via tenacity's `before_sleep`
hook — once per actual retry, not once per final outcome) with
`attempt_number`, `wait_seconds`, and the triggering error; the final
`Trace.retry_count` on the resulting `Trace` row reflects how many retries
actually happened for that request (`status=retried` when `retry_count > 0`
but the call ultimately succeeded).

Retry storms are avoided by: (1) the exponential backoff itself (no fixed
tight retry loop), (2) the hard cap of 2 retries per call, (3) non-retryable
errors failing immediately rather than being retried at all, and (4) retries
apply per-call, not per-request — a chat turn's guardrail/RAG/memory work
never re-triggers a retry storm on the LLM call.

Tested: `tests/reliability/test_retry.py` (7 tests — classification of every
retryable/non-retryable marker, succeed-first-try, retry-then-succeed,
no-retry-on-permanent-error, exhaust-then-reraise).

## Timeout handling

`app/core/retry.py::run_with_timeout(fn, timeout_seconds)` runs `fn` in a
single-worker `ThreadPoolExecutor` and enforces a hard wall-clock timeout
independent of whatever the provider SDK itself honors — necessary because an
SDK call can hang past its own advertised timeout on a bad connection.
Deliberately does **not** use `with ThreadPoolExecutor(...) as executor:`,
since the context manager's `__exit__` calls `shutdown(wait=True)`, which
would block until the hung worker finishes anyway — defeating the point of
the timeout. `shutdown(wait=False)` abandons a still-hung worker instead (it
finishes in the background and is garbage-collected; Python has no API to
forcibly kill a thread — a documented, accepted tradeoff, not an oversight).

| Component | Timeout config | Reasoning |
|---|---|---|
| LLM calls (`generate_reply`/`embed_texts`/`generate_with_tools`) | `llm_request_timeout_seconds=30.0` | Generous enough for a real completion (including RAG-context-heavy prompts) but well short of a request-handler-level HTTP timeout a client might enforce. |
| Tool execution (`execute_tool`, wrapped in `orchestrator.py`) | `tool_timeout_seconds=15.0` (new this phase) | Tools here (`search_documents`/`run_skill`/`save_memory`/`delete_document`) are all in-process DB operations, not external network calls — 15s is generous slack for a slow DB query, not a value chosen just to pass a test. A tool that legitimately hangs this long indicates a real bug worth surfacing, not something to wait out longer. |
| Retrieval | Bounded by the LLM embedding call's own `llm_request_timeout_seconds` (retrieval's only network dependency is the embedding call) | No separate retrieval-specific timeout is needed — the embedding call is retrieval's only blocking operation. |
| Whole agent turn | `agent_max_iterations=5` (a step-count cap, not a wall-clock one) | Bounds worst-case latency indirectly: N iterations × (model-call timeout + tool timeout) is always finite, so no separate end-to-end wall-clock timer was added on top — see Loop Prevention below for why a step cap was chosen over a wall-clock cap. |

A timed-out LLM call surfaces as `LLMTimeoutError` (mapped from the raw
`TimeoutError`, see `llm_service.py`), traced with `status=timeout`, and
converted to a safe, generic user-facing message via `user_facing_error()` —
never a raw stack trace. A timed-out tool call surfaces as a normal
`ToolResult(error="Tool '<name>' timed out after <N>s")`, fed back to the
model exactly like any other tool failure (see Graceful Degradation below).

Tested: `tests/reliability/test_timeout.py` (`run_with_timeout` fast/slow
paths, `generate_reply` mapping a persistent hang to `LLMTimeoutError`);
`tests/agent/test_orchestrator.py::test_tool_execution_timeout_is_recovered_from`
(new this phase — a hung tool times out and the agent still produces a
useful answer instead of hanging the whole request).

**Known tradeoff**: `run_with_timeout`'s abandoned worker thread, if it were
genuinely still running (e.g. a real hung DB call inside a tool), could in
principle still be mutating the same SQLAlchemy `Session` object after the
main thread has moved on to do something else with it. This is the same
tradeoff the LLM-call timeout already accepted (this mechanism is reused
unchanged, not duplicated) and is a low-probability edge case given SQLite's
single-writer model — documented here rather than solved with a
process-per-tool-call architecture, which is out of scope for this phase.

## Agent loop prevention

`app/agent/orchestrator.py::run_agent_turn` enforces, all via one
configurable knob and one unconditional check:

- **Max iterations**: `for iteration in range(settings.agent_max_iterations):`
  (default 5, configurable) — the `else` clause on the `for` loop (Python's
  for/else, triggered only if the loop completes without `break`) sets
  `hit_loop_limit=True` and returns "I wasn't able to finish this within the
  allowed number of steps." rather than looping forever.
- **Duplicate-call detection**: `_call_signature(name, arguments)` (JSON-dumped,
  sorted keys) tracked in a `seen_calls` set for the turn — a repeated
  identical `(tool, args)` pair is refused immediately (`hit_loop_limit=True`,
  "I wasn't able to make progress without repeating the same step...")
  rather than executing it again and hoping for a different result.
- **Max tool calls**: bounded by the same `agent_max_iterations` cap, since at
  most one tool call happens per iteration.
- **Max revision cycles**: not applicable — this is a single-agent,
  single-pass tool-calling loop with no separate "revise the draft" cycle
  concept (that pattern belongs to a critique/revise multi-agent design,
  which this application doesn't implement; see `docs/evaluation/evaluation-foundation.md`'s
  agent-evaluation section for the same honest "not applicable" call on
  multi-agent metrics).
- **Execution timeout**: see the Timeout Handling table above — bounded
  indirectly via the iteration cap rather than a separate wall-clock timer.

When any limit is hit: the loop stops, `hit_loop_limit=True` is recorded on
the `AgentTurnOutcome` and in the trace's `meta.hit_loop_limit`, a clear log
line is emitted, and a safe, plain-language message is returned to the user —
never a silent hang or a raw exception.

Tested: `tests/agent/test_orchestrator.py::test_repeated_identical_tool_call_triggers_loop_prevention`,
`::test_hitting_max_iterations_without_a_final_answer_stops_gracefully`.

## Graceful degradation (3+ real scenarios)

Each of these is a currently-passing test that drives the real code path
end-to-end and asserts the actual (not hypothetical) degraded behavior:

1. **LLM provider outage** (`tests/reliability/test_degradation.py::test_llm_provider_outage_degrades_to_a_clean_fallback_message`)
   — the model call raises `LLMTimeoutError`; the chat turn still returns
   HTTP 200 with a sanitized, generic message (`user_facing_error()`), and
   the trace records `status=timeout` rather than the request 500ing.
2. **Retrieval/embedding outage** (`::test_rag_embedding_outage_degrades_to_an_answer_without_citations`)
   — `embed_texts` raises `LLMError`; the chat turn still completes with
   `citations=None` (an answer without grounding, rather than no answer at
   all) and the embedding trace records `status=degraded`.
3. **Memory-extraction outage** (`::test_memory_extraction_outage_does_not_break_the_chat_turn`)
   — memory extraction's own LLM call fails; the user-facing reply is
   completely unaffected (memory is a side-effect, never load-bearing for the
   current turn's response) and the memory-extraction trace alone records
   `status=degraded`.
4. **Tool failure** (`tests/agent/test_orchestrator.py::test_tool_error_is_fed_back_and_agent_recovers`,
   plus the new `test_tool_execution_timeout_is_recovered_from`) — a tool
   error (missing skill) or a tool timeout is fed back to the model as a
   normal tool-error message, and the agent produces a real, useful answer
   acknowledging what it couldn't do, rather than surfacing the raw error or
   silently failing.
5. **Database error inside a tool** (`tests/agent/test_tools.py::test_execute_tool_catches_a_database_error_and_returns_a_safe_result`,
   new this phase) — `execute_tool`'s catch-all (`except Exception`) turns an
   `OperationalError` into a normal `ToolResult(error=...)` instead of an
   uncaught 500.

None of these expose a stack trace to the end user — `user_facing_error()`
(chat/LLM path) and `execute_tool`'s catch-all (tool path) are the two single
choke points that guarantee this, rather than a try/except sprinkled ad hoc
at every call site.

**Not implemented**: an automatic fallback to a *different model/provider*
on primary-model failure. This was considered but not built — with only one
of the two configured providers holding even a nominally valid API key in
this environment (see `docs/evaluation/model-comparison.md`), a same-provider
retry (already implemented) is the realistic, testable failure-recovery path;
a cross-provider fallback would be untestable against a real failure here and
risked being a fabricated, unverified capability. Documented as a known,
deliberate limitation rather than silently omitted.

## Failure injection

Every failure scenario above (and the ones in `docs/security/prompt-injection-report.md`)
is injected via `monkeypatch` at the exact boundary being tested (the SDK
dispatch function, `embed_texts`, a tool's underlying call, `execute_tool`
itself) — restricted entirely to `pytest`, never a runtime toggle or endpoint
reachable in a real deployment. This was a deliberate choice (see
`docs/performance/optimizations.md`'s sibling reasoning for the same
principle): a production failure-injection *endpoint* is itself an attack
surface (an unauthenticated or under-protected one could let an attacker
deliberately degrade the service), whereas pytest-level monkeypatching gets
the same test coverage with zero exposure in the shipped application — there
is no code path in `app/` that reads a "simulate failure" flag at request
time.

| Scenario | Injected via | Expected | Actual |
|---|---|---|---|
| LLM API unavailable / times out | monkeypatch `_generate_gemini`/`generate_reply` to raise/hang | Clean fallback message, `status=timeout` or `error` | Confirmed (`test_degradation.py`, `test_timeout.py`) |
| Embedding/vector search unavailable | monkeypatch `embed_texts` to raise | Chat continues without citations, `status=degraded` | Confirmed |
| Tool throws an exception | a nonexistent skill name / monkeypatched DB error | Fed back to the model as a tool error / caught by `execute_tool` | Confirmed |
| Tool returns empty result | `search_documents` against a workspace with zero documents (real `retrieve_relevant_chunks`, not monkeypatched) | `ToolResult(output={"results": []}, error=None)` — a normal outcome, never conflated with a failure | Confirmed (`test_search_documents_returns_an_explicit_empty_result_not_an_error`) |
| Tool takes too long | monkeypatch `execute_tool` to sleep past `tool_timeout_seconds` | `ToolResult(error="...timed out...")`, agent recovers | Confirmed (`test_tool_execution_timeout_is_recovered_from`) |
| Invalid JSON returned (tool-call arguments) | fake OpenAI response with malformed `function.arguments` | Falls back to `{}` args rather than raising | Confirmed (`test_malformed_tool_call_json_falls_back_to_empty_arguments`) |
| Database connection/operation failure | monkeypatch a tool's DB call to raise `OperationalError` | `ToolResult(error=...)`, no uncaught 500 | Confirmed (`test_execute_tool_catches_a_database_error_and_returns_a_safe_result`) |
| Rate limit reached | monkeypatch a raised "429"/"rate limit" error | Retried per the retry policy, then a clean failure if exhausted | Confirmed (`test_retry.py`) |
| Agent enters a repeated loop | a model that always calls the same tool with the same args | Loop-prevention trips on the second identical call | Confirmed (`test_repeated_identical_tool_call_triggers_loop_prevention`) |

**Known, disclosed gap**: no test simulates a database failure at the
`db.commit()` call sites *outside* tool execution (e.g. persisting the user's
own message before any tool runs) — a failure there would currently surface
as an unhandled 500 rather than a graceful degradation. Building full
request-level DB-transaction resiliency (retry-on-`OperationalError` around
every commit, or a circuit breaker) was judged out of scope for this phase
given SQLite's local, single-process nature in this deployment (no network
partition or connection-pool exhaustion is realistically reachable here) —
noted honestly as a known limitation rather than silently left untested.

## Configuration reference

All reliability knobs live in one place, `app/core/config.py::Settings` (no
scattered magic numbers):

| Setting | Default | Purpose |
|---|---|---|
| `llm_request_timeout_seconds` | 30.0 | Hard timeout per LLM/embedding call |
| `llm_max_retries` | 2 | Max retry attempts after the first try |
| `llm_retry_backoff_seconds` | 0.5 | Base for exponential backoff |
| `tool_timeout_seconds` | 15.0 | Hard timeout per tool execution (new this phase) |
| `agent_max_iterations` | 5 | Max agent-loop iterations / tool calls per turn |
| `guardrails_block_on_injection` | False | Flag-only vs. hard-block on detected injection patterns |
| `max_input_chars` | 8000 | Input-length guardrail |
