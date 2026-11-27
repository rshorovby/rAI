"""Оценка стоимости вызовов Gemini по usage_metadata."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

# USD за 1M токенов (Standard, ноябрь 2026). thinking входит в output.
MODEL_RATES: Mapping[str, tuple[float, float]] = {
    "gemini-4-neon": (3.0, 15.0),
    "gemini-4-hydrogen": (1.5, 7.5),
    "gemini-4-carbon": (4.0, 20.0),
    "gemini-4-argon": (4.0, 20.0),
    "gemini-3.1-pro-preview": (2.0, 12.0),
    "gemini-3.1-pro": (2.0, 12.0),
    "gemini-3.5-flash": (1.5, 9.0),
    "gemini-3-flash-preview": (0.5, 3.0),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.3, 2.5),
}

DEFAULT_RATES = (3.0, 15.0)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    model: str = ""
    cached_input_tokens: int = 0

    @property
    def billable_output(self) -> int:
        return self.output_tokens + self.thinking_tokens


def rates_for(model: str) -> tuple[float, float]:
    key = (model or "").strip().lower()
    if key in MODEL_RATES:
        return MODEL_RATES[key]
    for name, rates in MODEL_RATES.items():
        if name in key or key in name:
            return rates
    return DEFAULT_RATES


def _cached_input_multiplier(model: str) -> float:
    # Gemini 4: 95% скидка на implicit cache; более ранние модели: 90%.
    return 0.05 if "gemini-4" in (model or "").strip().lower() else 0.10


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    model: str = "",
    cached_input_tokens: int = 0,
    service_tier: Optional[str] = None,
) -> float:
    in_rate, out_rate = rates_for(model)
    total_in = max(0, int(input_tokens))
    cached_in = min(total_in, max(0, int(cached_input_tokens)))
    uncached_in = total_in - cached_in
    cached_rate = in_rate * _cached_input_multiplier(model)
    billable_out = max(0, int(output_tokens)) + max(0, int(thinking_tokens))
    cost = (
        uncached_in / 1_000_000 * in_rate
        + cached_in / 1_000_000 * cached_rate
        + billable_out / 1_000_000 * out_rate
    )
    if (service_tier or "").strip().lower() == "flex":
        cost *= 0.5
    return cost


def usage_from_response(response, model: str = "") -> Usage:
    """Достаёт токены из GenerateContentResponse.usage_metadata."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return Usage(model=model)

    def _get(name: str) -> int:
        value = getattr(meta, name, None)
        if value is None and isinstance(meta, dict):
            value = meta.get(name)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    input_tokens = _get("prompt_token_count") or _get("input_tokens")
    output_tokens = _get("candidates_token_count") or _get("output_tokens")
    thinking_tokens = _get("thoughts_token_count") or _get("thinking_tokens")
    cached_input_tokens = _get("cached_content_token_count")
    # некоторые SDK кладут thinking внутрь candidates; тогда не дублируем
    total = _get("total_token_count")
    if total and input_tokens and not output_tokens:
        output_tokens = max(0, total - input_tokens - thinking_tokens)

    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        model=model,
        cached_input_tokens=cached_input_tokens,
    )


def cost_for_usage(
    usage: Usage,
    model: Optional[str] = None,
    service_tier: Optional[str] = None,
) -> float:
    return estimate_cost(
        usage.input_tokens,
        usage.output_tokens,
        usage.thinking_tokens,
        model or usage.model,
        cached_input_tokens=usage.cached_input_tokens,
        service_tier=service_tier,
    )
