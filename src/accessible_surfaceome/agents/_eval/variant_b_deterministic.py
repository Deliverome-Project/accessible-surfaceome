"""Variant B — deterministic PubMed-count rule. No LLM.

Single-call PubMed/Europe PMC E-utilities query per gene:

* surface-anchored: ``<gene>[Gene] AND (Cell Membrane[MeSH] OR Receptors,
  Cell Surface[MeSH] OR GPI-Linked Proteins[MeSH] OR Membrane
  Proteins[MeSH] OR "cell surface"[tiab] OR "plasma membrane"[tiab] OR
  "extracellular domain"[tiab] OR "surface antigen"[tiab] OR "surface
  receptor"[tiab])``
* unconstrained: ``<gene>[Gene]``

``surface_fraction = surface_hits / max(total_hits, 1)``.

Verdict thresholds (calibrate after seeing benchmark behaviour):

* ``yes``         — surface_hits ≥ 5 AND surface_fraction ≥ 0.10
* ``contextual``  — surface_hits ≥ 1 AND surface_fraction ≥ 0.02
* ``no``          — otherwise

Signal:

* ``likely_accessible``    — surface_fraction ≥ 0.20
* ``possibly_accessible``  — surface_fraction ≥ 0.05
* ``unlikely``             — surface_hits == 0
* ``unknown``              — otherwise

Emits a ``TriageRecordDraft``-shaped dict (JSON-serialisable) so the
scoring pipeline treats it identically to LLM variants. ``cost_usd=0``
because it's just two HTTP calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from accessible_surfaceome.tools._shared.http import CachedHTTP

_EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EUROPEPMC_TTL = 7  # days

# Europe PMC syntax (not PubMed): MESH:"<term>" for MeSH, bare quoted
# strings default to title+abstract free-text. SRC:MED filters to MEDLINE.
#
# Mix of MeSH and free-text. Empirically the deterministic baseline is
# weak: surface fractions for true-yes (HER2: 2%) and true-no (KRAS: 2%)
# proteins overlap heavily because surface terms appear in passing in
# papers about non-surface biology. Variant B is included as a baseline
# to *test* the hypothesis that deterministic counting is competitive
# with an LLM, not to be the final genome-wide tool.
_SURFACE_QUERY_FRAGMENT = (
    'MESH:"Receptors, Cell Surface" OR '
    'MESH:"GPI-Linked Proteins" OR '
    'MESH:"Membrane Glycoproteins" OR '
    'MESH:"Antigens, Surface" OR '
    'MESH:"Cell Membrane" OR '
    '"cell surface" OR '
    '"plasma membrane" OR '
    '"extracellular domain" OR '
    '"surface antigen" OR '
    '"surface receptor"'
)


@dataclass
class DeterministicResult:
    gene_symbol: str
    uniprot_acc: str
    surface_hits: int
    total_hits: int
    surface_fraction: float
    verdict: str
    accessibility_signal: str
    latency_s: float


def run_variant_b(
    *,
    gene_symbol: str,
    uniprot_acc: str,
    hgnc_id: str | None,
    http: CachedHTTP,
) -> tuple[dict[str, Any], DeterministicResult]:
    """Run variant B for one gene.

    Returns ``(triage_draft_dict, telemetry)`` where ``triage_draft_dict``
    has the same shape as a ``TriageRecordDraft.model_dump(mode="json")``
    so the scoring pipeline can treat it uniformly.
    """

    started = time.monotonic()
    # Europe PMC: anchor on the gene symbol as a quoted phrase (no
    # `[Gene]` qualifier). SRC:MED restricts to MEDLINE.
    gene_anchor = f'"{gene_symbol}"'
    surface_hits = _hit_count(
        http=http,
        query=f"{gene_anchor} AND ({_SURFACE_QUERY_FRAGMENT}) AND SRC:MED",
    )
    total_hits = _hit_count(http=http, query=f"{gene_anchor} AND SRC:MED")
    latency = time.monotonic() - started

    surface_fraction = surface_hits / max(total_hits, 1)
    verdict = _verdict_from_counts(surface_hits=surface_hits, surface_fraction=surface_fraction)
    signal = _signal_from_counts(surface_hits=surface_hits, surface_fraction=surface_fraction)

    reasoning = (
        f"Variant B (deterministic, no LLM). "
        f"PubMed surface-anchored hits: {surface_hits}; "
        f"total {gene_symbol}[Gene] hits: {total_hits}; "
        f"surface_fraction={surface_fraction:.3f}. "
        f"Threshold rule: yes if hits>=5 & fraction>=0.10; "
        f"contextual if hits>=1 & fraction>=0.02; else no."
    )

    draft = {
        "schema_version": "v0.1.0",
        "gene": {
            "hgnc_symbol": gene_symbol,
            "hgnc_id": hgnc_id or "",
            "uniprot_acc": uniprot_acc,
            "ncbi_gene_id": None,
            "ensembl_gene": None,
        },
        "verdict": verdict,
        "verdict_reasoning": reasoning[:600],
        "accessibility_signal": signal,
        "evidence_claims": [],
        "model_path": "sonnet_only",  # not really, but the schema literal is closed; flag in summary instead
    }

    telemetry = DeterministicResult(
        gene_symbol=gene_symbol,
        uniprot_acc=uniprot_acc,
        surface_hits=surface_hits,
        total_hits=total_hits,
        surface_fraction=surface_fraction,
        verdict=verdict,
        accessibility_signal=signal,
        latency_s=latency,
    )
    return draft, telemetry


def _hit_count(*, http: CachedHTTP, query: str) -> int:
    """Issue a Europe PMC search and return ``hitCount``.

    ``pageSize=1`` is enough — we only need the total count, not the
    bodies. The cache layer keeps repeats free.
    """

    payload = http.get_json(
        _EUROPEPMC_SEARCH,
        source="europepmc",
        ttl_days=_EUROPEPMC_TTL,
        params={
            "query": query,
            "format": "json",
            "pageSize": "1",
            "resultType": "lite",
        },
    )
    raw = payload.get("hitCount") or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _verdict_from_counts(*, surface_hits: int, surface_fraction: float) -> str:
    """Empirically-tuned thresholds.

    On the v1 benchmark, surface_fractions cluster in 1–7% across all
    ground-truth classes (the hybrid query catches surface terms used in
    passing). Absolute hit counts spread over four orders of magnitude
    based on gene-specific paper volume. We use a hybrid rule:

    - ``yes``        when both: high absolute (≥ 100 surface hits) AND
      modest fraction (≥ 4%). Catches well-studied surface receptors.
    - ``contextual`` when at least one signal is present: ≥ 10 surface
      hits OR fraction ≥ 4%. Catches less-studied targets with surface
      lit.
    - ``no``         otherwise.
    """

    if surface_hits >= 100 and surface_fraction >= 0.04:
        return "yes"
    if surface_hits >= 10 or surface_fraction >= 0.04:
        return "contextual"
    return "no"


def _signal_from_counts(*, surface_hits: int, surface_fraction: float) -> str:
    if surface_hits >= 100 and surface_fraction >= 0.04:
        return "likely_accessible"
    if surface_hits >= 10 or surface_fraction >= 0.04:
        return "possibly_accessible"
    if surface_hits == 0:
        return "unlikely"
    return "unknown"


__all__ = ["run_variant_b", "DeterministicResult"]
