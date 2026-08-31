import json
import logging

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.events import RETRIEVAL_COMPLETED, RETRIEVAL_STARTED, log_event
from app.models.document import Chunk, Document, DocumentStatus
from app.models.trace import TraceStatus, TraceType
from app.rag.chunking import chunk_text
from app.rag.extraction import extract_text
from app.services.llm_service import LLMError, embed_texts
from app.services.trace_service import record_trace, timed_span

logger = logging.getLogger("app.rag")


class RagUnavailableError(LLMError):
    """Raised (not silently swallowed) when the embedding backend fails during
    retrieval, so callers can distinguish "the knowledge search backend is
    down" from "no relevant documents exist" and surface a real user-facing
    notice for the former — see chat_service.py and agent/tools.py, both of
    which catch this specifically rather than treating it like an ordinary
    empty-results case."""


def ingest_document(document: Document, content: bytes, db: Session) -> None:
    settings = get_settings()
    document.status = DocumentStatus.PROCESSING
    db.commit()

    trace_status = TraceStatus.SUCCESS
    trace_error: str | None = None

    with timed_span() as span:
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
        except Exception as exc:
            logger.exception("Document ingestion failed for document_id=%s", document.id)
            document.status = DocumentStatus.FAILED
            db.commit()
            trace_status = TraceStatus.ERROR
            trace_error = str(exc)

    record_trace(
        db,
        trace_type=TraceType.EMBEDDING,
        workspace_id=document.workspace_id,
        user_id=document.uploaded_by,
        status=trace_status,
        error_message=trace_error,
        latency_ms=span["elapsed_ms"],
        meta={"document_id": document.id, "filename": document.filename},
    )


def retrieve_relevant_chunks(
    workspace_id: str, query: str, db: Session, top_k: int | None = None
) -> list[dict]:
    settings = get_settings()
    top_k = top_k or settings.rag_top_k
    log_event(logger, RETRIEVAL_STARTED, workspace_id=workspace_id, query_length=len(query))

    chunks = (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Document.workspace_id == workspace_id, Document.status == DocumentStatus.READY)
        .all()
    )
    if not chunks:
        log_event(logger, RETRIEVAL_COMPLETED, workspace_id=workspace_id, chunks_scanned=0, chunks_returned=0)
        return []

    try:
        query_vector = np.array(embed_texts([query], task_type="RETRIEVAL_QUERY")[0])
    except LLMError as exc:
        logger.warning("Query embedding failed; degrading gracefully to no-RAG-context for this turn: %s", exc)
        record_trace(
            db,
            trace_type=TraceType.EMBEDDING,
            workspace_id=workspace_id,
            status=TraceStatus.DEGRADED,
            error_message=str(exc),
            meta={"stage": "query_embedding"},
        )
        # Raised (not returned as an empty list) so the caller can tell "the
        # search backend is down" apart from "nothing relevant exists" and
        # show the user a real notice instead of a silently ungrounded
        # answer — see chat_service.py::send_message and
        # agent/tools.py::_search_documents, both of which catch this
        # specifically.
        raise RagUnavailableError(f"Knowledge search is temporarily unavailable: {exc}") from exc

    scored = _rank_by_cosine_similarity(query_vector, chunks)
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
    log_event(
        logger,
        RETRIEVAL_COMPLETED,
        workspace_id=workspace_id,
        chunks_scanned=len(chunks),
        chunks_returned=len(results),
        retrieved_document_ids=[r["document_id"] for r in results],
    )
    return results


# Optimization (Week 6 performance pass): caches each chunk's parsed vector and
# precomputed norm, keyed by chunk id. A chunk's embedding never changes after
# ingestion, but the un-cached code re-ran json.loads() and np.linalg.norm()
# on every single chunk on *every* retrieval call, even though a given
# workspace is typically queried many times against the same, unchanged
# document set (e.g. one chat conversation sends many messages). An earlier
# attempt at "vectorizing" this into one big np.array(list) + matmul call was
# measured (scripts/benchmark_optimizations.py) to be *slower* than the
# original per-chunk loop at realistic scale (100-20,000 chunks, 3072-dim
# Gemini embeddings) — the cost of copying every embedding into one
# contiguous matrix on every call outweighed the BLAS matmul's savings. This
# cache instead removes the repeated parse/norm work itself, which is the
# part that's actually redundant across repeated queries.
_chunk_vector_cache: dict[str, tuple[np.ndarray, float]] = {}


def _get_cached_vector(chunk: Chunk) -> tuple[np.ndarray, float] | None:
    cached = _chunk_vector_cache.get(chunk.id)
    if cached is not None:
        return cached
    if not chunk.embedding:
        return None
    vector = np.array(json.loads(chunk.embedding))
    norm = float(np.linalg.norm(vector))
    _chunk_vector_cache[chunk.id] = (vector, norm)
    return vector, norm


def _rank_by_cosine_similarity(query_vector: np.ndarray, chunks: list[Chunk]) -> list[tuple[float, Chunk]]:
    query_norm = np.linalg.norm(query_vector)
    scored = []
    for chunk in chunks:
        cached = _get_cached_vector(chunk)
        if cached is None:
            continue
        vector, norm = cached
        denom = query_norm * norm
        score = 0.0 if denom == 0 else float(np.dot(query_vector, vector) / denom)
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored
