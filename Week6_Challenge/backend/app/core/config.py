from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173"

    database_url: str = "sqlite:///./app.db"

    secret_key: str = "changeme-generate-a-real-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    # gemini-2.5-flash was retired (confirmed live 2026-08-31: 404 NOT_FOUND, "no longer
    # available to new users... use models/gemini-3.6-flash"). Updated to the model the
    # provider's own error response names as the replacement — see app/api/routers/models.py
    # for the full deprecation history and the separate (unrelated) 403 PERMISSION_DENIED
    # finding, which is an account/project-access issue this config change cannot fix.
    gemini_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Groq (groq.com — fast Llama/Mixtral/Gemma inference, an OpenAI-compatible API, not
    # to be confused with xAI's "Grok"). No embeddings endpoint exists on Groq, so
    # embed_texts() never routes to it — see llm_service.py::embed_texts.
    #
    # openai/gpt-oss-20b confirmed live 2026-08-31 with a real Groq key: plain chat and
    # tool-calling both work. Several other commonly-referenced Groq model names were
    # tried against the same key and failed live: llama-3.3-70b-versatile / llama-3.1-8b-
    # instant / llama-3.1-70b-versatile ("does not exist or you do not have access to
    # it" — 404) and gemma2-9b-it / llama3-70b-8192 ("has been decommissioned" — 400).
    # Groq's available-model list is account/tier-specific and changes over time — treat
    # this default as verified-for-this-key, not a universal guarantee.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    upload_dir: str = "uploads"
    max_upload_bytes: int = 20 * 1024 * 1024
    chunk_size: int = 1000
    chunk_overlap: int = 200
    rag_top_k: int = 5
    rag_min_score: float = 0.65
    memory_context_limit: int = 10
    conversation_history_limit: int = 20

    log_level: str = "INFO"
    log_dir: str = "logs"

    llm_request_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 0.5

    agent_max_iterations: int = 5
    tool_timeout_seconds: float = 15.0

    guardrails_block_on_injection: bool = False
    max_input_chars: int = 8000

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
