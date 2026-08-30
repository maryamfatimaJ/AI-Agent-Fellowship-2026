from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.core.config import get_settings
from app.database.deps import get_db
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.rag.extraction import SUPPORTED_EXTENSIONS
from app.rag.retrieval import ingest_document
from app.schemas.document import DocumentRead

router = APIRouter(prefix="/api/workspaces/{workspace_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    settings = get_settings()
    extension = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    document = Document(
        workspace_id=workspace.id,
        uploaded_by=current_user.id,
        filename=file.filename or "untitled",
        mime_type=file.content_type,
        size_bytes=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    ingest_document(document, content, db)
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.workspace_id == workspace.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str, workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)
) -> None:
    document = (
        db.query(Document).filter(Document.id == document_id, Document.workspace_id == workspace.id).first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    db.delete(document)
    db.commit()
