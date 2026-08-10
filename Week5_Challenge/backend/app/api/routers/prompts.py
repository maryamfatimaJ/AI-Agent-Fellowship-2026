from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.database.deps import get_db
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.prompt_template import PromptTemplateCreate, PromptTemplateRead, PromptTemplateUpdate

router = APIRouter(prefix="/api/workspaces/{workspace_id}/prompts", tags=["prompts"])


def _get_owned_prompt(prompt_id: str, workspace: Workspace, db: Session) -> PromptTemplate:
    prompt = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.id == prompt_id, PromptTemplate.workspace_id == workspace.id)
        .first()
    )
    if prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return prompt


@router.get("", response_model=list[PromptTemplateRead])
def list_prompts(
    category: str | None = None,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> list[PromptTemplate]:
    query = db.query(PromptTemplate).filter(PromptTemplate.workspace_id == workspace.id)
    if category:
        query = query.filter(PromptTemplate.category == category)
    return query.order_by(PromptTemplate.updated_at.desc()).all()


@router.post("", response_model=PromptTemplateRead, status_code=status.HTTP_201_CREATED)
def create_prompt(
    payload: PromptTemplateCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromptTemplate:
    prompt = PromptTemplate(
        workspace_id=workspace.id,
        created_by=current_user.id,
        name=payload.name,
        content=payload.content,
        category=payload.category,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.patch("/{prompt_id}", response_model=PromptTemplateRead)
def update_prompt(
    prompt_id: str,
    payload: PromptTemplateUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> PromptTemplate:
    prompt = _get_owned_prompt(prompt_id, workspace, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(prompt, field, value)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    prompt_id: str, workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)
) -> None:
    prompt = _get_owned_prompt(prompt_id, workspace, db)
    db.delete(prompt)
    db.commit()
