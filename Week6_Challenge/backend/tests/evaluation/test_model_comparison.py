"""Proves the model-comparison INFRASTRUCTURE (run_evaluation's provider/model
overrides + compare_runs) works end to end: the same dataset run once per
"model" (here, gemini vs. openai, both through mock_llm since neither
provider's real API key is usable in this environment — see
docs/evaluation/model-comparison.md for the full writeup and honest
limitation disclosure), producing two independently comparable runs.

This does NOT claim a real quality difference between Gemini and OpenAI —
mock_llm.generate_reply() returns the same fixed text regardless of
`provider`, so under this mock the two runs are necessarily identical. What's
proven here is that the mechanism (per-run provider override, cost/token
accounting tagged by model, pairwise diffing) is real, executed code, not a
stub — the actual comparability of two live models is a separate, disclosed
limitation.
"""

from app.api.routers.assistants import get_or_create_assistant
from app.evaluation.comparison import compare_runs
from app.evaluation.runner import run_evaluation
from app.evaluation.seed import create_eval_workspace, ensure_eval_user
from app.models.workspace import Workspace


def test_the_same_dataset_can_be_run_against_two_different_providers_and_compared(db_session, mock_llm):
    owner = ensure_eval_user(db_session)
    workspace_id = create_eval_workspace(db_session, owner)
    workspace = db_session.query(Workspace).filter(Workspace.id == workspace_id).first()
    assistant = get_or_create_assistant(workspace, db_session)

    run_gemini = run_evaluation(
        workspace_id, assistant, owner.id, db_session,
        name="model-comparison-gemini", provider="gemini", model="gemini-2.5-flash",
        categories=["normal", "rag"], run_judge=True,
    )
    run_openai = run_evaluation(
        workspace_id, assistant, owner.id, db_session,
        name="model-comparison-openai", provider="openai", model="gpt-4o-mini",
        categories=["normal", "rag"], run_judge=True,
    )

    assert run_gemini.provider == "gemini" and run_gemini.model == "gemini-2.5-flash"
    assert run_openai.provider == "openai" and run_openai.model == "gpt-4o-mini"
    assert run_gemini.status.value == "completed"
    assert run_openai.status.value == "completed"

    comparison = compare_runs(run_gemini.id, run_openai.id, db_session)
    n_compared = comparison["improved"] + comparison["regressed"] + comparison["unchanged"]
    assert n_compared == run_gemini.summary["n_cases"]
