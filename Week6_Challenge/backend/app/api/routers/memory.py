from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.database.deps import get_db
from app.models.memory import Memory
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.memory import MemoryCreate, MemoryRead, MemoryUpdate

router = APIRouter(prefix="/api/workspaces/{workspace_id}/memory", tags=["memory"])


@router.get("", response_model=list[MemoryRead])
def list_memories(
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Memory]:
    return (
        db.query(Memory)
        .filter(Memory.workspace_id == workspace.id, Memory.user_id == current_user.id)
        .order_by(Memory.pinned.desc(), Memory.updated_at.desc())
        .all()
    )


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Memory:
    memory = Memory(
        workspace_id=workspace.id,
        user_id=current_user.id,
        key=payload.key,
        value=payload.value,
        pinned=payload.pinned,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def _get_owned_memory(memory_id: str, workspace: Workspace, current_user: User, db: Session) -> Memory:
    memory = (
        db.query(Memory)
        .filter(Memory.id == memory_id, Memory.workspace_id == workspace.id, Memory.user_id == current_user.id)
        .first()
    )
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory entry not found")
    return memory


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Memory:
    memory = _get_owned_memory(memory_id, workspace, current_user, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(memory, field, value)
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memory = _get_owned_memory(memory_id, workspace, current_user, db)
    db.delete(memory)
    db.commit()
