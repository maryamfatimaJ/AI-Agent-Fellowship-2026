"""One-off: create (or confirm) the Week 6 evaluation workspace and ingest its
fixture document corpus. Run from backend/: `python scripts/seed_eval_workspace.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal  # noqa: E402
from app.evaluation.seed import get_or_create_eval_workspace  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        workspace_id, user_id = get_or_create_eval_workspace(db)
        print(f"Eval workspace ready: workspace_id={workspace_id} user_id={user_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
