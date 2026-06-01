"""Tests for the tolerant clip_id resolver in `_promote_selections`.

The selector reliably mangles one class of clip_id: the menu renders a
source header `PMID:21444918` above a clip `draft_21444918_abstract_02`
(bare digits — the pool keys PMID sources by number), and the model
re-inserts the prefix it saw in the header → `draft_PMID21444918_...`.
That mangled id isn't a pool key, so the selection was silently dropped
(observed: 8 dropped picks in one MS4A1 A2 run, ~30% of its ledger).

`_promote_selections` now recovers these via a normalized lookup that
strips PMID/PMC type tokens, accepting the match only when it is unique.
"""

from __future__ import annotations

from accessible_surfaceome.agents.plan_trim_select.runner import (
    _normalize_clip_id,
    _promote_selections,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    Selection,
    SelectionResponse,
)
from accessible_surfaceome.tools._shared.models import AssayContext, EvidenceClaimDraft


def _draft(clip_id: str, source_id: str, quote: str = "CD20 is at the cell surface") -> EvidenceClaimDraft:
    return EvidenceClaimDraft(
        suggested_evidence_id=clip_id,
        quote=quote,
        source_id=source_id,
        section="abstract",
        figure_or_table_id=None,
        context_excerpt=None,
        hallmark_phrase="abstract_preview",
        score=1.5,
    )


def _selection(clip_id: str) -> Selection:
    return Selection(
        clip_id=clip_id,
        claim="CD20 is presented at the B-cell surface.",
        claim_type="surface_expression",
        evidence_type="flow_cytometry",
        evidence_tier="secondary",
        direction="supports",
        confidence="moderate",
        assay_context=AssayContext(species="human"),
    )


def test_normalize_collapses_pmid_prefix_regularization() -> None:
    # The exact mangling observed in production.
    assert _normalize_clip_id("draft_PMID21444918_abstract_02") == _normalize_clip_id(
        "draft_21444918_abstract_02"
    )


def test_promote_recovers_pmid_prefix_mangled_id() -> None:
    pool = {"draft_21444918_abstract_02": _draft("draft_21444918_abstract_02", "PMID:21444918")}
    # Selector emits the prefix-regularized id that isn't a pool key.
    resp = SelectionResponse(selections=[_selection("draft_PMID21444918_abstract_02")])

    claims, warnings = _promote_selections(resp, pool=pool, evidence_id_prefix="a2_evi_")

    assert len(claims) == 1, warnings
    assert claims[0].source_id == "PMID:21444918"
    assert claims[0].quote == "CD20 is at the cell surface"  # verbatim from pool
    assert warnings == []


def test_exact_match_still_preferred() -> None:
    pool = {"draft_PMC8639842_results_01": _draft("draft_PMC8639842_results_01", "PMC:PMC8639842")}
    resp = SelectionResponse(selections=[_selection("draft_PMC8639842_results_01")])

    claims, warnings = _promote_selections(resp, pool=pool, evidence_id_prefix="a1_evi_")

    assert len(claims) == 1
    assert warnings == []


def test_ambiguous_normalized_match_is_not_recovered() -> None:
    # Two pool clips collapse to the SAME normalized key
    # (draft21444918abstract02) — recovery must refuse and keep the
    # drop + warning rather than guess between them.
    pool = {
        "draft_21444918_abstract_02": _draft("draft_21444918_abstract_02", "PMID:21444918"),
        "draft_PMID21444918_abstract_02": _draft(
            "draft_PMID21444918_abstract_02", "PMID:21444918", quote="other"
        ),
    }
    # Query misses both exactly but normalizes to the shared key.
    resp = SelectionResponse(selections=[_selection("draft_PMID_21444918_abstract_02")])
    claims, warnings = _promote_selections(resp, pool=pool, evidence_id_prefix="a2_evi_")

    assert claims == []
    assert len(warnings) == 1
    assert "2 normalized matches" in warnings[0]


def test_genuinely_unknown_clip_id_still_warns() -> None:
    pool = {"draft_PMC8639842_results_01": _draft("draft_PMC8639842_results_01", "PMC:PMC8639842")}
    resp = SelectionResponse(selections=[_selection("draft_99999999_abstract_01")])

    claims, warnings = _promote_selections(resp, pool=pool, evidence_id_prefix="a1_evi_")

    assert claims == []
    assert len(warnings) == 1
    assert "unknown clip_id" in warnings[0]
