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
# 2.0-flash's flat deprecation. gemini-2.5-flash was the only model this key could reach,
# and is also subject to a hard 20 requests/day free-tier cap (confirmed via a real
# RESOURCE_EXHAUSTED response) — see docs/performance/README.md.
MODEL_CATALOG = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
}


@router.get("")
def list_models() -> dict[str, list[str]]:
    return MODEL_CATALOG
