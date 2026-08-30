# Week 6 — Observability, Tracing & Structured Logging

Covers execution tracing, trace spans, the trace viewer, and structured
logging — built as one reusable system (`app/services/trace_service.py`,
`app/core/events.py`, `app/core/logging_config.py`, `app/core/tracing_middleware.py`),
not scattered ad-hoc logging calls. The same `traces` table this produces
already backs the Quality Dashboard's performance/reliability views, cost
analysis (`app/services/stats_service.py`), and the evaluation harness
(`app/evaluation/runner.py` reads the matching `Trace` row for latency/cost/
tokens) — one tracking system, reused everywhere, not duplicated per feature.

## Trace structure

Every AI request (chat turn, skill run, agent turn, embedding/ingestion call)
writes exactly one row to the `traces` table (`app/models/trace.py`):

| Field | Notes |
|---|---|
| `trace_id` | Shared by every trace/log line produced by the same HTTP request (set by `TracingMiddleware`, propagated via a contextvar). |
| `user_id`, `workspace_id`, `conversation_id`, `message_id` | Who/where — nullable, since not every trace has all of them (e.g. an embedding trace has no message). |
| `trace_type` | `chat` \| `skill` \| `embedding` \| `memory_extraction` \| `tool_call` \| `evaluation`. |
| `provider`, `model` | Which LLM backend actually served this call. |
| `input_tokens`, `output_tokens`, `cost_usd` | From the provider's own usage response, priced via `usage_service.estimate_cost_usd`. |
| `latency_ms` | Wall-clock time of the traced operation. |
| `status` | `success` \| `error` \| `timeout` \| `retried` \| `degraded`. |
| `error_message` | Server-side detail (never shown to the end user — see `user_facing_error()`). |
| `retry_count` | How many retry attempts `app/core/retry.py` made before this outcome. |
| `evaluation_run_id`, `eval_case_id` | Set only when this trace was produced by the evaluation runner — links a live trace back to the `evaluation_runs` row and the `eval_dataset.json` test_id that generated it (see "Evaluation ↔ trace linkage" below). Nullable everywhere else. |
| `meta` (JSON) | Everything else: `spans` (see below), `prompt_version`, `total_tokens`, truncated `input_preview`/`output_preview`, `retrieved_document_ids`, RAG chunk count, and trace-type-specific extras (e.g. `tool_call` traces carry `steps`, `iteration_count`, `hit_loop_limit`). |

There is no separate column for "the input" or "the raw output" — see
"What is intentionally not stored" below for why only short previews are kept.

## Span structure

Within one trace's `meta.spans`, the stages that actually ran are recorded in
order (not every request has every stage):

```
request -> input_validation -> retrieval -> model_call -> memory_extraction -> final_response          (chat turn)
request -> agent_decision -> tool_call -> tool_result -> agent_decision -> final_response               (agent turn, per tool used)
```

Each span is `{"id", "name", "started_at", "duration_ms", "status", "error",
"metadata": {...}}` — built by `app/services/trace_service.py::SpanRecorder`.
`id` is a short random identifier (not positional) so a specific step can be
referenced directly — e.g. from a future dashboard drill-down — and
`started_at` is an absolute ISO timestamp, so spans can be placed on a real
timeline rather than only ordered relative to each other.

`chat_service.send_message` records `request` -> `input_validation` (guardrail
input-guard check, before the message is even persisted) -> `retrieval` ->
`model_call` -> `memory_extraction` -> `final_response`.
`agent/orchestrator.run_agent_turn` records `request` -> `agent_decision` (one
per loop iteration) -> for each tool the model picks: `tool_call` (the
dispatch — 0ms marker recorded the instant the tool is chosen, metadata
includes the tool name and arguments) immediately followed by `tool_result`
(the actual execution — its `duration_ms` is the tool's real wall-clock time,
status `success`/`error`) -> another `agent_decision` -> ... -> `final_response`.
Splitting call from result (rather than one combined `tool_call` span) means
the trace viewer can show "the agent decided to call X" as a distinct,
zero-latency event from "X actually took 340ms and failed," which is the
distinction a reader needs when diagnosing a slow or failing tool.

A retrieval span's metadata includes `retrieved_document_ids`; an
`input_validation` span's metadata includes `triggered_patterns` (empty list
when nothing fired) and its status is `flagged` rather than `success` when
the input guard detected something but didn't block. This is what makes a
failure diagnosable without re-running the request: the trace viewer renders
this list directly as a step-by-step timeline.

## Evaluation ↔ trace linkage

Every case the evaluation runner (`app/evaluation/runner.py`) executes runs
through the exact same `chat_service.send_message` / `agent/orchestrator.run_agent_turn`
code paths as a live request, so it produces the exact same trace(s). After a
case finishes, `runner.py::_link_trace_to_eval` finds the trace(s) whose
`conversation_id` matches that case's scratch conversation and stamps them
with `evaluation_run_id` and `eval_case_id`. The full chain is then:

```
Evaluation Run (evaluation_runs.id)
  -> Test ID (eval_dataset.json test_id, e.g. "n01")
      -> Trace(s) (traces.evaluation_run_id / traces.eval_case_id)
          -> Agent Steps / Tool Calls (trace.meta.steps, trace.meta.spans)
          -> Retrieval (trace.meta.retrieved_document_ids, "retrieval" span)
          -> Final Result (trace.meta.output_preview, trace.status)
      -> Evaluation Result (evaluation_results row: judge_score, judge_prompt_version, passed, ...)
```

A single case can produce more than one trace (e.g. a `chat` trace plus a
synchronous `memory_extraction` trace, since the runner doesn't background
memory extraction) — all of them get linked, and `GET /api/workspaces/{id}/traces`
accepts `evaluation_run_id`/`eval_case_id` query params to pull every trace
for one run or one specific test_id.

## Trace viewer

`frontend/src/pages/workspace/TraceViewerPage.tsx` — a filterable table
(by `trace_type`/`status`) of every trace in a workspace; selecting one shows
its detail panel: trace id, type/status, provider/model, latency, tokens,
cost, retries, error (if any), and the `meta.spans` timeline rendered as a
list of named steps each showing duration/status/metadata, with the full raw
`meta` JSON available behind a collapsed `<details>` for anything the
formatted view doesn't surface. Deliberately simple/functional — this is not
the full Quality Dashboard (that comes in the next part).

## Structured logging

`app/core/events.py::log_event(logger, event, **fields)` emits one log record
per named event, and `app/core/logging_config.py::JSONFormatter` folds every
extra field into a single JSON line (`logs/app.jsonl`) — an event is queryable
by `event`/`trace_id`/any context field, not just grep-able free text. The
human-readable console/file log (`logs/app.log`) still gets a normal
`%(asctime)s | %(levelname)s | ...` line for the same record.

Fixed event vocabulary, each fired from the one real call site (not
duplicated per feature):

| Event | Fired from |
|---|---|
| `request_received` / `request_completed` | `TracingMiddleware` (method, path, status_code, duration_ms — never the request body) |
| `model_called` | `llm_service.generate_reply` / `generate_with_tools`, before dispatch |
| `retrieval_started` / `retrieval_completed` | `rag/retrieval.py::retrieve_relevant_chunks` (chunks scanned/returned, retrieved document ids) |
| `tool_selected` | `agent/orchestrator.py`, when the model picks a tool, before executing it |
| `tool_succeeded` / `tool_failed` | `agent/orchestrator.py`, after `execute_tool()` |
| `retry_attempted` | `core/retry.py`, via tenacity's `before_sleep` hook — fires once per actual retry, not once per final outcome |
| `guardrail_triggered` | `services/guardrail_service.py::record_guardrail_event`, only when `triggered=True` |
| `evaluation_started` | `evaluation/runner.py::run_evaluation`, once per run (`scope="run"`) — right after the `EvaluationRun` row is created |
| `evaluation_completed` | `evaluation/runner.py::run_case` (once per case, `scope="case"`) and `run_evaluation` (once per run, `scope="run"`, after the summary is computed) |

The `scope` field is what distinguishes a run-level `evaluation_started`/
`evaluation_completed` line (one per `POST .../evaluations/run` call) from the
per-case ones (one per test_id) — both share the event name so a single query
can find every evaluation-related log line, filtered further by `scope` when
run-level vs. case-level matters.

Every trace_id-bearing log line can be correlated back to its `Trace` row via
`trace_id` — the same id appears in the `X-Trace-Id` response header, every
log line for that request, and the `traces.trace_id` column.

## Security & Privacy for Observability

What is intentionally NOT stored in any trace, span, or log line:

- **API keys, passwords, or any credential material** — never logged or
  traced; the only place they exist is `backend/.env`, read once at process
  start via `pydantic-settings`. Span metadata (`triggered_patterns`, tool
  `arguments`, etc.) is built from application-level values, never from
  request headers or environment/config objects, so there is no code path
  that could accidentally serialize a secret into `meta`.
- **Full request/response bodies** — only a 200-character `input_preview`/
  `output_preview` is kept in trace `meta`, and only *after* the output-guard
  pass has already redacted any detected secrets (see
  `docs/evaluation/evaluation-foundation.md`'s guardrails section) — a preview
  can never contain a secret the guardrail caught.
- **Private chain-of-thought** — neither the assistant nor the LLM judge is
  ever asked to reveal step-by-step reasoning; the judge prompt explicitly
  asks for a short final `explanation` only (see
  `docs/evaluation/evaluation-foundation.md`'s judge section). Agent spans
  record *that* a decision happened (`agent_decision`, `chose_tool`) and *which*
  tool was picked, never the model's internal reasoning for picking it.
- **Full RAG chunk text in logs** — retrieval events log `retrieved_document_ids`
  and counts, not chunk content; the content itself lives in the `chunks`
  table and the (already-truncated) message `citations`, not duplicated into
  logs.
- **Tool call arguments are logged as-is, never sanitized beyond what the
  tool schema itself constrains** — since the current tool registry
  (`search_documents`, `run_skill`, `save_memory`, `delete_document`) only
  accepts workspace-scoped identifiers and short query strings (see
  `app/agent/tools.py`), not free-form secrets, this is safe today; a future
  tool accepting arbitrary user-supplied text would need its own redaction
  pass before being added to `tool_call` span metadata.

Access control: every trace, guardrail event, and evaluation endpoint is
scoped through the same `get_owned_workspace` dependency as the rest of the
API (`app/api/routers/traces.py`, `evaluations.py`) — a user can only ever
list or read traces/evaluation runs/human-review worklists that belong to a
workspace they own, exactly like every other Week 5 resource. The new
`evaluation_run_id`/`eval_case_id` trace columns and the human-review
worklist's `human_notes` field are free-text authored internally (by the
evaluation dataset or a human reviewer), never by an untrusted end user, and
are only ever returned to the owning workspace's authenticated user — they
carry no new exposure surface beyond what already existed for trace `meta`.

## Testing performed for this part

`pytest tests/unit/test_structured_logging.py` — confirms: `log_event()`
attaches the event name and fields as structured `extra` attributes;
`JSONFormatter` serializes them as top-level JSON keys and never crashes on
an unserializable value; a real chat HTTP request emits
`request_received`/`retrieval_started`/`retrieval_completed`/
`request_completed` in sequence; `model_called` fires from the real
`llm_service.generate_reply` (even when the subsequent provider call then
fails); a real agent turn emits `tool_selected` and `tool_succeeded`/
`tool_failed`; a transient failure followed by a successful retry emits
`retry_attempted`. Trace/span creation is additionally covered by
`tests/integration/test_traces.py` (now also asserting the `input_validation`
span in chat traces and the `tool_call`/`tool_result` split in agent traces),
`tests/agent/`, and `tests/integration/test_agent_mode_and_approvals.py`.

Evaluation-run ↔ trace linkage is covered by
`tests/evaluation/test_runner.py::test_traces_are_linked_back_to_the_evaluation_run_and_test_id`
(confirms every trace produced by a run carries the correct
`evaluation_run_id`/`eval_case_id`, and that filtering by `eval_case_id`
isolates exactly the traces for one test_id) and
`test_judge_prompt_version_is_stored_on_the_result` (confirms
`evaluation_results.judge_prompt_version` is populated from the judge's own
reported version, not hardcoded). The additive-only SQLite column migration
that introduced these new columns on an existing database is covered by
`tests/unit/test_lightweight_migrations.py`.
