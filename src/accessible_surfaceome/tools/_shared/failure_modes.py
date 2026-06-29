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
    # Not a terminal result — a mid-run PTS checkpoint row written to
    # ``agent_run_intermediates`` immediately after the (expensive) plan-trim-
    # select dual completes, BEFORE the builders run. Its only purpose is
    # crash-durability: if the gene then dies hard (Modal eviction / OOM /
    # builder exception) before the driver publishes a terminal row, this row
    # still carries the serialized PTS dual so a resume can reconstruct
    # ``cached_dual`` and skip re-paying for plan-trim-select. Written ONLY
    # after the PTS cost cap passes — an over-cap dual aborts to
    # ``cost_ceiling_pts`` first and never leaves a resumable checkpoint, so
    # resuming this mode can't smuggle an over-cap gene past the cap. Superseded
    # by a later terminal row (``ok`` / a failure) for the same gene when the
    # run finishes. See ``QUARANTINE_FAILURE_MODES`` / ``RESUMABLE_FAILURE_MODES``.
    "pts_checkpoint",
    # Anything that didn't slot into the above. Default fallback so a
    # newly-introduced abort path that isn't yet wired here still
    # tags itself instead of staying empty.
    "unknown",
]

# Over-cost-cap aborts. A gene whose latest intermediates row carries one of
# these has already burned the per-gene budget; the sweep must NOT auto-resume
# it — it is quarantined for manual review (raise the ceiling deliberately, or
# investigate why it's pathological), per the operator's explicit choice.
QUARANTINE_FAILURE_MODES: frozenset[str] = frozenset(
    {"cost_ceiling_pts", "cost_ceiling_total"}
)

# Graceful, non-cap failures (and the mid-run checkpoint) whose intermediates
# carry a usable plan-trim-select dual. A resume can reconstruct ``cached_dual``
# from these and skip re-paying ~$1.35 of PTS spend. Deliberately excludes the
# quarantine modes (we don't auto-resume over-cap genes) and ``pts_failure``
# (no dual was produced) and ``ok`` (already complete).
RESUMABLE_FAILURE_MODES: frozenset[str] = frozenset(
    {"validation_failed", "synth_draft_missing", "schema_drift", "pts_checkpoint"}
)


__all__ = [
    "QUARANTINE_FAILURE_MODES",
    "RESUMABLE_FAILURE_MODES",
    "FailureMode",
]
