"""Content Extraction Tool — fetches a URL and extracts readable body text."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.config.logging_config import get_logger
from app.config.settings import get_settings
from app.utils.errors import ToolExecutionError
from app.utils.retry import async_retry

logger = get_logger("tools.content_extraction")

_STRIP_TAGS = ("script", "style", "nav", "footer", "header", "aside", "form", "noscript")


class ExtractedContent(BaseModel):
    url: str
    title: str
    text: str


@async_retry(max_attempts=2, retry_on=(httpx.HTTPError,))
async def extract_content(url: str, *, max_chars: int = 6000) -> ExtractedContent:
    """Fetch `url` and return its readable text, trimmed to `max_chars`.

    Raises:
        ToolExecutionError: on network failure or non-success HTTP status.
    """

    settings = get_settings()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EvidentResearchBot/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=settings.tool_timeout_seconds, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        logger.warning("content_extraction.failed", url=url, error=str(exc))
        raise ToolExecutionError(f"Failed to fetch {url}", details={"error": str(exc)}) from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url
    text = " ".join(soup.get_text(separator=" ", strip=True).split())
    text = text[:max_chars]

    logger.info("content_extraction.completed", url=url, chars=len(text))
    return ExtractedContent(url=url, title=title, text=text)
