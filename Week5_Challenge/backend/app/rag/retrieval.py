import json
import logging

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Chunk, Document, DocumentStatus
from app.rag.chunking import chunk_text
from app.rag.extraction import extract_text
from app.services.llm_service import LLMError, embed_texts

logger = logging.getLogger("app.rag")


def ingest_document(document: Document, content: bytes, db: Session) -> None:
    settings = get_settings()
    document.status = DocumentStatus.PROCESSING
    db.commit()

    try:
        text = extract_text(document.filename, content)
        pieces = chunk_text(text, settings.chunk_size, settings.chunk_overlap)

        if not pieces:
            document.status = DocumentStatus.FAILED
            db.commit()
            return

        vectors = embed_texts(pieces, task_type="RETRIEVAL_DOCUMENT")

        for index, (piece, vector) in enumerate(zip(pieces, vectors)):
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=piece,
                    embedding=json.dumps(vector),
                )
            )

        document.status = DocumentStatus.READY
        db.commit()
    except Exception:
        logger.exception("Document ingestion failed for document_id=%s", document.id)
        document.status = DocumentStatus.FAILED
        db.commit()


def retrieve_relevant_chunks(
    workspace_id: str, query: str, db: Session, top_k: int | None = None
) -> list[dict]:
    settings = get_settings()
    top_k = top_k or settings.rag_top_k

    chunks = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.workspace_id == workspace_id, Document.status == DocumentStatus.READY)
        .all()
    )
    if not chunks:
        return []

    try:
        query_vector = np.array(embed_texts([query], task_type="RETRIEVAL_QUERY")[0])
    except LLMError:
        logger.exception("Query embedding failed; skipping retrieval for this turn")
        return []

    scored = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        chunk_vector = np.array(json.loads(chunk.embedding))
        score = _cosine_similarity(query_vector, chunk_vector)
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    relevant = [pair for pair in scored if pair[0] >= settings.rag_min_score]

    results = []
    for score, chunk in relevant[:top_k]:
        results.append(
            {
                "document_id": chunk.document_id,
                "filename": chunk.document.filename,
                "chunk_index": chunk.chunk_index,
                "snippet": chunk.content[:400],
                "score": round(float(score), 4),
            }
        )
    return results


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
