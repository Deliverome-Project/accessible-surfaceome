"""Classify each v2 candidate gene's deterministic-feature coverage.

Pass 1 (this module) is presence-based: a feature with a D1 row is
``present``; a feature with no D1 row is ``needs-backfill``. Genuine
absence (a singleton with no paralogs, a single-isoform gene, a gene with
no one2one ortholog) is resolved in pass 2 *after* the backfill sweep —
whatever still has no row once the sweep has tried is reclassified
``genuinely-absent`` and stamped via the checked-none sentinel. ``canonical``
is never genuinely absent: every protein has a main sequence.

The scope these genes come from is the candidate-set union
(``in_db_union = 1`` OR triage yes/contextual), so the gene-level
``needs-backfill`` counts are upper bounds — most missing-isoform genes are
single-isoform and most no-row genes only need the sentinel, not a run.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeaturePresence:
    canonical: bool
    isoforms: bool
    paralogs: bool
    orthologs: bool


def _status(present: bool) -> str:
    return "present" if present else "needs-backfill"


def classify_gene(
    hgnc_symbol: str, uniprot_acc: str, p: FeaturePresence
) -> dict[str, str]:
    return {
        "hgnc_symbol": hgnc_symbol,
        "uniprot_acc": uniprot_acc,
        "canonical_topology_status": _status(p.canonical),
        "isoform_topology_status": _status(p.isoforms),
        "paralogs_status": _status(p.paralogs),
        "orthologs_status": _status(p.orthologs),
    }
