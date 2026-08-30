from sqlalchemy.orm import Session

from app.models.telemetry import Usage

# Approximate public list pricing per 1M tokens, USD, as of this writing. These are
# rough estimates for dashboard purposes only, not a billing-accurate source of truth.
_PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _PRICING_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 6)


def record_usage(
    db: Session,
    user_id: str,
    workspace_id: str | None,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    if input_tokens == 0 and output_tokens == 0:
        return

    db.add(
        Usage(
            user_id=user_id,
            workspace_id=workspace_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
        )
    )
    db.commit()
