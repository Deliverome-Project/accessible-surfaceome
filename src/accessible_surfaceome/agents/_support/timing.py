"""Per-step wall-clock timing for the surfaceome_v2 pipeline.

A ``TimingRecorder`` collects ``StepTiming`` rows as the pipeline runs.
The pipeline threads one recorder through the dual plan-trim-select
driver, every block-builder, the synthesizer, evidence promotion, the
deterministic-features stub, and filters derivation. Each row carries
``elapsed_s`` plus (when applicable) the model + token counts pulled
from the most recently appended ``UsageRecord`` so the JSON dump and
HTML viewer can answer "where did the time go on this gene" at a
glance.

Designed to be invisible when ``timing=None`` is passed — every entry
point that takes a recorder treats ``None`` as a no-op so existing call
sites don't have to opt in.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.agents._support.pricing import UsageRecord

__all__ = [
    "StepTiming",
    "TimingRecorder",
    "summarize_usage_for_step",
]


@dataclass
class StepTiming:
    """One step's wall-clock + (optionally) model/token attribution."""

    step_name: str
    phase: str
    started_at: str  # ISO-8601 UTC
    elapsed_s: float
    n_items: int | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cost_usd: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def summarize_usage_for_step(
    records: list[UsageRecord], model: str | None
) -> dict[str, Any]:
    """Roll a list of ``UsageRecord`` into the token+cost fields a
    ``StepTiming`` carries. Skips silently when the list is empty."""
    if not records:
        return {}
    return {
        "model": model,
        "input_tokens": sum(r.input_tokens for r in records),
        "output_tokens": sum(r.output_tokens for r in records),
        "cache_creation_input_tokens": sum(
            r.cache_creation_input_tokens for r in records
        ),
        "cache_read_input_tokens": sum(r.cache_read_input_tokens for r in records),
        "cost_usd": round(sum(r.cost_usd for r in records), 6),
    }


@dataclass
class TimingRecorder:
    """Append-only list of ``StepTiming`` rows.

    Use :meth:`step` as a context manager around any logical pipeline
    step; on exit it stamps elapsed_s and pushes a row. The yielded
    handle exposes :meth:`set_usage` so the step body can attach a
    list of ``UsageRecord`` after a model call returns — the recorder
    summarizes them into token/cost columns on the row when the
    context exits.
    """

    entries: list[StepTiming] = field(default_factory=list)

    def add(self, entry: StepTiming) -> None:
        self.entries.append(entry)

    @contextmanager
    def step(
        self,
        step_name: str,
        *,
        phase: str,
        n_items: int | None = None,
        model: str | None = None,
    ) -> Iterator[_StepHandle]:
        """Time a block; emit one StepTiming on exit."""
        started = datetime.now(UTC)
        t0 = time.perf_counter()
        handle = _StepHandle(model=model, n_items=n_items)
        try:
            yield handle
        finally:
            elapsed = time.perf_counter() - t0
            usage_fields = summarize_usage_for_step(
                handle.usage_records, handle.model
            )
            self.entries.append(
                StepTiming(
                    step_name=step_name,
                    phase=phase,
                    started_at=started.isoformat().replace("+00:00", "Z"),
                    elapsed_s=round(elapsed, 3),
                    n_items=handle.n_items,
                    model=usage_fields.get("model") or handle.model,
                    input_tokens=usage_fields.get("input_tokens"),
                    output_tokens=usage_fields.get("output_tokens"),
                    cache_creation_input_tokens=usage_fields.get(
                        "cache_creation_input_tokens"
                    ),
                    cache_read_input_tokens=usage_fields.get(
                        "cache_read_input_tokens"
                    ),
                    cost_usd=usage_fields.get("cost_usd"),
                )
            )

    def to_jsonable(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.entries]


@dataclass
class _StepHandle:
    """Mutable per-step scratchpad the context body writes into."""

    model: str | None = None
    n_items: int | None = None
    usage_records: list[UsageRecord] = field(default_factory=list)

    def set_usage(self, records: list[UsageRecord], *, model: str | None = None) -> None:
        """Attach the token/cost records produced inside this step.

        Pass the model the call was made against (``model`` here wins
        over the value supplied at :meth:`step` open time, so calls
        with mixed-model behavior surface the actually-used model).
        """
        self.usage_records = list(records)
        if model is not None:
            self.model = model

    def set_n_items(self, n: int) -> None:
        self.n_items = n
