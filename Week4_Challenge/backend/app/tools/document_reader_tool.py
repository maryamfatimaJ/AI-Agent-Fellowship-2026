"""Document Reader Tool — reads plain-text/markdown documents supplied by the
user (e.g. an internal memo) so their content can be folded into evidence."""

from __future__ import annotations

from pathlib import Path

from app.utils.errors import ToolExecutionError

_SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}


def read_document(path: str, *, max_chars: int = 20_000) -> str:
    file_path = Path(path)
    if file_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ToolExecutionError(
            f"Unsupported document type: {file_path.suffix!r}",
            details={"supported": sorted(_SUPPORTED_SUFFIXES)},
        )
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolExecutionError(f"Could not read document: {path}", details={"error": str(exc)}) from exc

    return text[:max_chars]
