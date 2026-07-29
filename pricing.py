"""Оценка стоимости вызовов Gemini по usage_metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

# USD за 1M токенов (Standard, июль 2026). thinking входит в output.
MODEL_RATES: Mapping[str, tuple[float, float]] = {
    "gemini-3.1-pro-preview": (2.0, 12.0),
    "gemini-3.1-pro": (2.0, 12.0),
    "gemini-3.5-flash": (1.5, 9.0),
    "gemini-3-flash-preview": (0.5, 3.0),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.3, 2.5),
}

DEFAULT_RATES = (2.0, 12.0)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    model: str = ""

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


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
    model: str = "",
) -> float:
    in_rate, out_rate = rates_for(model)
    billable_out = max(0, int(output_tokens)) + max(0, int(thinking_tokens))
    return (
        max(0, int(input_tokens)) / 1_000_000 * in_rate
        + billable_out / 1_000_000 * out_rate
    )


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
    # некоторые SDK кладут thinking внутрь candidates; тогда не дублируем
    total = _get("total_token_count")
    if total and input_tokens and not output_tokens:
        output_tokens = max(0, total - input_tokens - thinking_tokens)

    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        model=model,
    )


def cost_for_usage(usage: Usage, model: Optional[str] = None) -> float:
    return estimate_cost(
        usage.input_tokens,
        usage.output_tokens,
        usage.thinking_tokens,
        model or usage.model,
    )
