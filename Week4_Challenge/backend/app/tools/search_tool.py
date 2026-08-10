"""Search Tool.

Uses Tavily (an LLM-oriented search API) when `TAVILY_API_KEY` is configured;
otherwise falls back to scraping DuckDuckGo's HTML endpoint, which requires
no API key. Both paths are real, working implementations — the fallback is
not a stub.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.config.logging_config import get_logger
from app.config.settings import get_settings
from app.utils.errors import SearchFailureError
from app.utils.retry import async_retry

logger = get_logger("tools.search")

_DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
_TAVILY_URL = "https://api.tavily.com/search"


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


async def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web and return up to `max_results` results.

    Raises:
        SearchFailureError: if the search could not be completed at all
        (both the primary provider and network are unreachable). Returning
        zero *results* for a valid-but-unproductive query is not an error —
        callers must handle an empty list gracefully.
    """

    settings = get_settings()
    try:
        if settings.tavily_api_key:
            return await _search_tavily(query, max_results, settings.tavily_api_key)
        return await _search_duckduckgo(query, max_results)
    except SearchFailureError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize all transport errors
        logger.error("search.failed", query=query, error=str(exc))
        raise SearchFailureError(f"Search failed for query: {query!r}", details={"error": str(exc)}) from exc


@async_retry(max_attempts=2, retry_on=(httpx.HTTPError,))
async def _search_tavily(query: str, max_results: int, api_key: str) -> list[SearchResult]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.tool_timeout_seconds) as client:
        response = await client.post(
            _TAVILY_URL,
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
        )
        response.raise_for_status()
        payload = response.json()

    results = [
        SearchResult(
            title=item.get("title", "Untitled"),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
        )
        for item in payload.get("results", [])[:max_results]
    ]
    logger.info("search.tavily.completed", query=query, result_count=len(results))
    return results


@async_retry(max_attempts=2, retry_on=(httpx.HTTPError,))
async def _search_duckduckgo(query: str, max_results: int) -> list[SearchResult]:
    settings = get_settings()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EvidentResearchBot/1.0)"}
    async with httpx.AsyncClient(timeout=settings.tool_timeout_seconds, headers=headers) as client:
        response = await client.post(_DUCKDUCKGO_HTML_URL, data={"q": query})
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResult] = []
    for result_div in soup.select("div.result")[: max_results * 2]:
        link = result_div.select_one("a.result__a")
        snippet_el = result_div.select_one("a.result__snippet") or result_div.select_one(".result__snippet")
        if not link or not link.get("href"):
            continue
        results.append(
            SearchResult(
                title=link.get_text(strip=True) or "Untitled",
                url=link["href"],
                snippet=snippet_el.get_text(strip=True) if snippet_el else "",
            )
        )
        if len(results) >= max_results:
            break

    logger.info("search.duckduckgo.completed", query=query, result_count=len(results))
    return results
