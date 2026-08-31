"""Groq support (added 2026-08-31): an OpenAI-compatible fast-inference API
(groq.com — Llama/Mixtral/Gemma models), not xAI's "Grok". Verifies
generate_reply/generate_with_tools actually dispatch to the Groq client and
model when provider="groq", using a fake OpenAI-shaped client rather than a
real network call.
"""

from dataclasses import dataclass

from app.services.llm_service import _get_groq_client, generate_reply, generate_with_tools


@dataclass
class _FakeUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class _FakeMessage:
    content: str | None
    tool_calls: list | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list
    usage: _FakeUsage


def _install_fake_groq_client(monkeypatch, response: _FakeResponse, capture: dict):
    class _FakeCompletions:
        def create(self, **kwargs):
            capture["kwargs"] = kwargs
            return response

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    _get_groq_client.cache_clear()
    monkeypatch.setattr("app.services.llm_service._get_groq_client", lambda: _FakeClient())


def test_generate_reply_dispatches_to_groq_and_uses_the_configured_model(monkeypatch):
    capture: dict = {}
    response = _FakeResponse(
        choices=[_FakeChoice(message=_FakeMessage(content="Hello from Groq."))],
        usage=_FakeUsage(prompt_tokens=12, completion_tokens=4),
    )
    _install_fake_groq_client(monkeypatch, response, capture)

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "groq_model", "openai/gpt-oss-20b")

    result = generate_reply(system_prompt="You are terse.", history=[{"role": "user", "content": "hi"}], provider="groq")

    assert result.text == "Hello from Groq."
    assert result.input_tokens == 12
    assert result.output_tokens == 4
    assert capture["kwargs"]["model"] == "openai/gpt-oss-20b"


def test_generate_with_tools_dispatches_to_groq(monkeypatch):
    capture: dict = {}
    response = _FakeResponse(
        choices=[_FakeChoice(message=_FakeMessage(content="No tool needed.", tool_calls=[]))],
        usage=_FakeUsage(prompt_tokens=8, completion_tokens=2),
    )
    _install_fake_groq_client(monkeypatch, response, capture)

    result = generate_with_tools(
        system_prompt="test",
        history=[{"role": "user", "content": "search"}],
        tools=[{"name": "search_documents", "description": "d", "parameters": {}}],
        provider="groq",
    )

    assert result.text == "No tool needed."
    assert result.tool_calls == []
    assert capture["kwargs"]["tools"][0]["function"]["name"] == "search_documents"
