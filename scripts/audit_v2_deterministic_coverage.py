"""Audit deterministic-feature coverage for the genome-wide v2 candidates.

Reads the candidate set produced by ``build_topology_candidate_set.py`` (the
authoritative union scope: candidate-universe ``in_db_union = 1`` OR v2 triage
``yes``/``contextual``), probes the deterministic-feature tables at their
CURRENT latest version, classifies each (gene × feature), and writes a manifest
TSV that sizes the backfill.

    # prerequisite (Task 7 Step 1): build the candidate set first
    uv run python scripts/build_topology_candidate_set.py \
        --topology-version topo_2026_05_16 \
        --triage-run-id genome_full_sonnet_ncbi_v2

    uv run python scripts/audit_v2_deterministic_coverage.py

Output: data/analysis/v2_deterministic_coverage/manifest.tsv

The per-feature ``needs-backfill`` counts are GENE-level upper bounds — most
missing-isoform genes are single-isoform and most no-row genes only need the
"checked, none" sentinel, not a sequence run. The real DeepTMHMM count is far
smaller; the sweep's UniProt isoform + BioMart ortholog resolution narrows the
gene set to the genes that actually have alts / one2one orthologs.
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_topology_version_for_cohort,
    _query_public,
)
from accessible_surfaceome.audit.v2_deterministic_coverage import (
    FeaturePresence,
    classify_gene,
)
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)
DEFAULT_CANDIDATE_SET = Path(
    "data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv"
)
OUT_DIR = Path("data/analysis/v2_deterministic_coverage")
PARALOG_VERSION = "paralog_topo_2026_05_16"
ORTHOLOG_ECD_VERSION = "orthologecd_topo_2026_05_16_idfix"


def _present(sql: str, params: list) -> set[str]:
    return {r["a"] for r in _query_public(sql, params) if r.get("a")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate-set", type=Path, default=DEFAULT_CANDIDATE_SET)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    if not args.candidate_set.exists():
        raise SystemExit(
            f"candidate set not found at {args.candidate_set} — run "
            "build_topology_candidate_set.py first (Task 7 Step 1)."
        )
    cands = list(csv.DictReader(args.candidate_set.open(), delimiter="\t"))
    cands = [c for c in cands if c.get("uniprot_acc")]
    accs = sorted({c["uniprot_acc"] for c in cands})
    logger.info("candidate-set scope: %d rows, %d distinct uniprot", len(cands), len(accs))

    canon_v = _latest_topology_version_for_cohort("human_canonical")
    iso_v = _latest_topology_version_for_cohort("human_isoforms")
    logger.info("versions: canonical=%s isoforms=%s paralog=%s ortholog_ecd=%s",
                canon_v, iso_v, PARALOG_VERSION, ORTHOLOG_ECD_VERSION)

    canon = _present(
        "SELECT DISTINCT uniprot_acc a FROM topology_public "
        "WHERE cohort='human_canonical' AND topology_version=?",
        [canon_v],
    )
    isos = _present(
        "SELECT DISTINCT uniprot_acc a FROM topology_public "
        "WHERE cohort='human_isoforms' AND topology_version=?",
        [iso_v],
    )
    paras = _present(
        "SELECT DISTINCT human_uniprot_acc a FROM compara_paralog "
        "WHERE paralog_version=?",
        [PARALOG_VERSION],
    )
    orthos = _present(
        "SELECT DISTINCT human_uniprot_acc a FROM compara_ortholog_ecd "
        "WHERE ortholog_ecd_version=?",
        [ORTHOLOG_ECD_VERSION],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "manifest.tsv"
    cols = [
        "hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene",
        "canonical_topology_status", "isoform_topology_status",
        "paralogs_status", "orthologs_status",
    ]
    status_cols = [c for c in cols if c.endswith("_status")]
    counts = {c: {"present": 0, "needs-backfill": 0} for c in status_cols}
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for c in cands:
            acc = c["uniprot_acc"]
            row = classify_gene(
                c.get("hgnc_symbol") or "", acc,
                FeaturePresence(
                    canonical=acc in canon,
                    isoforms=acc in isos,
                    paralogs=acc in paras,
                    orthologs=acc in orthos,
                ),
            )
            row["hgnc_id"] = c.get("hgnc_id") or ""
            row["ensembl_gene"] = c.get("ensembl_gene") or ""
            for k in status_cols:
                counts[k][row[k]] += 1
            w.writerow(row)

    logger.info("wrote %s (%d rows)", out, len(cands))
    for k in status_cols:
        v = counts[k]
        logger.info("  %-28s present=%-6d needs-backfill=%d", k, v["present"], v["needs-backfill"])
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
