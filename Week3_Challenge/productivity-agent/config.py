"""
config.py
---------
All configuration lives here, read from environment variables.
No API keys or secrets are ever hard-coded in this file — see .env.example
for the variables this app expects.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central place every other module reads configuration from."""

    # --- LLM provider ---
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GENERATION_MODEL: str = os.environ.get("GENERATION_MODEL", "gemini-2.5-flash-lite")

    # --- Flask ---
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")

    # --- Database ---
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///productivity_agent.db")

    # --- Agent execution limits (Requirement 9) ---
    # 8 steps: enough for the deepest real workflow here (Daily Planning
    # is 4 tool calls + a final answer) with headroom for a wrong turn,
    # without letting a confused loop run indefinitely.
    MAX_AGENT_STEPS: int = int(os.environ.get("MAX_AGENT_STEPS", "8"))
    # 2 retries (3 attempts total): enough to ride out a transient
    # hiccup (a flaky LLM call, a momentary DB lock) without masking a
    # genuinely broken call behind a long, silent delay.
    MAX_TOOL_RETRIES: int = int(os.environ.get("MAX_TOOL_RETRIES", "2"))
    # 30s: generous enough for a slow LLM-backed tool call (e.g.
    # extract_meeting_actions) under normal conditions, short enough
    # that a hung request still fails within one user-perceived "is
    # this stuck?" window instead of hanging indefinitely.
    TOOL_TIMEOUT_SECONDS: int = int(os.environ.get("TOOL_TIMEOUT_SECONDS", "30"))

    # --- Logging ---
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIRECTORY: str = os.environ.get("LOG_DIRECTORY", "logs")

    def validate(self):
        """
        Check that required settings are actually present. Called once at
        startup so a missing API key fails fast with a clear message,
        instead of crashing deep inside an LLM call later.
        """
        missing = []

        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.SECRET_KEY:
            missing.append("SECRET_KEY")

        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): " + ", ".join(missing) +
                ". Copy .env.example to .env and fill in real values."
            )


settings = Settings()
