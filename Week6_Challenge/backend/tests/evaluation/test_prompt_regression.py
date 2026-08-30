"""Runs the real evaluation dataset against all 3 seeded system-prompt
versions (app/prompts/system_prompt_versions.py) through the real chat/agent
pipeline, then diffs each pair with compare_runs() — this is the actual
"prompt regression testing" requirement executed for real (via the same
mock_llm fixture every other test in this suite uses, since the project's
only configured API key is currently rejected by the provider — see
docs/evaluation/prompt-regression-results.md for the full writeup and honest
limitation disclosure).

Because mock_llm.generate_reply() returns a fixed reply string regardless of
the system prompt it's given (by design — see tests/conftest.py), these runs
cannot show a real model-quality difference between prompt versions; what
this test proves is that the *mechanism* — three independent runs, executed
through the real runner, diffed pairwise — actually works end-to-end. The
capacity to detect a genuine regression is proven separately, against
directly-constructed results, by tests/evaluation/test_comparison.py.
"""

from app.api.routers.assistants import get_or_create_assistant
from app.evaluation.comparison import compare_runs
from app.evaluation.runner import run_evaluation
from app.evaluation.seed import create_eval_workspace, ensure_eval_user
from app.models.workspace import Workspace
from app.prompts.system_prompt_versions import SYSTEM_PROMPT_VERSIONS


def test_all_three_prompt_versions_run_against_the_same_dataset_and_are_comparable(db_session, mock_llm):
    owner = ensure_eval_user(db_session)
    workspace_id = create_eval_workspace(db_session, owner)
    workspace = db_session.query(Workspace).filter(Workspace.id == workspace_id).first()
    assistant = get_or_create_assistant(workspace, db_session)

    runs = {}
    for version in SYSTEM_PROMPT_VERSIONS:
        run = run_evaluation(
            workspace_id, assistant, owner.id, db_session,
            name=f"prompt-regression-{version['version_label']}",
            categories=["normal", "adversarial", "rag"],
            limit=None,
            run_judge=True,
            system_prompt_override=version["system_prompt"],
        )
        runs[version["version_label"]] = run
        assert run.status.value == "completed"
        assert run.summary["n_cases"] > 0

    v1_v2 = compare_runs(runs["v1"].id, runs["v2"].id, db_session)
    v2_v3 = compare_runs(runs["v2"].id, runs["v3"].id, db_session)
    v1_v3 = compare_runs(runs["v1"].id, runs["v3"].id, db_session)

    for comparison in (v1_v2, v2_v3, v1_v3):
        n_compared = comparison["improved"] + comparison["regressed"] + comparison["unchanged"]
        assert n_compared == runs["v1"].summary["n_cases"]
        # Every case must be classified as exactly one of the three outcomes —
        # never silently dropped.
        assert len(comparison["cases"]) == n_compared
