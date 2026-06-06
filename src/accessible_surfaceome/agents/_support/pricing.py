"""Per-model token pricing + cost accounting for the v1.0.0 deep-dive runners.

The Anthropic ``messages.create`` response carries a ``usage`` block with
four token counts: ``input_tokens`` (uncached input), ``output_tokens``,
``cache_creation_input_tokens`` (5-minute cache writes), and
``cache_read_input_tokens`` (cache hits). We bill all four against the
per-MTok rates published at
https://platform.claude.com/docs/en/about-claude/pricing (snapshot
captured below — re-fetch if a model price moves).

Pricing snapshot taken 2026-05-15; all numbers in **USD per million
tokens**. 1-hour cache writes are not used by the runners today, so the
table only carries the four columns the SDK actually reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "PRICING",
    "ModelPricing",
    "UsageRecord",
    "cost_for_usage",
    "summarize_usage",
]


@dataclass(frozen=True)
class ModelPricing:
    """USD per million tokens, by token-category column.

    Field names match the Anthropic SDK ``Usage`` block one-for-one so the
    cost calculation is a straight per-key multiply.
    """

    input_tokens: float
    output_tokens: float
    cache_creation_input_tokens: float  # 5-minute cache write
    cache_read_input_tokens: float


# Pricing table — single source of truth. Future model swaps need one edit.
PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(
        input_tokens=3.0,
        output_tokens=15.0,
        cache_creation_input_tokens=3.75,
        cache_read_input_tokens=0.30,
    ),
    "claude-opus-4-7": ModelPricing(
        input_tokens=5.0,
        output_tokens=25.0,
        cache_creation_input_tokens=6.25,
        cache_read_input_tokens=0.50,
    ),
    # opus-4-8 priced same as 4-7 pending confirmed list price; only affects
    # cost reporting (recomputable), not verdicts.
    "claude-opus-4-8": ModelPricing(
        input_tokens=5.0,
        output_tokens=25.0,
        cache_creation_input_tokens=6.25,
        cache_read_input_tokens=0.50,
    ),
    "claude-haiku-4-5": ModelPricing(
        input_tokens=1.0,
        output_tokens=5.0,
        cache_creation_input_tokens=1.25,
        cache_read_input_tokens=0.10,
    ),
}


@dataclass
class UsageRecord:
    """One ``messages.create`` call's token usage, plus its dollar cost.

    The four token fields mirror the SDK's ``Usage`` shape exactly; ``cost_usd``
    is computed from them at the model's per-MTok rate when the record is
    appended.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float = 0.0


def cost_for_usage(usage: UsageRecord, model: str) -> float:
    """USD cost for a single ``messages.create`` call's token counts.

    Unknown models raise ``KeyError`` — we want a loud failure rather than a
    silently-zero cost when a new model gets wired up without a pricing
    table entry.
    """
    p = PRICING[model]
    return (
        usage.input_tokens * p.input_tokens
        + usage.output_tokens * p.output_tokens
        + usage.cache_creation_input_tokens * p.cache_creation_input_tokens
        + usage.cache_read_input_tokens * p.cache_read_input_tokens
    ) / 1_000_000.0


@dataclass
class UsageSummary:
    """Per-agent rollup of one run's per-iteration token usage."""

    model: str
    n_iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float = 0.0
    iterations: list[UsageRecord] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "n_iterations": self.n_iterations,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "iterations": [
                {
                    "input_tokens": it.input_tokens,
                    "output_tokens": it.output_tokens,
                    "cache_creation_input_tokens": it.cache_creation_input_tokens,
                    "cache_read_input_tokens": it.cache_read_input_tokens,
                    "cost_usd": round(it.cost_usd, 6),
                }
                for it in self.iterations
            ],
        }


def summarize_usage(records: list[UsageRecord], model: str) -> UsageSummary:
    """Roll a list of per-iteration ``UsageRecord``s into a ``UsageSummary``."""
    summary = UsageSummary(model=model, iterations=list(records))
    for r in records:
        summary.n_iterations += 1
        summary.input_tokens += r.input_tokens
        summary.output_tokens += r.output_tokens
        summary.cache_creation_input_tokens += r.cache_creation_input_tokens
        summary.cache_read_input_tokens += r.cache_read_input_tokens
        summary.cost_usd += r.cost_usd
    return summary


def record_from_response(usage: object, model: str) -> UsageRecord:
    """Build a ``UsageRecord`` from an Anthropic SDK ``response.usage``.

    The SDK exposes ``input_tokens`` and ``output_tokens`` always; the cache
    fields are ``None`` when prompt caching wasn't engaged. We default
    missing fields to 0 so cost math is total-of-all-buckets without
    branching at every call site.
    """
    rec = UsageRecord(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        cache_creation_input_tokens=int(
            getattr(usage, "cache_creation_input_tokens", 0) or 0
        ),
        cache_read_input_tokens=int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        ),
    )
    rec.cost_usd = cost_for_usage(rec, model)
    return rec
