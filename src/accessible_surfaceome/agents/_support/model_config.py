"""Single source of truth for the v2 deep-dive agent model.

The production deep-dive (``plan_trim_select`` dual + 9 block builders +
synthesizer) all run on one Sonnet model. Centralizing the id here — and
making it env-overridable — means a model trial (e.g. Sonnet 5 vs the
current Sonnet 4.6) flips ONE knob instead of editing five module
constants, and the override is reversible without a code change.

Set ``SURFACEOME_DEEP_DIVE_MODEL`` to override (e.g.
``SURFACEOME_DEEP_DIVE_MODEL=claude-sonnet-5``); unset → the default
below. The value is resolved at module import, so the env must be set
before the agent modules import (true for the CLI's ``load_env()`` at
startup and for the Modal container's secret/image env).

Cost note: every model the knob can point at MUST have a row in
``agents/_support/pricing.py`` (``cost_for_usage`` raises ``KeyError`` on
an unknown model — a deliberate loud failure rather than silently-zero
cost). Sampling-param note: the Claude 5 family rejects ``temperature`` /
``top_p`` / ``top_k`` (HTTP 400) — ``messages_create_with_backoff``
guards the cohort-temperature injection via
:func:`model_rejects_sampling_params`.
"""

from __future__ import annotations

import os

DEFAULT_DEEP_DIVE_MODEL = "claude-sonnet-4-6"

_ENV_VAR = "SURFACEOME_DEEP_DIVE_MODEL"


def deep_dive_model() -> str:
    """The agent model id for the v2 deep-dive — env-overridable.

    Returns ``$SURFACEOME_DEEP_DIVE_MODEL`` when set (and non-blank),
    else :data:`DEFAULT_DEEP_DIVE_MODEL`.
    """
    return (os.environ.get(_ENV_VAR) or "").strip() or DEFAULT_DEEP_DIVE_MODEL


def model_rejects_sampling_params(model: str | None) -> bool:
    """True iff ``model`` rejects ``temperature`` / ``top_p`` / ``top_k``.

    The Claude 5 family (``claude-{sonnet,opus,haiku,fable,mythos}-5...``)
    removed the sampling parameters — passing any returns HTTP 400
    (``"`temperature` is deprecated for this model."``). Opus 4.7/4.8 did
    too. Sonnet 4.6 and earlier still accept them, so the cohort sweep's
    ``temperature=0.2`` default stays valid there. Verified empirically
    against ``claude-sonnet-5`` (2026-06-30).
    """
    if not model:
        return False
    m = model.lower()
    if any(
        m.startswith(f"claude-{family}-5")
        for family in ("sonnet", "opus", "haiku", "fable", "mythos")
    ):
        return True
    return m.startswith(("claude-opus-4-7", "claude-opus-4-8"))
