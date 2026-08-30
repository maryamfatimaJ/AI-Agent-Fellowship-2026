"""Creates (or reuses) a dedicated workspace pre-loaded with the fixture
document corpus (app/evaluation/data/fixture_documents/) that the rag and
adversarial-indirect-injection eval cases retrieve against. Reuses the real
workspace-creation route function directly (not a copy of its logic) so the
eval workspace gets the exact same default assistant/skills/prompts as any
real workspace.
"""

from sqlalchemy.orm import Session

from app.api.routers.workspaces import create_workspace
from app.core.security import hash_password
from app.evaluation.dataset import FIXTURE_DOCUMENTS_DIR
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.rag.retrieval import ingest_document
from app.schemas.workspace import WorkspaceCreate

EVAL_WORKSPACE_NAME = "Week 6 Evaluation Workspace"
EVAL_USER_EMAIL = "eval-harness@internal.local"


def ensure_eval_user(db: Session) -> User:
    user = db.query(User).filter(User.email == EVAL_USER_EMAIL).first()
    if user is None:
        user = User(email=EVAL_USER_EMAIL, hashed_password=hash_password("not-a-real-login-eval-harness"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _ingest_fixture_documents(workspace_id: str, owner: User, db: Session) -> None:
    for path in sorted(FIXTURE_DOCUMENTS_DIR.glob("*")):
        content = path.read_bytes()
        document = Document(
            workspace_id=workspace_id,
            uploaded_by=owner.id,
            filename=path.name,
            mime_type="text/markdown" if path.suffix == ".md" else "text/plain",
            size_bytes=len(content),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        ingest_document(document, content, db)


def create_eval_workspace(db: Session, owner: User) -> str:
    workspace = create_workspace(WorkspaceCreate(name=EVAL_WORKSPACE_NAME), current_user=owner, db=db)
    _ingest_fixture_documents(workspace.id, owner, db)
    return workspace.id


def get_or_create_eval_workspace(db: Session) -> tuple[str, str]:
    """Returns (workspace_id, user_id). Idempotent — reuses an existing eval
    workspace for the dedicated eval-harness user if one already exists,
    rather than re-creating (and re-uploading documents into) a new one on
    every run."""
    owner = ensure_eval_user(db)
    existing = (
        db.query(Workspace)
        .filter(Workspace.owner_id == owner.id, Workspace.name == EVAL_WORKSPACE_NAME)
        .first()
    )
    if existing is not None:
        return existing.id, owner.id
    workspace_id = create_eval_workspace(db, owner)
    return workspace_id, owner.id
