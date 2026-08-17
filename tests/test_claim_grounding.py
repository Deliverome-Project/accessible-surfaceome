"""Deterministic homonym-contamination drop.

Guards the serotransferrin (TF) / tissue factor (F3/CD142) fix: F3 claims are
dropped via the collider's distinguishing token (CD142), while (a) legit paralog
mentions that name the target (DSC1 vs DSC2) and (b) incidental mentions of
*non-colliding* genes (serotransferrin's receptor TFRC) are kept.
"""
from __future__ import annotations

from types import SimpleNamespace

from accessible_surfaceome.agents._support.claim_grounding import (
    partition_competing_claims,
)
from accessible_surfaceome.tools._shared.gene_gazetteer import build_target_names


def _claim(cid: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(evidence_id=cid, claim=text)


def test_drops_collider_keeps_target_and_noncolliding():
    # Target TF: 2-char symbol -> not groundable; F3 collider distinguishing
    # token is CD142.
    target_names = build_target_names("TF")  # frozenset() — TF too short
    competitors = frozenset({"CD142"})
    claims = [
        _claim("f3", "Tissue factor (TF/F3/CD142) on tumor cells by live-cell flow cytometry."),
        _claim("tfrc", "Serotransferrin binds the transferrin receptor TFRC at the cell surface."),
        _claim("sec", "Serotransferrin circulates as a soluble iron-binding plasma glycoprotein."),
    ]
    kept, dropped = partition_competing_claims(
        claims, target_names=target_names, competitor_tokens=competitors
    )
    assert [c.evidence_id for c in dropped] == ["f3"]          # collider token -> drop
    assert [c.evidence_id for c in kept] == ["tfrc", "sec"]    # TFRC (non-collider) + anaphoric kept


def test_keeps_paralog_mention_that_names_target():
    # DSC1 names itself; DSC2 is a collider token but the target IS named -> keep.
    target_names = build_target_names("DSC1")  # {"DSC1"}
    competitors = frozenset({"DSC2", "DSC3"})
    claims = [
        _claim("e1", "DSC1 is restricted to suprabasal epidermis, unlike DSC2 in basal layers."),
        _claim("e2", "DSC2 and DSC3 are the dominant desmocollins in simple epithelia."),
    ]
    kept, dropped = partition_competing_claims(
        claims, target_names=target_names, competitor_tokens=competitors
    )
    assert [c.evidence_id for c in kept] == ["e1"]      # names DSC1 -> kept
    assert [c.evidence_id for c in dropped] == ["e2"]   # only names colliders -> dropped


def test_no_competitors_is_noop():
    claims = [_claim("e1", "CD142 tissue factor at the cell surface.")]
    kept, dropped = partition_competing_claims(
        claims, target_names=build_target_names("TF"), competitor_tokens=frozenset()
    )
    assert dropped == [] and len(kept) == 1
