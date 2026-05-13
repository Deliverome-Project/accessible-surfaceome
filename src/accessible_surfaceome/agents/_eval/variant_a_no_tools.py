"""Variant A — pure model, no tools at all.

Uses ``anthropic.messages.create`` with the triage system prompt + a
kickoff message that contains only the gene symbol. No custom tools.
No builtins. No tool-use loop. The model emits a single fenced JSON
block as its final response, which we parse and return.

Tests how much of the verdict comes from trained knowledge alone,
across Haiku 4.5 / Sonnet 4.6 / Opus 4.7.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

# Per-million-token rates for cost accounting. Update as Anthropic pricing
# changes; these are list prices (no batch discount).
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
}


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class PureModelResult:
    gene_symbol: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_s: float
    raw_response: str
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


def run_variant_a(
    *,
    gene_symbol: str,
    model: str,
    system_prompt: str,
    client: Anthropic,
    max_tokens: int = 2048,
) -> tuple[dict[str, Any] | None, PureModelResult]:
    """Run variant A for one gene with the given model.

    Returns ``(triage_draft_dict | None, telemetry)``. ``None`` when the
    model didn't emit a JSON-fenced block we could parse.

    The system prompt is marked ``cache_control: ephemeral`` so a
    consecutive sweep over many genes pays the system-prompt input cost
    once per 5-minute window (~70% cost reduction at scale; harmless
    for one-shot use).
    """

    user_message = (
        f"Triage the human gene `{gene_symbol}`. Emit one "
        f"`TriageRecordDraft` JSON block as your final response. "
        f"You have no tools available; reason from your trained "
        f"knowledge of this protein's biology."
    )

    started = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    latency = time.monotonic() - started

    raw = _extract_text(response)
    parsed = _parse_triage_json(raw)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = _estimate_cost(
        model=model,
        in_tok=prompt_tokens,
        out_tok=completion_tokens,
        cache_creation_tok=cache_creation_tokens,
        cache_read_tok=cache_read_tokens,
    )

    return parsed, PureModelResult(
        gene_symbol=gene_symbol,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        cost_usd=cost,
        latency_s=latency,
        raw_response=raw,
    )


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def _parse_triage_json(raw: str) -> dict[str, Any] | None:
    candidates = _FENCED_JSON_RE.findall(raw)
    for cand in reversed(candidates):
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "verdict" in data and "accessibility_signal" in data:
            return data
    return None


def _estimate_cost(
    *,
    model: str,
    in_tok: int,
    out_tok: int,
    cache_creation_tok: int = 0,
    cache_read_tok: int = 0,
) -> float:
    """Total $ cost. Mirrors the runner's pricing model.

    Anthropic prompt-caching tiers (as of 2026-Q1):
      * ``cache_creation_input_tokens`` billed at 1.25× the base input rate.
      * ``cache_read_input_tokens``     billed at 0.10× the base input rate.
      * ``input_tokens`` excludes both — add them separately.
    """
    in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
    uncached_in = in_tok * in_price
    cache_write = cache_creation_tok * in_price * 1.25
    cache_read = cache_read_tok * in_price * 0.10
    output = out_tok * out_price
    return (uncached_in + cache_write + cache_read + output) / 1_000_000


def load_triage_system_prompt() -> str:
    """Load the live surface_triage system prompt for variant A."""

    path = (
        Path(__file__).resolve().parent.parent
        / "surface_triage"
        / "prompts"
        / "system.md"
    )
    return path.read_text()


__all__ = [
    "run_variant_a",
    "PureModelResult",
    "load_triage_system_prompt",
    "MODEL_PRICING",
]
