"""Runs the Week 6 evaluation dataset (app/evaluation/data/eval_dataset.json)
against the real chat/agent pipeline and prints a summary report.

Usage (from backend/):
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --provider openai --model gpt-4o-mini
    python scripts/run_evaluation.py --categories rag,adversarial --limit 10
    python scripts/run_evaluation.py --no-judge   # skip the LLM-judge call (faster, cheaper)

Note: this makes one real LLM call per case (two for RAG/adversarial-indirect
cases: one for the reply, one for memory extraction) plus one more if the
judge is enabled — against a live Gemini free-tier key that may be limited to
as few as ~20 requests/day (see docs/evaluation for the original Week 5
finding). Use --categories/--limit to run a small slice at a time, or set
GEMINI_API_KEY/OPENAI_API_KEY to a key without that constraint.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routers.assistants import get_or_create_assistant  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.evaluation.runner import run_evaluation  # noqa: E402
from app.evaluation.seed import get_or_create_eval_workspace  # noqa: E402
from app.models.prompt_version import PromptVersion  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="cli evaluation run")
    parser.add_argument("--provider", default=None, help="gemini | openai (default: workspace assistant's provider)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--categories", default=None, help="comma-separated: normal,difficult,ambiguous,tool_use,rag,adversarial")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM-judge call")
    parser.add_argument(
        "--prompt-version-label",
        default=None,
        help="v1 | v2 | v3 — substitutes that version's system prompt for this run only "
        "(run scripts/seed_prompt_versions.py first). Does not change the real assistant.",
    )
    args = parser.parse_args()

    categories = args.categories.split(",") if args.categories else None

    db = SessionLocal()
    try:
        workspace_id, user_id = get_or_create_eval_workspace(db)
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        assistant = get_or_create_assistant(workspace, db)

        prompt_version_id = None
        system_prompt_override = None
        if args.prompt_version_label:
            version = (
                db.query(PromptVersion)
                .filter(PromptVersion.workspace_id == workspace_id, PromptVersion.version_label == args.prompt_version_label)
                .first()
            )
            if version is None:
                raise SystemExit(
                    f"No prompt version '{args.prompt_version_label}' found — run scripts/seed_prompt_versions.py first."
                )
            prompt_version_id = version.id
            system_prompt_override = version.system_prompt

        run = run_evaluation(
            workspace_id,
            assistant,
            user_id,
            db,
            name=args.name,
            provider=args.provider,
            model=args.model,
            categories=categories,
            limit=args.limit,
            run_judge=not args.no_judge,
            prompt_version_id=prompt_version_id,
            system_prompt_override=system_prompt_override,
        )

        print(f"\nEvaluation run {run.id} ({run.provider}/{run.model}) — status={run.status.value}")
        summary = run.summary or {}
        print(f"  cases: {summary.get('n_cases')}")
        print(f"  overall pass rate: {summary.get('overall_pass_rate')}")
        print(f"  avg latency (ms): {summary.get('avg_latency_ms')}")
        print(f"  total cost (usd): {summary.get('total_cost_usd')}")
        print(f"  total tokens: {summary.get('total_tokens')}")
        print("  by category:")
        for category, stats in (summary.get("by_category") or {}).items():
            print(f"    {category:12s} n={stats['n_cases']:3d}  pass_rate={stats['pass_rate']}  avg_judge={stats['avg_judge_score']}")
        if summary.get("rag_metrics"):
            print(f"  rag metrics: {summary['rag_metrics']}")
        if summary.get("agent_metrics"):
            print(f"  agent metrics: {summary['agent_metrics']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
