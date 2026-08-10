"""Search and content-extraction tool tests.

These tools call the network via `httpx.AsyncClient`; here we monkeypatch
the client so we test our own parsing logic (DuckDuckGo HTML scraping,
Tavily JSON parsing, readable-text extraction) without ever making a real
HTTP request.
"""

from __future__ import annotations

import httpx

from app.tools import content_extraction_tool, search_tool

_DUCKDUCKGO_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/1">First Result</a>
  <a class="result__snippet">First snippet text.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/2">Second Result</a>
  <a class="result__snippet">Second snippet text.</a>
</div>
</body></html>
"""


class _FakeResponse:
    def __init__(self, *, text: str = "", json_data=None, status_code: int = 200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, *args, **kwargs):
        return self._response

    async def get(self, *args, **kwargs):
        return self._response


async def test_duckduckgo_search_parses_results(monkeypatch):
    fake_response = _FakeResponse(text=_DUCKDUCKGO_HTML)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response))

    results = await search_tool._search_duckduckgo("test query", max_results=5)

    assert len(results) == 2
    assert results[0].title == "First Result"
    assert results[0].url == "https://example.com/1"
    assert results[0].snippet == "First snippet text."


async def test_tavily_search_parses_results(monkeypatch):
    payload = {
        "results": [
            {"title": "Tavily Result", "url": "https://example.com/t", "content": "Tavily snippet"},
        ]
    }
    fake_response = _FakeResponse(json_data=payload)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response))

    results = await search_tool._search_tavily("test query", 5, "fake-api-key")

    assert len(results) == 1
    assert results[0].title == "Tavily Result"
    assert results[0].snippet == "Tavily snippet"


async def test_extract_content_strips_scripts_and_returns_text(monkeypatch):
    html = "<html><head><title>My Page</title></head><body><script>evil()</script><p>Hello world</p></body></html>"
    fake_response = _FakeResponse(text=html)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient(fake_response))

    content = await content_extraction_tool.extract_content("https://example.com/page")

    assert content.title == "My Page"
    assert "Hello world" in content.text
    assert "evil" not in content.text
