"""Per-run reproducibility metadata captured at module load + per-call.

These are fields that travel with every annotate run so a 1-year-later
audit can fully reproduce a record from saved metadata alone.

The Tier 3 audit (``docs/audit/r2_and_reproducibility_2026_06_08.md``)
identified six fields missing from the ``agent_run_intermediates`` D1
table that block a full replay of a cohort run:

* ``code_sha`` — git rev at runtime (a bug-fix between two same-
  ``prompt_corpus_version`` runs is otherwise invisible).
* ``model_id`` — the dated alias from ``response.model`` (e.g.
  ``claude-sonnet-4-6-20251022``) rather than the caller's bare
  ``claude-sonnet-4-6`` alias.
* ``api_response_id`` — Anthropic's own response id (``anthropic-...``)
  for cross-referencing against support tickets / billing.
* ``api_stop_reason`` — whether the call ended normally
  (``end_turn``) or hit a guardrail (``max_tokens``, ``stop_sequence``,
  ``tool_use``).
* explicit ``temperature`` — currently defaults to 1.0; cohort runs
  want 0.2 to reduce stochastic variation across the sweep.
* structured ``failure_mode`` — free-text ``error`` only today; an
  enum makes cohort-scale analytics tractable.

This module owns the helpers; the wiring lives in callers (orchestrator,
backoff wrapper, ``publish_intermediates``). See
``docs/audit/reproducibility_followup_2026_06_09.md`` for the integration
TODO list — those edits land after Agents #17/#18/#19 commit so the
worktree-level merge order stays clean.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def code_sha() -> str:
    """Git rev-parse HEAD at module load. Falls back to env (Modal-friendly).

    Order:
      1. ``CODE_SHA`` env var — set explicitly (Modal image build, CI).
      2. ``GIT_COMMIT`` env var — common alias (Modal image build sets
         this by default; many CI systems do too).
      3. ``git rev-parse HEAD`` — works in dev / local sweeps where the
         working tree is a real git checkout.
      4. ``"unknown"`` — never fail; just record absence.

    Truncated to 40 chars (a full git SHA is 40 hex). The truncation
    survives short SHAs too — they pass through unchanged.

    Cached for the process lifetime via ``lru_cache``; the SHA can't
    change mid-run.
    """
    for env in ("CODE_SHA", "GIT_COMMIT"):
        v = os.environ.get(env)
        if v:
            return v.strip()[:40]
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()[:40]
        )
    except Exception:  # noqa: BLE001 — never fail at module load
        return "unknown"


def api_response_metadata(response: Any) -> dict[str, Any]:
    """Extract reproducibility-relevant fields from an Anthropic SDK response.

    Defensive — returns empty dict on any error rather than raising into
    the hot path. The intent is "best-effort capture": a malformed mock
    response in a test or a future SDK shape change must not crash a
    cohort run, but the most common case (a real ``Message``) must
    surface its identifiers.

    Fields:
      * ``api_response_id`` — Anthropic's ``response.id``
        (``anthropic-NN-...``); the cross-reference key for support
        tickets, billing, and any post-mortem against Anthropic's logs.
      * ``api_model`` — ``response.model`` (the resolved model snapshot
        id, e.g. ``claude-sonnet-4-6-20251022`` even when caller passed
        the bare alias ``claude-sonnet-4-6``).
      * ``api_stop_reason`` — one of ``end_turn`` (normal completion),
        ``max_tokens`` (output truncated — bumps ``max_tokens`` are the
        fix), ``stop_sequence`` (caller-supplied stop hit),
        ``tool_use`` (server tool produced its result inside the same
        ``create`` call).

    Callers should stash the returned dict into the per-call usage
    record (the synthesizer's ``BResult`` or a builder's ``UsageRecord``)
    so the round-trip metadata travels with the cost row to D1.
    """
    try:
        return {
            "api_response_id": getattr(response, "id", None),
            "api_model": getattr(response, "model", None),
            "api_stop_reason": getattr(response, "stop_reason", None),
        }
    except Exception:  # noqa: BLE001 — best-effort capture
        return {}


def cohort_temperature() -> float:
    """Cohort-run default temperature for ``messages.create``.

    The Anthropic SDK defaults ``temperature`` to 1.0, which is the
    right value for development and one-off exploration but elevates
    stochastic variation across a 6,500-gene cohort sweep. 0.2 gives
    near-deterministic outputs on the structured-JSON tasks the v2
    pipeline runs (PTS classifier, block builders, synthesizer) without
    sacrificing the model's reasoning quality.

    Override via the ``COHORT_TEMPERATURE`` env var when a one-off run
    wants the SDK default behavior (e.g. ``COHORT_TEMPERATURE=1.0`` for
    a reproducibility probe of the pre-Tier-3 behavior).

    Returns a float so callers can pass it directly to
    ``messages.create`` (the SDK rejects ints there).
    """
    return float(os.environ.get("COHORT_TEMPERATURE", "0.2"))


__all__ = ["api_response_metadata", "code_sha", "cohort_temperature"]
