from fastapi import APIRouter

router = APIRouter(prefix="/api/models", tags=["models"])

# A small curated catalog for the assistant settings dropdown. Users can still type a
# custom model name via the assistant's model_name override field.
MODEL_CATALOG = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
}


@router.get("")
def list_models() -> dict[str, list[str]]:
    return MODEL_CATALOG
