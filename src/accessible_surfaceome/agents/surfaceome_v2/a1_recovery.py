"""A1 evidence-ledger recovery — reclaim mis-routed direct-surface methods.

The A1/A2 selector prompts route a *surface-method observation* to the A2
(biological-context) ledger whenever the clip is framed around a tissue /
cell-type / disease context (see ``plan_trim_select/prompts/a2_select_system.md``:
"Functional engagement on a named tissue / cell type / disease context is
ALWAYS ``tissue_expression``"). For genes whose surface literature is
dominated by disease-context papers (ICAM1 — the inducible inflammatory
adhesion molecule), that empties the A1 ledger, so the *deterministic*
``evidence_grade`` — scored over A1 only — defaults to ``weak`` and
``has_live_cell_surface_evidence`` defaults to ``False``, even though the
record cites non-permeabilized flow cytometry and surface proteomics.

This module reclaims those clips **without re-running plan-trim-select**
(the expensive, paper-body-reading stage). It re-tags the qualifying A2
claims into A1 on a cached intermediates blob, reconstructs the dual, and
replays the builders + synthesizer (~$0.7/gene) so the ``methods_builder``
re-reads the verbatim quotes *as A1 methods* and the grade recomputes from
a genuinely populated A1 ledger.

A claim counts as direct-surface evidence when it is a **surface-localization
assay** (flow cytometry, immunofluorescence, surface biotinylation, cell-
surface MS, proximity labeling), ``direction='supports'``, ``evidence_tier=
'primary'``, and **not explicitly permeabilized**. Only ``permeabilized=True``
is excluded — a permeabilized assay reaches intracellular epitopes and measures
total protein, not surface; ``permeabilized`` of ``None`` or ``False`` is
credited. This matches the deep-dive **grader's own breadth** (it credits
``permeabilized=None`` observations), rather than imposing a stricter
``permeabilized=False`` floor — the pre-filter only decides which clips to
*move*; the final grade is decided by the ``methods_builder`` +
``evidence_grade`` builder during the replay.

It also mirrors the grader's **species rule**: an assay whose only species is
non-human cannot anchor a human ``direct_*`` grade (the ``evidence_grade``
builder caps such genes at ``supportive_but_indirect``), so a non-human claim
does not count as recoverable direct-surface evidence. This matters for the
CD79A-class — genes whose one A1 direct method is non-human (e.g. an avian
flow read) while human surface-flow evidence sits misfiled in A2; without the
species check the scan would see A1 as "populated" and skip a recoverable gene.
``species`` of ``None`` / ``unspecified`` is treated as human (a human-gene
deep-dive defaults to human); only an explicit non-human species is excluded.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Literal

from accessible_surfaceome.agents.plan_trim_select.runner import (
    DualPlanTrimSelectResult,
    EvidenceClaim,
    PlanTrimSelectResult,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.tools.gene_lookup import IdentifierBundle

# Surface-localization assays the deep-dive grader credits as direct surface
# evidence. Kept to the assays that measure PM localization/accessibility;
# permeabilization is handled in ``claim_is_direct_surface`` (only an explicit
# ``permeabilized=True`` is excluded).
_SURFACE_LOCALIZATION_ASSAYS = frozenset(
    {
        "flow_cytometry",
        "immunofluorescence",
        "surface_biotinylation",
        "mass_spec_surfaceome",
        "proximity_labeling",
    }
)

# Species values that anchor a human ``direct_*`` grade. Mirrors the
# evidence_grade builder's rule: an assay whose only species is non-human
# (mouse/chicken/rat/…) cannot anchor a direct call for the human protein, so
# it does not count as recoverable direct-surface evidence. Unspecified/None
# gets the benefit of the doubt (a human-gene deep-dive defaults to human).
_HUMAN_ANCHORED_SPECIES = frozenset(
    {"human", "homo sapiens", "homo_sapiens", "hsapiens", "unspecified", ""}
)


def _is_human_anchored(species: Any) -> bool:
    """True unless the claim carries an *explicit* non-human species."""
    if not species:
        return True
    return str(species).strip().lower() in _HUMAN_ANCHORED_SPECIES


def ensure_d1_env() -> None:
    """Populate ``CLOUDFLARE_D1_SURFACEOME_{AGENTS,PUBLIC}_ID`` from the D1
    REST API when absent.

    The shared ``.env`` carries the Cloudflare account + token but not the
    per-database UUIDs that :meth:`D1Config.from_env` requires. Rather than
    forcing every caller (local CLI, Modal worker) to hard-code them, resolve
    the UUIDs once from the account's D1 database list. No-op when both vars
    are already set (e.g. injected via the Modal ``surfaceome-env`` secret).
    """
    need = [
        v
        for v in ("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID")
        if not os.environ.get(v, "").strip()
    ]
    if not need:
        return
    import httpx

    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    tok = os.environ["CLOUDFLARE_API_TOKEN"]
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/d1/database",
            headers={"Authorization": f"Bearer {tok}"},
        )
        resp.raise_for_status()
        dbs = {d["name"]: d["uuid"] for d in resp.json()["result"]}
    if dbs.get("surfaceome_agents"):
        os.environ.setdefault("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", dbs["surfaceome_agents"])
    if dbs.get("surfaceome_public"):
        os.environ.setdefault("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", dbs["surfaceome_public"])


def claim_is_direct_surface(claim: dict[str, Any]) -> bool:
    """True iff a cached PTS claim is a direct surface-localization assay.

    Applies the grader-matching rule documented in the module docstring
    (surface-localization assay + supports + primary + not explicitly
    permeabilized + human-anchored species). Operates on the raw claim dict
    (as persisted in the intermediates blob), so it is usable both for the D1
    scan and for the re-tag on a loaded blob.
    """
    if claim.get("direction") != "supports" or claim.get("evidence_tier") != "primary":
        return False
    if claim.get("evidence_type") not in _SURFACE_LOCALIZATION_ASSAYS:
        return False
    ac = claim.get("assay_context") or {}
    # Exclude only an explicit permeabilized=True (total protein, not surface);
    # None/False are credited (bool True or the SQLite/int 1 both count as True).
    if ac.get("permeabilized") in (True, 1):
        return False
    # Species rule: a non-human-anchored assay can't lift the human grade
    # (CD79A-class — its only A1 direct method is a chicken flow), so it isn't
    # recoverable direct-surface evidence.
    return _is_human_anchored(ac.get("species"))


def retag_a2_direct_into_a1(blob: dict[str, Any]) -> dict[str, Any]:
    """Move qualifying A2 direct-surface claims into A1, in place.

    Renumbers the moved claims into the ``a1_evi_`` id namespace (the A1
    ledger validator rejects ``a2_evi_`` ids) and flips their ``claim_type``
    to ``surface_expression`` (they were mis-tagged ``tissue_expression`` at
    selection). Returns a summary; ``n_moved == 0`` means nothing to recover.
    """
    pts = blob["plan_trim_select"]
    a1_claims = list(pts.get("a1", {}).get("claims") or [])
    a2_claims = list(pts.get("a2", {}).get("claims") or [])
    move = [c for c in a2_claims if claim_is_direct_surface(c)]
    keep = [c for c in a2_claims if not claim_is_direct_surface(c)]
    for i, c in enumerate(move, start=len(a1_claims) + 1):
        c["claim_type"] = "surface_expression"
        c["evidence_id"] = f"a1_evi_{i:02d}"
    pts["a1"]["claims"] = a1_claims + move
    pts["a2"]["claims"] = keep
    return {
        "n_moved": len(move),
        "method_types": dict(Counter(c.get("evidence_type") for c in move)),
        "a1_before": len(a1_claims),
        "a1_after": len(a1_claims) + len(move),
    }


def reconstruct_dual_from_blob(blob: dict[str, Any]) -> DualPlanTrimSelectResult:
    """Rebuild a :class:`DualPlanTrimSelectResult` from an intermediates blob.

    The orchestrator's replay path reads only ``dual.bundle`` + each side's
    ``.claims`` — ``plan`` / ``selection_response`` are unused, so they are
    stubbed ``None``. Cost/usage default to zero (a replay pays no
    plan-trim-select cost). This is the single source of truth for the
    reconstruction; ``scripts/surfaceome_v2_replay_builders.py`` imports it.
    """
    pts = blob.get("plan_trim_select", {})
    bundle_dict = blob.get("bundle")
    if not bundle_dict:
        raise ValueError(
            "intermediates blob has no 'bundle' — too old for a builders replay "
            "(bundle persistence landed in v2.34). Re-annotate once to refresh."
        )
    bundle = IdentifierBundle.model_validate(bundle_dict)
    gene = blob.get("gene") or bundle.hgnc_symbol or "<unknown>"

    def _side(side_blob: dict[str, Any], focus: Literal["a1", "a2"]) -> PlanTrimSelectResult:
        claims = [EvidenceClaim.model_validate(c) for c in side_blob.get("claims") or []]
        return PlanTrimSelectResult(
            gene=gene,
            bundle=bundle,
            plan=None,
            selection_response=None,
            agent_focus=focus,
            claims=claims,
            n_claims=len(claims),
            n_anchored=side_blob.get("n_anchored") or len(claims),
            n_papers_total=side_blob.get("n_papers_total") or 0,
            n_drafts_total=side_blob.get("n_drafts_total") or 0,
            n_kept_after_trim=side_blob.get("n_kept_after_trim") or 0,
            n_iterations_run=side_blob.get("n_iterations_run") or 0,
        )

    return DualPlanTrimSelectResult(
        gene=gene,
        bundle=bundle,
        a1=_side(pts.get("a1") or {}, "a1"),
        a2=_side(pts.get("a2") or {}, "a2"),
        elapsed_s=0.0,
    )


def load_latest_intermediates(gene: str, at: str | None = None) -> dict[str, Any]:
    """Load a gene's most-recent (or ``at``-prefixed) intermediates blob."""
    ensure_d1_env()
    with D1Client(D1Config.from_env()) as d1:
        if at:
            rows = d1.query(
                "SELECT intermediates_json FROM agent_run_intermediates "
                "WHERE gene_symbol = ? AND created_at LIKE ? "
                "ORDER BY created_at DESC LIMIT 1",
                [gene, at + "%"],
            )
        else:
            rows = d1.query(
                "SELECT intermediates_json FROM agent_run_intermediates "
                "WHERE gene_symbol = ? ORDER BY created_at DESC LIMIT 1",
                [gene],
            )
    if not rows:
        raise LookupError(f"no intermediates row for {gene}")
    return json.loads(rows[0]["intermediates_json"])


def recover_one(
    gene: str,
    *,
    publish: bool = False,
    at: str | None = None,
    cohort_run_id: str | None = "a1_recovery",
) -> dict[str, Any]:
    """Re-tag + builders/synth replay for one gene.

    Loads the cached dual, moves qualifying A2 direct-surface claims into A1,
    and replays the builders + synthesizer. When ``publish`` is True the
    corrected record is pushed to **public D1** via
    :func:`cloud.surface_annotation.publish_record` (the same path
    ``surfaceome_v2_annotate.py --publish`` uses — D1 write + edge-cache purge),
    NOT ``annotate``'s ``persist`` (which only writes an ephemeral local disk
    artifact). Otherwise the record is computed and discarded (the return value
    carries the before/after grade for review).

    Import of the heavy orchestrator is deferred so the pure-logic helpers
    above (used by the D1 scan / tests) don't drag it in.
    """
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import annotate
    from accessible_surfaceome.cloud.surface_annotation import publish_record

    blob = load_latest_intermediates(gene, at)
    retag = retag_a2_direct_into_a1(blob)
    if retag["n_moved"] == 0:
        return {"gene": gene, "status": "skip", "reason": "no A2 direct-surface claims"}
    dual = reconstruct_dual_from_blob(blob)
    # persist=False: annotate's own persist writes only a local disk artifact
    # (lost when a Modal container exits). The real public-D1 publish is the
    # publish_record call below.
    result = annotate(gene, cached_dual=dual, persist=False)
    if result.record is None:
        return {
            "gene": gene,
            "status": "failed",
            "error": str(result.error),
            "n_moved": retag["n_moved"],
        }
    rec = result.record
    out: dict[str, Any] = {
        "gene": gene,
        "status": "ok",
        "n_moved": retag["n_moved"],
        "method_types": retag["method_types"],
        "evidence_grade": rec.surface_evidence.evidence_grade,
        "has_live_cell_surface_evidence": rec.filters.has_live_cell_surface_evidence,
        "surface_accessibility": rec.executive_summary.surface_accessibility,
        "confidence": rec.confidence,
        "n_methods": len(rec.surface_evidence.methods),
        "cost_usd": round(result.total_cost_usd, 4),
        "published": False,
    }
    if publish:
        pub = publish_record(rec, push_to_d1=True, cohort_run_id=cohort_run_id)
        out["published"] = bool(pub.d1_written)
        out["publish_skipped_reason"] = pub.skipped_reason
        out["cache_purged"] = pub.cache_purged
    return out
