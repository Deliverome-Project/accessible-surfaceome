"""Symmetric triage ↔ accessibility-class disagreement gate.

The synthesizer prompt promises that ANY cross-agent disagreement (triage
verdict vs deep-dive ``surface_accessibility`` class) must be justified in a
non-empty ``confidence_reasoning``. The validator historically gated only the
single ``unlikely``↔``high`` pair; it now gates every opposing pair:

    triage ``unlikely``          ↔ deep-dive ``high`` / ``moderate``
    triage ``likely_accessible`` ↔ deep-dive ``no`` / ``low``

Neutral / uncertain pairings (``possibly_accessible``, ``unknown``,
``uncertain``) and same-direction pairs do NOT require reasoning.

Two layers of coverage:
  * the standalone ``_validate_triage_signal_consistency`` helper (the single
    source of truth both ``SurfaceomeRecord`` and ``SurfaceomeRecordDraft``
    delegate to); and
  * the integrated ``SurfaceomeRecord.model_validate`` path, exercised against
    a committed snapshot so we hit the real ``@model_validator``.
"""

from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import pytest

from accessible_surfaceome.tools._shared.models import (
    SurfaceomeRecord,
    _validate_triage_signal_consistency,
)

_REASON = "Deep-dive web search overturned the no-web-search triage call."

# (triage_signal, surface_accessibility) pairs that POINT IN OPPOSITE
# DIRECTIONS — empty reasoning must raise, non-empty must pass.
_OPPOSING = [
    ("unlikely", "high"),
    ("unlikely", "moderate"),
    ("likely_accessible", "no"),
    ("likely_accessible", "low"),
]

# Pairs that agree or are neutral/uncertain — empty reasoning is fine.
_NON_OPPOSING = [
    ("unlikely", "no"),  # both lean against accessibility
    ("unlikely", "low"),  # same direction
    ("unlikely", "uncertain"),  # deep-dive no-signal
    ("likely_accessible", "high"),  # both lean accessible
    ("likely_accessible", "moderate"),  # same direction
    ("likely_accessible", "uncertain"),  # deep-dive no-signal
    ("possibly_accessible", "high"),  # weak triage signal — neutral
    ("possibly_accessible", "no"),  # weak triage signal — neutral
    ("unknown", "high"),  # no triage signal
    ("unknown", "no"),  # no triage signal
]


# --------------------------------------------------------------------------
# Standalone helper (the validator's logic)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("triage", "accessibility"), _OPPOSING)
def test_opposing_pair_requires_reasoning(triage: str, accessibility: str):
    with pytest.raises(ValueError, match="conflicts with"):
        _validate_triage_signal_consistency(triage, accessibility, "")
    # whitespace-only is still "empty"
    with pytest.raises(ValueError, match="conflicts with"):
        _validate_triage_signal_consistency(triage, accessibility, "   ")


@pytest.mark.parametrize(("triage", "accessibility"), _OPPOSING)
def test_opposing_pair_passes_with_reasoning(triage: str, accessibility: str):
    # Non-empty reasoning satisfies the gate — no raise.
    _validate_triage_signal_consistency(triage, accessibility, _REASON)


@pytest.mark.parametrize(("triage", "accessibility"), _NON_OPPOSING)
def test_non_opposing_pair_does_not_require_reasoning(triage: str, accessibility: str):
    # Agreeing / neutral pairs validate with empty reasoning — no over-firing.
    _validate_triage_signal_consistency(triage, accessibility, "")


# --------------------------------------------------------------------------
# Integrated path through SurfaceomeRecord.model_validate
# --------------------------------------------------------------------------

_SNAPSHOT = (
    # A dedicated committed fixture — the pre-removal KLK2 deep-dive record.
    # Kept HERE, not under viewer/public/data/surfaceome/, so it isn't subject
    # to test_committed_snapshots_have_live_d1_records (KLK2 has no live D1 row;
    # its viewer snapshot was removed as a stale orphan). Its field combination
    # (surface_call_reason='tissue_restricted_surface', state_dependence='high')
    # is what makes every triage×accessibility case below validate cleanly.
    Path(__file__).resolve().parent / "fixtures" / "klk2_record_snapshot.json"
)


def _base_record_dict() -> dict:
    """The committed KLK2 fixture record, which validates, used as a base.

    Set ``confidence='high'`` so the orthogonal ``_check_confidence_reasoning``
    rule (which requires reasoning when confidence is moderate/low) doesn't
    confound the triage-consistency assertions.
    """
    d = json.loads(_SNAPSHOT.read_text())
    d["confidence"] = "high"
    return d


def _validate(d: dict) -> SurfaceomeRecord:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # soft prose-length overshoot warnings
        return SurfaceomeRecord.model_validate(d)


# The KLK2 fixture's ``surface_call_reason`` is not in the NO-bucket, so
# integration cases avoid ``surface_accessibility='no'`` (which trips an
# orthogonal NO-bucket-reason validator). The standalone helper tests above
# cover the ``no`` / ``low`` opposing pairs exhaustively.
_OPPOSING_INTEGRATION = [
    ("unlikely", "high"),
    ("unlikely", "moderate"),
    ("likely_accessible", "low"),
]


def test_record_matching_pair_validates_with_empty_reasoning():
    d = _base_record_dict()
    d["triage_signal"] = "likely_accessible"
    d["executive_summary"]["surface_accessibility"] = "high"  # both lean accessible
    d["confidence_reasoning"] = ""
    rec = _validate(d)
    assert rec.confidence_reasoning == ""


@pytest.mark.parametrize(("triage", "accessibility"), _OPPOSING_INTEGRATION)
def test_record_opposing_pair_requires_reasoning(triage: str, accessibility: str):
    d = _base_record_dict()
    d["triage_signal"] = triage
    d["executive_summary"]["surface_accessibility"] = accessibility
    d["confidence_reasoning"] = ""
    with pytest.raises(ValueError, match="conflicts with"):
        _validate(d)
    # ... and passes once the disagreement is explained.
    ok = copy.deepcopy(d)
    ok["confidence_reasoning"] = _REASON
    rec = _validate(ok)
    assert rec.triage_signal == triage
    assert rec.executive_summary.surface_accessibility == accessibility


def test_record_neutral_pair_does_not_require_reasoning():
    d = _base_record_dict()
    d["triage_signal"] = "possibly_accessible"  # weak/neutral triage signal
    d["executive_summary"]["surface_accessibility"] = "high"
    d["confidence_reasoning"] = ""
    rec = _validate(d)
    assert rec.confidence_reasoning == ""
