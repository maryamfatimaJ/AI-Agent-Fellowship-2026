import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import limiter
from app.database.base import Base
from app.database.deps import get_db
from app.main import app
from app.services.llm_service import GenerationResult

MOCK_VOCAB = ["refund", "policy", "shipping", "warranty", "onboarding"]


def _mock_embed(texts, provider=None, task_type="RETRIEVAL_DOCUMENT"):
    """Deterministic fake embedding: one dim per keyword, value = occurrence count.
    Lets retrieval tests assert that a chunk mentioning a keyword outranks one that
    doesn't, without any network call or real embedding model.
    """
    vectors = []
    for text in texts:
        lowered = text.lower()
        vectors.append([float(lowered.count(word)) for word in MOCK_VOCAB])
    return vectors


class _MockLLMCalls:
    def __init__(self):
        self.generate_calls = []

    def generate_reply(self, system_prompt, history, temperature=0.7, max_tokens=1024, provider=None, model=None):
        self.generate_calls.append({"system_prompt": system_prompt, "history": history})
        return GenerationResult(text="Mock assistant reply.", input_tokens=10, output_tokens=5)


@pytest.fixture()
def mock_llm(monkeypatch):
    calls = _MockLLMCalls()
    monkeypatch.setattr("app.services.chat_service.generate_reply", calls.generate_reply)
    monkeypatch.setattr("app.services.skill_service.generate_reply", calls.generate_reply)
    monkeypatch.setattr("app.rag.retrieval.embed_texts", _mock_embed)
    monkeypatch.setattr(
        "app.memory.memory_service.generate_reply",
        lambda *args, **kwargs: GenerationResult(text="[]", input_tokens=5, output_tokens=2),
    )
    # LLM-as-judge (Week 6 evaluation harness) — same deterministic-mock treatment as
    # every other generate_reply call site, so eval-harness tests never make a real
    # (would-fail-anyway, no test API key) network attempt against the Gemini SDK.
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply",
        lambda *args, **kwargs: GenerationResult(
            text=(
                '{"correctness": 4, "relevance": 4, "completeness": 4, "clarity": 4, '
                '"groundedness": 4, "explanation": "Mock judge score."}'
            ),
            input_tokens=8,
            output_tokens=4,
        ),
    )
    return calls


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The auth rate limiter is disabled by default for every test — the suite legitimately
    registers/logs in far more than a real user would in a minute (many isolated test
    users per file). A dedicated test re-enables it explicitly to prove it actually works;
    see tests/unit/test_rate_limit.py."""
    limiter.reset()
    limiter.enabled = False
    yield
    limiter.enabled = False


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    # Background tasks (e.g. scheduled memory extraction) open their own fresh
    # session via `from app.database.session import SessionLocal` rather than
    # FastAPI's get_db dependency override — patch the module-level factory
    # itself so those sessions land on this same in-memory StaticPool-shared
    # connection instead of the real (file-based) test.db engine.
    monkeypatch.setattr("app.database.session.SessionLocal", session_local)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session, mock_llm):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        test_client.mock_llm = mock_llm
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client, email: str, password: str = "pass1234") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
