"""Writes the human-review worklist for a completed evaluation run to a JSON
file a reviewer can read while filling in eval_dataset.json's human_label
fields. Never fabricates a human score — rows with no human_label yet are
written with human_score=null and status="pending_human_review".

Usage (from backend/):
    python scripts/run_evaluation.py --name "baseline"      # note the printed run id
    python scripts/generate_human_review_worklist.py <run_id>
    python scripts/generate_human_review_worklist.py <run_id> --out my_worklist.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal  # noqa: E402
from app.evaluation.human_comparison import build_human_review_worklist  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "app" / "evaluation" / "data" / "human_review_worklist.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", help="An evaluation run id (see scripts/run_evaluation.py's printed output)")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        worklist = build_human_review_worklist(args.run_id, db)
    finally:
        db.close()

    if worklist["n_cases"] == 0:
        raise SystemExit(
            f"No flagged cases found for run {args.run_id} — check the run id and that it actually ran "
            "the flagged categories (normal/difficult/ambiguous/rag/tool_use/adversarial)."
        )

    out_path = Path(args.out)
    out_path.write_text(json.dumps(worklist, indent=2), encoding="utf-8")
    print(f"Wrote {worklist['n_cases']} cases ({worklist['n_pending']} pending review) to {out_path}")
    print("Fill in human_score/notes/evaluation_date by hand-editing app/evaluation/data/eval_dataset.json's")
    print("human_label field for each test_id listed above, then re-run compare_human_vs_judge().")


if __name__ == "__main__":
    main()
