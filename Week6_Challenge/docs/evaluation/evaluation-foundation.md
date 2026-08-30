# Week 6 — Evaluation Foundation & Advanced Evaluation

This document covers the evaluation foundation built on top of the Week 5
platform, plus its "advanced evaluation" extensions: Baseline V1, the 68-case
dataset, the evaluation runner, deterministic evaluators, LLM-as-a-judge (5
subjective dimensions, schema-validated), human-vs-judge comparison and judge
limitations, RAG failure classification, agent evaluation, task-success rules,
and result storage. Execution tracing, trace spans, the trace viewer, and
structured logging are documented separately in `docs/observability.md`. This
document does **not** cover the Quality Dashboard, model comparison
execution, or the 3 performance optimizations — those are documented
separately (`docs/performance/optimizations.md`) and were already implemented
in an earlier pass of this work, alongside the guardrails/agent-layer/
versioning modules the evaluation foundation itself depends on (an evaluation
harness that can score tool selection or guardrail compliance needs those to
already exist).

## Baseline V1

See `docs/evaluation/baseline-v1.md` for the full write-up. Summary: model
(`gemini-2.5-flash`, temp 0.7), prompt v1 (the untouched Week 5 default), RAG
config (chunk 1000/200, top_k 5, min_score 0.65), and the 4-tool agent registry
are all captured. **Real latency/cost/task-success numbers are marked
unavailable** — the configured Gemini API key returns `400 API_KEY_INVALID` on
every real call (confirmed live), not merely quota-exhausted. Two honest
substitutes are used instead: (1) a live smoke test against the real, broken key
proving the error-handling/observability pipeline works correctly on a genuine
failure, and (2) a full 68-case run with the LLM calls mocked (the same
deterministic mock the automated test suite uses), which exercises everything
*except* real model quality — guardrails, RAG retrieval scoring, routing, and
tracing all ran for real.

## Dataset structure

`backend/app/evaluation/data/eval_dataset.json` — a single checked-in JSON file
(not database rows), chosen so it's reviewable and diffable like any other test
fixture. Loaded by `app/evaluation/dataset.py` into a `EvalCase` dataclass.

**Every case has** (the required fields): `test_id`, `category`, `user_input`,
plus whichever of `expected_behavior`, `expected_tool`, `expected_source`,
`expected_structured_output`, `approval_required`, `critical_failure_conditions`
actually apply to that case (null/false/empty otherwise), and always a `notes`
field explaining what the case is testing.

**Deliberately NOT in the dataset**: `actual_result`, `score`, `pass_fail`. Those
are *execution-result* concepts — the dataset holds test **definitions** only.
Keeping them apart means the same 68 cases are reusable, unmodified, across
every future evaluation run (baseline, prompt-version comparison, model
comparison, regression testing) without ever touching the source-of-truth file.
Execution results live in the database instead (see "Result storage" below);
`app/evaluation/runner.py` is what joins a test *definition* with its *result*
for a given run.

## Evaluation categories & test-case design

| Category | Count (min required) | What it tests |
|---|---|---|
| `normal` | 15 (15) | Plain requests unrelated to tools/RAG/agents — general knowledge, arithmetic, translation, instruction-following. A control group: if these fail, something more basic than Week 6's new features is broken. |
| `difficult` | 10 (10) | Multi-step reasoning, nuanced technical explanations, proportional/compound math — harder than `normal` but still model-only (no tools/RAG). |
| `ambiguous` | 8 (8) | Genuinely underspecified requests in a fresh conversation (no prior context to resolve the ambiguity) — the correct behavior is to ask a clarifying question, not guess. |
| `tool_use` | 10 (10) | Routes through the agent orchestrator (`app/agent/orchestrator.py`), each case naming an `expected_tool` and `expected_structured_output` (the minimal required argument keys) for one of the 4 real tools (`search_documents`, `run_skill`, `save_memory`, `delete_document`). `t07` is the one high-risk case (`delete_document`), with `approval_required: true`. |
| `rag` | 10 (10) | Grounded Q&A against the fixture document corpus (`app/evaluation/data/fixture_documents/`), each naming an `expected_source` document the answer must cite. |
| `adversarial` | 15 (7) | Direct prompt injection (12 cases), indirect injection embedded in a retrieved document (2 cases), and a direct secret-exfiltration attempt (1 case) — each carries `critical_failure_conditions` naming exactly what must not happen (comply with the injection, leak the system prompt, leak a secret). |

Every case is written against a real capability of *this* application — the
`tool_use` cases name the actual 4 tools and the actual skill names
(`Summarize`, `SWOT analysis`, `Generate a report`); the `rag` cases ask
questions only answerable from the actual fixture documents; the `adversarial`
cases target the actual guardrail detections built in this project, not generic
chatbot jailbreak trivia.

## Scoring logic & task-success definition

For each case, `run_case()` (in `runner.py`) does, in order:

1. **Dispatch**: `tool_use` cases go through `run_agent_turn()` (the agent
   orchestrator); everything else goes through `send_message()` (the plain
   chat pipeline) — both are the real, unmodified production code paths.
2. **Deterministic checks** (`run_deterministic_checks()`): whichever checks
   apply to this case (exact match, keyword match, tool match, tool-args
   match, structured-output schema, retrieval hit, citation presence, approval
   compliance) each return a `passed: True`. If **no** ordinary check applies
   (most `ambiguous` and `adversarial` cases have none), `passed` is `None`.
3. **Critical-failure conditions** (`check_forbidden_actions()`): evaluated
   *unconditionally* and *separately* from the ordinary checks above.
4. **Overall verdict**, in this priority order:
   - If an ordinary check applies → its pass/fail is the verdict.
   - Else if the case declares `critical_failure_conditions` (typical for
     `adversarial` cases with no other check) → the verdict is exactly "no
     critical condition was violated".
   - Else (no signal at all) → fall back to the LLM judge's overall score
     (`>= 3.0` on the 1-5 scale) when the judge ran; `False` otherwise.
   - **Regardless of the above**: if any critical_failure_condition was
     violated, the verdict is forced to `False` and the failure reason becomes
     `critical_failure:<condition_name>` — a passing keyword match or a high
     judge score can never hide an unauthorized action or a leaked secret.
     This is enforced by code (`runner.py::run_case`), not left to averaging,
     and is covered by
     `tests/evaluation/test_runner.py::test_critical_failure_overrides_a_case_that_otherwise_passes`,
     which forces a real secret leak through the real pipeline and confirms the
     case is marked failed even though its keyword check passed.

**Task success rate** is computed at 3 granularities in `EvaluationRun.summary`:
`overall_pass_rate`/`overall_failure_rate`, per-category `pass_rate`/
`failure_rate`/`failure_reasons`, and a top-level `main_failure_reasons`
histogram — so a dashboard (or this document) can see *why* things failed, not
just the aggregate rate.

## Deterministic evaluators

`backend/app/evaluation/deterministic_evaluators.py` — every check normal code
can reliably determine, never an LLM judge call:

| Evaluator | Checks |
|---|---|
| `exact_match` / `keyword_match` / `regex_match` | Text-level checks against `expected_output`/`expected_keywords`. |
| `tool_selection_correct` | Expected tool vs. actual tool called. |
| `tool_args_correct` | Fuzzy (substring, case-insensitive) match of actual tool arguments against `expected_args`. |
| `validate_structured_output` | Required-keys/type schema check against `expected_structured_output` — distinct from `tool_args_correct`: this checks *shape*, not specific values. |
| `retrieval_hit` / `check_citation_presence` | Whether the *specific* expected document was retrieved, and whether *any* citation was returned when one was expected. |
| `check_approval_compliance` | A high-risk tool call must be gated behind a `PendingAction`, never auto-executed. |
| `check_forbidden_actions` | Evaluates each named `critical_failure_conditions` entry against the real execution context (guardrail events, output-guard flags, whether a tool actually ran). |
| `check_task_completion` | The single combined verdict: ordinary checks passed AND no critical condition was violated. |

Every evaluator returns a `CheckResult` (`check`, `expected`, `actual`, `passed`,
`detail`) — a structured object, never a bare boolean — so a failure always
carries enough information to diagnose it without re-running the case.

## LLM-as-a-judge

`backend/app/evaluation/llm_judge.py::judge_reply()` — handles exactly the
criteria deterministic code cannot reliably check: **correctness, relevance,
completeness, clarity, groundedness**, each scored 1-5, plus an
`overall_score` (their mean) and a short `explanation`. This is a strict
division of labor from the deterministic evaluators above: tool selection,
tool arguments, structured output, citation presence, approval compliance,
and forbidden actions are **never** judged by the LLM — those are exactly the
things normal code can check with certainty, and doing so is cheaper, faster,
and immune to the biases below. `EvaluationResult` stores the two sources in
separate columns (`deterministic_result` vs. `judge_score`/`judge_reasoning`)
so a report can always say which score came from which method.

**The judge prompt** (verbatim in `llm_judge.py::_JUDGE_SYSTEM_PROMPT`) gives
the five dimension definitions, asks for a single JSON object, and explicitly
says: *"do not include your step-by-step reasoning, only a brief final
explanation"* — the judge is never asked to reveal or store a chain-of-thought.
The judge receives: the user's request, the assistant's actual reply, the
case's `expected_behavior` when one exists (e.g. `ask_for_clarification`), and
the retrieved RAG context when there is any (needed specifically for scoring
groundedness).

**Structured output validation**: the judge's raw text is parsed as JSON and
then validated against a Pydantic model (`JudgeScore` — each dimension
`ge=1, le=5`, `explanation` a bounded string). A response that isn't valid
JSON, or is valid JSON that violates the schema (out-of-range score, missing
dimension, wrong type), is treated identically to a judge outage: a null
score with `error` set, never a fabricated/coerced result. Covered by
`tests/evaluation/test_llm_judge.py` (8 cases, including a schema-violating
score and a missing dimension).

**Judge prompt versioning**: `llm_judge.py::JUDGE_PROMPT_VERSION = "v1"` is
stored on every `EvaluationResult.judge_prompt_version` the judge produces
(covered by
`tests/evaluation/test_runner.py::test_judge_prompt_version_is_stored_on_the_result`).
This exists specifically so a future rewording of `_JUDGE_SYSTEM_PROMPT` can
bump the constant to `"v2"` and old and new scores never get silently
compared as if they meant the same thing — per `JUDGE_LIMITATIONS`'
`prompt_sensitivity` entry above, scores are only comparable to each other
under the exact same judge prompt. Regression-testing a judge prompt change
is then just: re-run the same dataset with the new prompt version, and
compare `evaluation_results` rows grouped by `judge_prompt_version` instead of
assuming every row in the table used the same rubric.

### Human vs. LLM judge comparison

10 of the 68 cases (spread across categories, `flagged_for_human_review: true`
in the dataset) are earmarked for this comparison. `human_label` starts as
`null`; a reviewer fills in
`{"overall_score": 1-5, "notes": "...", "evaluation_date": "YYYY-MM-DD"}`
after reading that case's actual output from a completed run.
`app/evaluation/human_comparison.py::compare_human_vs_judge(run_id, db)`
returns, per compared case: `test_id`, `llm_judge_score`, `human_score`,
`difference`, `agreement` (within 1 point on the 1-5 scale),
`reason_for_disagreement` (the human's own `notes`, surfaced only when the
two disagree), plus the raw `human_notes`/`evaluation_date` fields. Verified
end-to-end by
`tests/evaluation/test_runner.py::test_human_comparison_reports_agreement_and_disagreement_once_labels_are_filled_in`.

**Human review worklist** (`human_comparison.py::build_human_review_worklist(run_id, db)`,
exposed as `GET /api/workspaces/{id}/evaluations/{run_id}/human-review-worklist`
and `scripts/generate_human_review_worklist.py`): the actual workflow a human
reviewer follows, rather than just the aggregate-comparison endpoint above.
For each of the 10 flagged cases it pairs the **real** LLM judge score/
explanation/`judge_prompt_version` from a completed run with whatever human
fields exist so far — `human_score`/`human_notes`/`evaluation_date` all stay
exactly `None` and `status: "pending_human_review"` until a person fills in
`eval_dataset.json`'s `human_label` for that case, never a fabricated
placeholder score. Once filled in, the case flips to `status: "reviewed"`.
`why_human_evaluation_is_needed` (a plain-language explanation of why a
second, human opinion matters given the judge's own documented biases) is
included in every response. Verified by
`tests/evaluation/test_runner.py::test_human_review_worklist_lists_all_ten_flagged_cases_as_pending`
— confirms all 10 flagged cases appear with real (non-null) judge scores and
`n_pending == 10`/`n_reviewed == 0` in the current, not-yet-reviewed state
(never fabricating a human score to make the numbers look more complete).

**LLM judge limitations** (`human_comparison.JUDGE_LIMITATIONS`, returned
alongside every comparison so a consumer of the API never sees a bare score
without the caveats) — the judge is explicitly **not** claimed to be
reliable:

- **model_bias** — the judge is itself an LLM and inherits that model's own
  blind spots and preferences; it is not a neutral, external ground truth.
- **position_bias** — LLM judges are documented to weight earlier/later
  prompt content inconsistently; not tested for or corrected here.
- **verbosity_bias** — tends to rate longer, more elaborate answers higher
  even when a shorter answer is equally or more correct.
- **self_preference** — a judge model may rate replies from its own model
  family more favorably; relevant here since the judge and the assistant can
  be the same underlying model/provider.
- **inconsistent_scoring** — `temperature=0` improves repeatability but does
  not guarantee an identical score for the same input on every call.
- **prompt_sensitivity** — small wording changes to the judge prompt can
  shift scores measurably; scores are only comparable to each other under
  this exact prompt, not across a differently-worded judge.

## RAG evaluation methodology

`backend/app/evaluation/rag_metrics.py` — RAG is never scored only from the
final answer; retrieval quality and generation quality are evaluated and
classified separately:

```
question
  -> was the correct chunk retrieved? (retrieval_hit, against expected_source)
       no  -> retrieval_failure
       yes -> was the correct answer generated from it? (expected_keywords present?)
                no  -> generation_failure
                yes -> success
```

(A fourth state, `unclassified`, covers cases with no `expected_keywords` to
check the answer against — honestly marked as not evaluable this way, never
silently counted as a success.) Alongside that classification: **retrieval
hit rate** (did retrieval return the specific expected document),
**context relevance** (fraction of returned chunks that were the expected
one), **answer groundedness** (from the judge's groundedness dimension,
normalized to 0-1), **citation correctness** (does at least one citation
point at the expected source), and **unsupported claim rate** (a heuristic:
relevant context WAS retrieved, but the answer doesn't reflect the facts it
should have grounded on).

## Agent evaluation methodology

`backend/app/evaluation/agent_metrics.py` — reuses the orchestrator's own
captured tool-call trace directly rather than re-deriving anything. Mapping
from the required dimensions to what's actually computed, since this is a
single-agent system with single-decision eval cases (each `tool_use` case
names exactly one expected tool call):

- **intent understanding** → `intent_understood`, approximated as "did the
  agent pick the tool that correctly reflects the request" — a wrong tool
  choice is itself evidence of a misunderstood intent; there's no signal to
  check intent independently of tool selection in this dataset.
- **tool selection / argument generation** → `tool_selection_correct` /
  `tool_arguments_correct`, direct checks against `expected_tool`/`expected_args`.
- **planning / routing** → collapses into tool selection in a single-tool,
  single-step system — "routing" *is* "which tool got selected" here.
  Multi-step planning across several tool calls is not exercised by this
  dataset version (every `tool_use` case is a single decision), and this is
  stated plainly rather than fabricating a planning score.
- **state management** → out of scope for the same reason (no multi-step case
  exists yet); `loop_count` is the closest available proxy.
- **task completion / loop frequency / recovery behavior** → `task_completed`,
  `loop_count`/`hit_loop_limit`, `recovered_from_error` (did the agent still
  produce a real answer after a tool error, rather than parroting the raw
  error or giving up).
- **multi-agent metrics** (routing accuracy across agents, handoff success
  rate, revision count, unnecessary agent calls) → **not applicable**. This
  application has exactly one agent
  (`app/agent/orchestrator.py::run_agent_turn`), not a multi-agent system, so
  there is no handoff or inter-agent routing to measure —
  `aggregate_agent_metrics()` reports this explicitly
  (`"multi_agent_metrics": "not_applicable_single_agent_system"`) rather than
  omitting it silently or inventing placeholder numbers.

## Evaluation runner

`backend/app/evaluation/runner.py`:

- `run_evaluation(workspace_id, assistant, user_id, db, ...)` — creates one
  `EvaluationRun` row (a unique run id, dataset version, prompt-version id if
  any, provider/model), runs every selected case through `run_case()`, and
  writes a summary (`_summarize()`) once all cases complete.
- `run_case(case, ...)` — one case, one turn, through the real pipeline;
  captures the actual reply, tool-call trace (for `tool_use`), RAG citations,
  guardrail events, and the `Trace` row's latency/tokens/cost; runs the
  deterministic checks and (optionally) the LLM judge; returns one
  `EvaluationResult`.
- `_resolve_assistant()` builds an **un-persisted** `Assistant` object carrying
  any provider/model/prompt override for this run — it's never added to the
  DB session, so running an eval with a different prompt version or model
  never mutates the workspace's real assistant configuration (verified by
  `test_system_prompt_override_is_actually_used_for_the_run`).

The same dataset + runner is reusable, unmodified, for prompt-version
comparison (pass `system_prompt_override`), model comparison (pass
`provider`/`model`), and regression testing (diff two runs' `EvaluationResult`
rows by `case_id`) — none of that logic needed to change when the dataset or
scoring rules did.

## Result storage

Two tables (`backend/app/models/evaluation.py`), additive to the existing
schema, no columns changed on any pre-existing table:

- **`evaluation_runs`**: one row per run — id, workspace, name, dataset
  version, prompt-version id, provider, model, status, started/completed
  timestamps, and the `summary` JSON blob described above.
- **`evaluation_results`**: one row per case per run — `case_id` (the
  dataset's `test_id`), category, `actual_output` (the case's `actual_result`),
  `deterministic_result` (the full structured check list plus
  `critical_checks`/`critical_failed`/`task_completion`), `judge_score` (the
  case's `score`), `judge_reasoning`, `rag_metrics`, `agent_metrics`,
  `latency_ms`/`input_tokens`/`output_tokens`/`cost_usd` (from the matching
  `Trace` row), `passed` (the case's `pass_fail`), and `failure_category` (the
  case's failure notes — `deterministic_check_failed`, `low_judge_score`, or
  `critical_failure:<condition>`).

This is enough metadata to identify run, test id, timestamp (`created_at`),
model, prompt version, actual result, every evaluator's result, score, and
pass/fail — everything the spec asks results to carry — without needing to
touch the physical schema of an already-existing, already-tested table (no
Alembic exists in this project; adding new columns to a table SQLite already
created would require a destructive recreate, which was deliberately avoided).

## How to run the evaluation suite

```bash
cd backend

# One-off: create/confirm the eval workspace + fixture documents
python scripts/seed_eval_workspace.py

# Full 68-case run (real LLM calls — see the API-key limitation above)
python scripts/run_evaluation.py

# A safe slice, or skip the extra judge call entirely
python scripts/run_evaluation.py --categories rag,adversarial --limit 10
python scripts/run_evaluation.py --no-judge

# Against a specific prompt version (see docs/performance and the
# prompt_versions API) or model
python scripts/run_evaluation.py --prompt-version-label v2
python scripts/run_evaluation.py --provider openai --model gpt-4o-mini
```

```bash
# After a run completes, generate the human-review worklist for a reviewer
# to work from (writes app/evaluation/data/human_review_worklist.json by default)
python scripts/generate_human_review_worklist.py <run_id>
```

Or via the API: `POST /api/workspaces/{id}/evaluations/run`,
`GET /api/workspaces/{id}/evaluations`, `GET /api/workspaces/{id}/evaluations/{run_id}`,
`GET /api/workspaces/{id}/evaluations/compare?run_a=&run_b=`,
`GET /api/workspaces/{id}/evaluations/{run_id}/human-comparison`,
`GET /api/workspaces/{id}/evaluations/{run_id}/human-review-worklist`. Every
trace a run produces is also independently queryable via
`GET /api/workspaces/{id}/traces?evaluation_run_id=<run_id>` (optionally add
`&eval_case_id=<test_id>` for one specific case) — see `docs/observability.md`'s
"Evaluation ↔ trace linkage" section for the full run → test_id → trace →
result chain.

Automated tests: `pytest tests/evaluation` (dataset validation, every
deterministic evaluator, the runner end-to-end with mocked LLM calls, the
critical-failure-override rule, human-vs-judge comparison, the human-review
worklist, judge-prompt-version storage, and evaluation-run-to-trace linkage)
and `pytest tests/agent tests/security` (the agent orchestrator and guardrails
the evaluation harness scores against).

## Limitations

1. **No real model-quality baseline yet** — the configured Gemini API key is
   invalid. A valid key is required before `judge_score`/task-success numbers
   reflect real model behavior rather than the deterministic mock.
2. **Human labels not yet filled in** — the 10 `flagged_for_human_review` cases
   have `human_label: null`; a human reviewer needs to read each case's actual
   output from a completed run and fill in `{"overall_score": 1-5, "notes":
   "..."}` before `compare_human_vs_judge()` has anything to compare.
3. **`ambiguous` cases have no deterministic ground truth** — "did the
   assistant ask a good clarifying question" is graded by keyword heuristics
   or the judge, not a hard check; this is a genuine grading limitation of the
   category, not a bug, and is why several `ambiguous`/`normal` cases are among
   the 10 flagged for human review.
4. **`tool_use` category needs `generate_with_tools` mocked separately** from
   the plain-chat mock — a run with only the default `mock_llm` fixture (no
   extra monkeypatching) will have its tool-calling calls hit the real,
   currently-invalid API key and fail closed rather than route to a tool; this
   is disclosed rather than hidden in `baseline-v1.md`.
