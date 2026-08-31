from sqlalchemy.orm import Session

from app.models.telemetry import Usage

# Approximate public list pricing per 1M tokens, USD, as of this writing. These are
# rough estimates for dashboard purposes only, not a billing-accurate source of truth.
# gemini-3.6-flash and openai/gpt-oss-20b (Groq) — see app/core/config.py — have no
# confirmed public pricing available to add here — they intentionally fall through to the
# (0.0, 0.0) default below rather than a fabricated number; cost for those models will show
# as $0.00 (visibly unpriced) until real pricing is added.
_PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}


def estimate_cost_breakdown(model: str, input_tokens: int, output_tokens: int) -> tuple[float, float, float]:
    """Returns (input_cost_usd, output_cost_usd, total_cost_usd) — computed
    separately (not just summed) so both halves can be stored and reported
    individually, per the Week 6 cost-tracking requirement, rather than only
    ever exposing the combined total."""
    input_rate, output_rate = _PRICING_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    input_cost = round(input_tokens * input_rate / 1_000_000, 6)
    output_cost = round(output_tokens * output_rate / 1_000_000, 6)
    return input_cost, output_cost, round(input_cost + output_cost, 6)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Total-only convenience wrapper around estimate_cost_breakdown(), kept
    for call sites that only ever needed the combined figure."""
    return estimate_cost_breakdown(model, input_tokens, output_tokens)[2]


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

    input_cost, output_cost, total_cost = estimate_cost_breakdown(model, input_tokens, output_tokens)
    db.add(
        Usage(
            user_id=user_id,
            workspace_id=workspace_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            cost_usd=total_cost,
        )
    )
    db.commit()
