"""Seeds the 3 system-prompt versions (app/prompts/system_prompt_versions.py)
into the Week 6 evaluation workspace, for use with:
    python scripts/run_evaluation.py --prompt-version-label v2
(or directly via the API's POST .../evaluations/run with prompt_version_id).

Idempotent — re-running updates existing rows by version_label instead of
duplicating them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal  # noqa: E402
from app.evaluation.seed import get_or_create_eval_workspace  # noqa: E402
from app.models.prompt_version import PromptVersion  # noqa: E402
from app.prompts.system_prompt_versions import SYSTEM_PROMPT_VERSIONS  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        workspace_id, _user_id = get_or_create_eval_workspace(db)

        for spec in SYSTEM_PROMPT_VERSIONS:
            existing = (
                db.query(PromptVersion)
                .filter(PromptVersion.workspace_id == workspace_id, PromptVersion.version_label == spec["version_label"])
                .first()
            )
            if existing is not None:
                existing.name = spec["name"]
                existing.system_prompt = spec["system_prompt"]
                existing.notes = spec["notes"]
            else:
                db.add(
                    PromptVersion(
                        workspace_id=workspace_id,
                        name=spec["name"],
                        version_label=spec["version_label"],
                        system_prompt=spec["system_prompt"],
                        notes=spec["notes"],
                        is_active=spec["version_label"] == "v1",
                    )
                )
        db.commit()
        print(f"Seeded {len(SYSTEM_PROMPT_VERSIONS)} prompt versions into workspace {workspace_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
