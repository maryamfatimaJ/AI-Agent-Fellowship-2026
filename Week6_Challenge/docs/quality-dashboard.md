# Quality Dashboard

`frontend/src/pages/workspace/QualityDashboardPage.tsx`, six tabs, backed
entirely by `app/api/routers/quality.py` + `app/api/routers/evaluations.py` +
`app/services/stats_service.py` — no second/parallel metrics system, no
hard-coded dashboard values. Every number rendered is a live query result at
page-load time.

## Metrics coverage against the spec

| Required metric | Where it's shown | Backed by |
|---|---|---|
| Task Success Rate | Overview tab | `EvaluationRun.summary.overall_pass_rate` (latest completed run) |
| Average Judge Score | Overview tab | `_avg_judge_score()` — mean of per-category `avg_judge_score` |
| RAG Groundedness | RAG tab | `rag_metrics.avg_groundedness` (from the latest run's aggregated RAG metrics) |
| Tool Selection Accuracy | Agent tab | `agent_metrics.tool_selection_accuracy` |
| Failure Rate | Overview tab | `performance.reliability.error_rate` |
| Successful Requests | Reliability & Performance tabs (new this phase) | `stats_service.get_performance_summary().successful_requests` |
| Failed Requests | Reliability & Performance tabs (new this phase) | `...failed_requests` |
| Retry Rate | Reliability tab | `performance.reliability.retry_rate` |
| Timeout Rate | Reliability tab | `performance.reliability.timeout_rate` |
| Guardrail Triggers | Overview + Reliability tabs | `guardrail_trigger_count`, `guardrail_events_by_type`/`by_action` |
| Average Latency | Performance tab | `latency_ms.mean` |
| Median Latency | Performance tab (new this phase) | `latency_ms.median` |
| P50 Latency | Performance tab | `latency_ms.p50` (numerically equal to median — both shown per the spec's literal wording) |
| P95 Latency | Overview + Performance tabs | `latency_ms.p95` |
| Input Tokens | Performance tab (new this phase) | `tokens.input` |
| Output Tokens | Performance tab (new this phase) | `tokens.output` |
| Total Tokens | Overview + Performance tabs | `tokens.total` |
| Request Count | Overview + Performance tabs | `n_requests` |
| Average Cost per Request | Performance tab | `cost.per_request_usd` |
| Total Estimated Cost | Overview + Performance tabs | `cost.total_usd` |
| Cost per Successful Task | Performance tab | `cost.per_successful_task_usd` — **`null`, not `0`, when there are zero successful tasks** (see below) |

## Breakdown/filter support

- **By model**: `by_model` breakdown always computed and rendered ("Cost by
  model" chart, Performance tab); `GET .../quality/{overview,performance,reliability}`
  all accept an optional `?model=` query param (new this phase) to narrow the
  whole aggregation to one model.
- **By prompt version**: `by_prompt_version` breakdown (new this phase,
  `stats_service.py`) computed from each trace's `meta.prompt_version` —
  returned by the API (`overview`/`performance`) but **not yet rendered as
  its own panel in the UI** — an implemented-with-limitation item, since
  building a full prompt-version filter control was judged lower priority
  than closing the other, more load-bearing gaps this phase (agent-path
  guardrails, tool timeout, prompt-version-to-API wiring). The data is one
  API call away from a UI panel.
- **By date**: `?since=`/`?until=` query params (new this phase) on the same
  three endpoints, filtering by `Trace.created_at` — implemented API-side;
  no date-range picker exists yet in the dashboard UI (same
  implemented-with-limitation status as prompt-version filtering).
- **By test category**: available per evaluation run via
  `EvaluationRun.summary.by_category` (already rendered indirectly — the
  RAG/Agent tabs are themselves category-scoped views) and via the
  Comparison tab's per-case table, which shows each case's `category`
  alongside its improved/regressed/unchanged status.
- **By evaluation run**: the Comparison tab's run-A/run-B selectors already
  let you pick any two runs (which may differ by prompt version, model, or
  date) and diff them case-by-case.

## Distinguishing unavailable from zero

This was a deliberate, tested design decision, not an oversight:
`stats_service.get_performance_summary()`'s `cost.per_successful_task_usd` is
`None` (rendered as `—` in the UI) when there are zero successful tasks to
divide by — never `0.0`, which would misleadingly read as "free." Covered by
`tests/api/test_quality.py::test_quality_performance_empty_workspace_returns_zeroed_summary`
(asserts `is None`, not `== 0.0`) and
`::test_quality_performance_reports_successful_and_failed_request_counts`
(asserts it becomes a real number once a successful request exists). The same
pattern applies to `latency_ms`'s percentiles (all `None` on an empty
workspace, not `0`) and to `avg_judge_score` (`None` when no judge scores
exist in the summary, never averaged against zero).

## What's intentionally not built

The full spec describes an ambitious "final Quality Dashboard" as the
capstone of an even later part of Week 6; this phase's version is deliberately
the practical subset above, reusing existing evaluation/trace/guardrail data
exactly as instructed ("reuse existing evaluation and trace data rather than
creating a second metrics system") — no new dashboard-only tables, no
duplicated aggregation logic, and no synthetic/sample data anywhere in the
page.
