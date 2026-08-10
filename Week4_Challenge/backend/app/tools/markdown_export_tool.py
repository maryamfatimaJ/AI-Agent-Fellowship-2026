"""Markdown Export Tool — writes the final report to disk as a `.md` file
under the configured reports directory."""

from __future__ import annotations

from pathlib import Path

import aiofiles

from app.config.logging_config import get_logger
from app.config.settings import get_settings

logger = get_logger("tools.markdown_export")


async def export_markdown(run_id: str, markdown: str) -> Path:
    settings = get_settings()
    path = settings.reports_dir_path / f"{run_id}.md"
    async with aiofiles.open(path, mode="w", encoding="utf-8") as handle:
        await handle.write(markdown)
    logger.info("markdown_export.written", run_id=run_id, path=str(path), bytes=len(markdown.encode("utf-8")))
    return path
