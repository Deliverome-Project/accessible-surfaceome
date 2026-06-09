"""Structured failure modes for a v2 annotate run.

Used by ``AnnotateResultV2.error_mode`` (free-text ``error`` stays —
this is a structured complement, not a replacement, so cohort-scale
analytics can group abort reasons without parsing prose).

Owned by ``tools/_shared`` (alongside ``models.py``) so the enum is
import-safe from both the orchestrator side (``agents/surfaceome_v2/``)
and the cloud-side analytics consumers
(``cloud/intermediates.py``, ``cloud/surface_annotation.py``,
post-cohort jupyter notebooks). Kept in its own file rather than
inside ``models.py`` so the Tier-3 follow-up commit doesn't collide
with Agent #17's in-flight edits to ``models.py``.

A ``Literal`` (not an ``Enum``) so it serializes to a bare string in
JSON / D1 — matches how the rest of the v2 ``error: str | None`` field
is stored, makes the downstream SQL straightforward
(``WHERE failure_mode = 'cost_ceiling_pts'``), and avoids a Pydantic
``Enum``-vs-str-coercion gotcha at the D1 boundary.
"""

from __future__ import annotations

from typing import Literal

FailureMode = Literal[
    # Happy path — the only "success" value. Stamped on every result that
    # produced a valid SurfaceomeRecord. Default for ``AnnotateResultV2``.
    "ok",
    # PTS (plan-trim-select) dual A1/A2 cost exceeded the ~$5 cap. The
    # post-PTS checkpoint aborts before any builders run so the per-gene
    # spend stops growing. (Cap value lives in the orchestrator; this is
    # just the label.)
    "cost_ceiling_pts",
    # Total cost (PTS + builders + synth) exceeded the ~$7 per-gene cap
    # at the post-builders checkpoint. Aborts before the synth call so
    # the cohort doesn't billable-runaway on a pathological literature-
    # dense gene.
    "cost_ceiling_total",
    # Synthesizer draft failed Pydantic schema validation after
    # ``MAX_REPAIRS`` repair-loop attempts. The raw_json is preserved in
    # intermediates for post-mortem; record is None.
    "validation_failed",
    # Synthesizer call returned but never produced a fenced JSON block
    # at all (no ```json``` fence to extract from). Different shape from
    # ``validation_failed`` — the model wandered off-spec entirely.
    "synth_draft_missing",
    # The dual PTS call itself raised (not a cost-ceiling abort — a real
    # exception from inside the planner / trim / select stages). The
    # exception's str is captured in the free-text ``error`` field.
    "pts_failure",
    # One of the 9 block builders raised. Distinct from a validation
    # failure inside a builder's repair loop, which returns ``None``
    # silently — this is a hard exception that aborted the builder
    # dispatch.
    "builder_failure",
    # The tenacity backoff wrapper in ``api_retry`` exhausted its 5
    # attempts on a transient 429 / 5xx. The original exception
    # propagates with its type preserved; ``error`` carries the
    # underlying message.
    "rate_limit_unrecovered",
    # Any other ``anthropic.APIError`` not covered by the more specific
    # categories above — schema-too-large, content-policy, etc. Free-
    # text ``error`` is the place to look for the specific shape.
    "api_error_other",
    # Final ``SurfaceomeRecord.model_validate`` failed even after the
    # synth draft passed. Indicates a schema-version drift between the
    # draft schema and the canonical record schema — a high-priority
    # post-mortem signal.
    "schema_drift",
    # Anything that didn't slot into the above. Default fallback so a
    # newly-introduced abort path that isn't yet wired here still
    # tags itself instead of staying empty.
    "unknown",
]


__all__ = ["FailureMode"]
