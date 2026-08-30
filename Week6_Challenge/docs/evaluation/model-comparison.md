# Model Comparison

## Infrastructure (implemented and tested)

`app/evaluation/runner.py::run_evaluation(..., provider=..., model=...)`
already accepted per-run provider/model overrides from an earlier phase;
`app/evaluation/comparison.py::compare_runs` (the same mechanism used for
prompt-version comparison, see `docs/evaluation/prompt-regression-results.md`)
diffs any two runs case-by-case regardless of what varies between them —
prompt, provider, or model. `_resolve_assistant()` builds an in-memory,
never-persisted `Assistant` carrying the override, so comparing models never
mutates the workspace's real configured assistant.

`backend/tests/evaluation/test_model_comparison.py::test_the_same_dataset_can_be_run_against_two_different_providers_and_compared`
actually executes this end-to-end: two real `run_evaluation()` calls (one
tagged `provider="gemini", model="gemini-2.5-flash"`, one tagged
`provider="openai", model="gpt-4o-mini"`), each producing a real
`EvaluationRun`/`EvaluationResult` set correctly tagged by model, diffed with
`compare_runs`. This proves the comparison **infrastructure** — tagging,
running, diffing — works, independent of whether the two models' outputs
actually differ.

## Why no real two-model comparison could be produced

This environment has exactly one API key configured
(`backend/.env`'s `GEMINI_API_KEY`), no `OPENAI_API_KEY` at all. A live smoke
test run during this phase (`generate_reply(...)` against the real Gemini
API) returned:

```
google.genai.errors.ClientError: 404 NOT_FOUND. {'error': {'code': 404,
'message': 'This model models/gemini-2.5-flash is no longer available to
new users. Please update your code to use models/gemini-3.6-flash...'}}
```

Retrying against the suggested replacement model name (`gemini-3.6-flash`)
returned a second, more fundamental error:

```
google.genai.errors.ClientError: 403 PERMISSION_DENIED. {'error': {'code':
403, 'message': 'Your project has been denied access. Please contact
support.'}}
```

This is a **worse** failure than the one recorded in an earlier phase of this
project (`docs/evaluation/baseline-v1.md` originally documented a
`400 API_KEY_INVALID`) — the configured Google Cloud project now appears to
be blocked outright, not merely using an invalid key or a deprecated model.
Combined with there being no OpenAI key at all, **neither of the two
supported providers can currently serve a real request in this environment.**

Per this phase's explicit instruction ("if a second model cannot actually be
executed... implement the comparison infrastructure, document the
limitation, and use real results only"), no fabricated Gemini-vs-OpenAI
comparison numbers are reported anywhere in this project. The mocked test
above (`test_model_comparison.py`) necessarily shows identical results for
both "models," since `mock_llm.generate_reply()` returns a fixed reply
regardless of `provider`/`model` — that flatness is a property of the mock,
not a claim that the two providers perform identically.

## What a real comparison would evaluate (unexecuted, for reference)

Had working keys been available, `run_evaluation()`/`compare_runs()` already
compute everything the spec asks for, per model: task success (`pass_rate`),
quality (`avg_judge_score`), latency (`Trace.latency_ms`, aggregated via
`stats_service.get_performance_summary`'s `by_model` breakdown), token usage
(`input_tokens`/`output_tokens`), estimated cost (`usage_service.estimate_cost_usd`,
per-model pricing table), and tool-calling reliability (`agent_metrics`'
`tool_selection_correct`/`hit_loop_limit` rates for `tool_use`-category
cases). No new computation is needed once a valid key exists — running
`python scripts/run_evaluation.py --provider openai --model gpt-4o-mini` and
`... --provider gemini` and then `GET .../evaluations/compare?run_a=&run_b=`
would produce the real comparison immediately.

## Conclusion

**Value determination deferred, not fabricated.** "Which model is better for
this application" cannot be honestly answered without at least one working
provider key — this document records the infrastructure is ready, the
specific environmental blocker (denied Gemini project access, no OpenAI key),
and exactly what command to run once a key is available, rather than guessing.
