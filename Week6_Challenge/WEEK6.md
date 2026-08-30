# Week 6 — Production AI Reliability & Evaluation Platform

## Project objective

Turn the Week 5 AI Workspace Platform into a system that can be *evaluated,
observed, and trusted* — not just used. Week 5 proved the product works;
Week 6 adds the evaluation harness, tracing/logging, guardrails, reliability
engineering, and a quality dashboard needed to answer "how well does it work,
how often does it fail, and is it safe?" with evidence instead of opinion.

## Week 5 foundation

Unmodified base: JWT auth, per-user workspace isolation enforced at the ORM
level, a configurable AI assistant per workspace, persistent multi-turn chat,
document RAG with citations, long-term memory, a prompt library, and six
reusable skills. See [PROJECT.md](PROJECT.md) for the full Week 5 write-up —
every Week 5 feature and test still passes unmodified (verified this phase).

## Architecture

```
FastAPI + SQLAlchemy 2.0 + SQLite (backend/app/)
  chat_service.py / agent/orchestrator.py   — plain chat vs. tool-calling agent mode
  guardrails/                               — input/output validation, injection detection, secrets
  core/retry.py                             — retry + timeout, shared by every LLM/tool call
  services/trace_service.py                 — spans + Trace rows, one per request
  evaluation/                               — dataset, deterministic checks, LLM judge, RAG/agent metrics, runner
  services/stats_service.py                 — cost/latency/reliability aggregation over traces

React 19 + Vite + TypeScript + Tailwind + recharts (frontend/src/)
  pages/workspace/{TraceViewerPage,GuardrailsPage,QualityDashboardPage}.tsx
```

Nothing here replaces Week 5's chat/RAG/memory pipeline — every new system
wraps or observes it (tracing wraps every call, guardrails gate the same
entry/exit points, the evaluation runner drives the same `send_message`/
`run_agent_turn` code a real user's request drives).

## Evaluation dataset and evaluators

`backend/app/evaluation/data/eval_dataset.json` — **68 cases** across 6
categories: `normal` (15), `difficult` (10), `ambiguous` (8), `tool_use` (10),
`rag` (10), `adversarial` (15). A checked-in, reviewable JSON file, not
database rows — test *definitions* stay separate from *results*.

Deterministic evaluators (`deterministic_evaluators.py`, 8 checks — exact/
keyword/regex match, tool selection, tool args, structured-output schema,
retrieval hit, citation presence, approval compliance, forbidden-action
check) run first; a violated `critical_failure_condition` (e.g. a leaked
secret) **always** overrides an otherwise-passing score.

## LLM-as-a-Judge

`app/evaluation/llm_judge.py` — 5 dimensions (correctness, relevance,
completeness, clarity, groundedness, each 1-5) plus `overall_score` and a
short `explanation`, schema-validated via Pydantic (a malformed response is
treated as a null score, never coerced). The judge prompt is versioned
(`JUDGE_PROMPT_VERSION = "v1"`, stored on every result) so a future prompt
rewrite can be regression-tested rather than silently invalidating old scores.
10 of the 68 cases are flagged for human-vs-judge comparison
(`human_comparison.py`); human scores are genuinely unfilled (`null`) —
never fabricated.

## RAG / Agent evaluation

RAG: hit rate, context relevance, groundedness, citation correctness,
unsupported-claim rate, plus explicit `retrieval_failure` / `generation_failure`
/ `success` / `unclassified` classification (`rag_metrics.py`).

Agent: intent, tool selection/argument accuracy, task completion, loop
count/limit, recovery from a tool error — computed from the real orchestrator
trace (`agent_metrics.py`). Planning/state/multi-agent metrics are explicitly
marked not-applicable for this single-tool-per-case, single-agent system,
rather than fabricated.

## Tracing and logging

Every request (chat, skill, agent turn, embedding, evaluation case) writes
one `Trace` row with a span timeline:
`request → input_validation → retrieval → model_call → memory_extraction → final_response`
(chat) or `request → input_validation → agent_decision → tool_call → tool_result → agent_decision → final_response`
(agent — tool_call/tool_result are separate spans this phase, tracking
dispatch vs. actual execution/outcome). Traces link back to their evaluation
run and test id (`evaluation_run_id`/`eval_case_id`). Structured JSON logs
(`app/core/logging_config.py`) carry a fixed event vocabulary
(`model_called`, `tool_selected`/`succeeded`/`failed`, `retry_attempted`,
`guardrail_triggered`, `evaluation_started`/`completed`, ...). API keys,
full request/response bodies, and chain-of-thought are never logged or traced
— only short previews and structured metadata.

## Quality Dashboard

`/workspaces/:id/quality-dashboard` — 6 tabs (Overview, RAG, Agent,
Reliability, Performance, Comparison), all backed by real trace/evaluation
data, no hard-coded values: task success rate, avg judge score, RAG
groundedness, tool selection accuracy, failure rate, successful/failed
request counts, retry/timeout rate, guardrail triggers, mean/median/P50/P95
latency, input/output/total tokens, request count, cost per request/total/
**per successful task** (`null`, never `0`, when undefined). Model/prompt-
version breakdowns are computed API-side; a UI filter control isn't built yet.

## Prompt / model comparison

3 real, distinct system-prompt versions (`v1` baseline, `v2` adds grounding +
injection resistance, `v3` further tightens groundedness + adds clarify-when-
ambiguous + tool-use guidance) — stored, versioned, and identifiable in every
trace and evaluation result. `compare_runs()` classifies every case as
improved/regressed/unchanged (including judge-score-only regressions), proven
correct against constructed data. **Honest limitation**: this environment's
only configured API key (Gemini) is currently rejected by the provider
(`403 PERMISSION_DENIED`, confirmed via a live call this phase) and no OpenAI
key exists, so no real prompt-quality or model-vs-model difference could be
measured — the comparison *mechanism* is real and tested; the *live signal*
is not available here. No fabricated results are reported anywhere.

## Guardrails and prompt-injection protection

Input guard (empty/oversized/injection-flagged text) and output guard
(system-prompt leakage, echoed injection, secret redaction) run on **both**
the plain-chat and agent paths. Default mode flags rather than blocks;
blocking mode exists and is tested. **25 distinct prompt-injection/agent-
security tests** (18 direct, 3 indirect/RAG-embedded, 4 new agent-mode
tool/approval attacks) covering every required attack category — see
[docs/security/prompt-injection-report.md](docs/security/prompt-injection-report.md)
for the full attack-type/input/expected/actual/blocked/severity table. One
real detection gap (a "disable safety checks" phrasing) was found and fixed
this phase.

## Tool security

4 real tools (`search_documents`, `run_skill`, `save_memory`,
`delete_document`), each assigned a risk level (low/low/medium/high) by
actual behavior. The high-risk tool requires human approval via a
server-side `PendingAction` gate — proven un-bypassable by disguised
phrasing or forged cross-tenant tool arguments (both are new tests this
phase). Enforcement is entirely server-side; the frontend approval UI is
just a view onto it.

## Failure handling, retries, timeouts

Tenacity-based exponential backoff (default 2 retries) with explicit
retryable (429/5xx/timeout/connection errors) vs. non-retryable
(400/401/403/invalid key/invalid argument) classification. Hard timeouts:
30s for LLM calls, 15s for tool execution (new this phase) — both enforced
independently of whatever the provider SDK itself honors. 9 failure
scenarios are tested (LLM outage, embedding outage, tool exception/timeout,
malformed tool-call JSON, DB error in a tool, rate limit, repeated agent
loop) — see [docs/reliability.md](docs/reliability.md). Agent loop
prevention: max 5 iterations + duplicate-call detection, both configurable.
5 graceful-degradation scenarios are tested (exceeds the required 3).

## Cost and latency tracking

Every request's tokens/model/estimated cost is recorded on its trace, priced
from one centralized, configurable table (`usage_service.py`) — an
approximation, explicitly labeled as such. `stats_service.py` computes
mean/median/P50/P95/P99 latency and cost per request / per successful task /
by model, and automatically ranks the slowest pipeline stage.

## Optimizations

3 real, shipped, benchmarked optimizations (implemented in an earlier phase,
re-verified this phase): RAG chunk-vector caching (~4.7-5.1x retrieval
speedup), LLM SDK client reuse (~20,000x reduction in per-call construction
overhead), backgrounded memory extraction (-300ms off response latency). One
honestly-reported non-improvement (a vectorization rewrite that was actually
*slower*, reverted) is disclosed rather than hidden — see
[docs/performance/optimizations.md](docs/performance/optimizations.md).

## Testing

Full backend suite and frontend build results are reported in the assistant's
final response for this task (not restated here to avoid the numbers drifting
out of sync with what was actually run). Test suites include:
`tests/evaluation/` (dataset, evaluators, judge, runner, comparison, prompt
regression, model comparison), `tests/security/` (prompt injection + agent
security), `tests/reliability/` (retry, timeout, degradation), `tests/agent/`
(orchestrator, tools), `tests/integration/` (traces, agent mode), `tests/api/`
(quality endpoints), plus every pre-existing Week 5 test.

## Known limitations

- **No working LLM API key in this environment** — the single biggest
  limitation; every evaluation/comparison result is mechanism-proven against
  a deterministic mock, not live model output.
- Human-review labels for the 10 flagged cases are genuinely unfilled.
- Dashboard date/model/prompt-version filters exist API-side, not yet as UI
  controls.
- Database-transaction failures outside tool execution (e.g. a commit
  failure persisting the user's own message) aren't specifically caught.
- No automatic cross-provider model fallback on primary-model failure.
- One harmless pre-existing pydantic `UserWarning` in a test's schema
  validation, unrelated to correctness.

## How to run the project

```bash
# Backend
cd Week6_Challenge/backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in a real GEMINI_API_KEY/OPENAI_API_KEY to use a live model
uvicorn app.main:app --reload

# Frontend
cd Week6_Challenge/frontend
npm install
npm run dev   # http://localhost:5173

# Tests
cd Week6_Challenge/backend && pytest -q
cd Week6_Challenge/frontend && npm run build   # tsc + vite build

# Evaluation / security
cd Week6_Challenge/backend
python scripts/seed_eval_workspace.py
python scripts/run_evaluation.py --no-judge
pytest tests/security tests/reliability -q
```

## Week 6 requirement checklist

See [docs/week6-final-summary.md](docs/week6-final-summary.md) for the
complete, requirement-by-requirement audit (✅ implemented+tested /
⚠️ implemented with limitation / ➖ not applicable, each with a stated
reason) — not duplicated here to keep this file the concise entry point.
