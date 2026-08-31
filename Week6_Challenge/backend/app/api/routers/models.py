from fastapi import APIRouter

router = APIRouter(prefix="/api/models", tags=["models"])

# A small curated catalog for the assistant settings dropdown. Users can still type a
# custom model name via the assistant's model_name override field.
#
# gemini-2.0-flash was removed 2026-08-12 after live testing hit a real 404 NOT_FOUND —
# Google retired it globally ("no longer available... use a newer model"). This class of
# failure (a previously-valid model silently retired) recurred at least once before in
# this repo's history — this catalog needs periodic revalidation, not a one-time fix.
#
# gemini-2.5-pro and gemini-2.5-flash-lite are kept in the catalog despite also returning
# 404 ("no longer available to new users") when tested live with this dev API key — that
# message is account-specific (implies older/different accounts may retain access), unlike
# 2.0-flash's flat deprecation. gemini-2.5-flash was, at the time, the only model this key
# could reach, and was also subject to a hard 20 requests/day free-tier cap (confirmed via
# a real RESOURCE_EXHAUSTED response) — see docs/performance/README.md.
#
# Update 2026-08-31: gemini-2.5-flash itself is now also retired (live 404 NOT_FOUND —
# "no longer available to new users... use models/gemini-3.6-flash"). gemini-3.6-flash is
# added below and is now the configured default (app/core/config.py). Note this does NOT
# by itself restore chat functionality in this dev environment: a second, separate live
# error (403 PERMISSION_DENIED — "Your project has been denied access") shows the
# configured Google Cloud project is blocked at the account level, independent of which
# model name is requested. That requires a new/unblocked API key to fix, not a code change.
# Groq (groq.com) added 2026-08-31 as a third provider — an OpenAI-compatible fast-inference
# API for open-weight models, not to be confused with xAI's "Grok". No embeddings endpoint
# exists on Groq (see Settings.groq_api_key's docstring in config.py), so it only appears
# here for chat/agent models, never as an embedding option.
#
# Only openai/gpt-oss-20b is confirmed live with this dev Groq key (plain chat and
# tool-calling both verified). llama-3.3-70b-versatile, llama-3.1-8b-instant, and
# llama-3.1-70b-versatile all returned a live 404 ("does not exist or you do not have
# access to it"); gemma2-9b-it and llama3-70b-8192 returned a live 400 ("has been
# decommissioned"). Kept out of the catalog entirely rather than listed as a false option.
MODEL_CATALOG = {
    "gemini": ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    "groq": ["openai/gpt-oss-20b"],
}


@router.get("")
def list_models() -> dict[str, list[str]]:
    return MODEL_CATALOG
