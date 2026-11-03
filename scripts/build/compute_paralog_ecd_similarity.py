"""Compute + persist ECD percent-similarity for close (>=80%) paralog pairs.

`compara_paralog` already carries `ecd_pct_identity` (per-loop BLOSUM62
length-weighted identity). This adds the companion `ecd_pct_similarity`
(identity + BLOSUM62-positive substitutions) for the *close* paralog pairs
— those with full-length identity >= 80% — using the sequences + topology
the genome DeepTMHMM sweep already landed in `topology_public`. Mirrors how
the ortholog table carries both ECD identity and ECD similarity.

Scope: pairs with `biomart_percent_identity >= THRESHOLD` (default 80).
ECD similarity is NULL for pairs where either protein has no extracellular
('O') residues — same semantics as `ecd_pct_identity`.

Usage:
    uv run python scripts/build/compute_paralog_ecd_similarity.py            # dry-run
    uv run python scripts/build/compute_paralog_ecd_similarity.py --execute  # write D1
"""
from __future__ import annotations

import argparse
import logging
import sys

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_topology_version_for_cohort,
    _query_public,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

logger = logging.getLogger(__name__)
PV = "paralog_topo_2026_05_16"


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=80.0,
                    help="full-length identity floor for 'close' paralogs (default 80)")
    ap.add_argument("--execute", action="store_true",
                    help="write ecd_pct_similarity to public D1 (default: dry-run)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    tv = _latest_topology_version_for_cohort("human_canonical")
    logger.info("topology_version=%s threshold=%.0f%% execute=%s", tv, args.threshold, args.execute)

    rows = _query_public(
        "SELECT human_ensembl_gene heg, paralog_ensembl_gene peg, "
        "human_uniprot_acc h, paralog_uniprot_acc p, biomart_percent_identity fl "
        "FROM compara_paralog WHERE paralog_version=? AND biomart_percent_identity>=?",
        [PV, args.threshold],
    )
    logger.info("close pairs (>=%.0f%%): %d", args.threshold, len(rows))

    accs = sorted({a for r in rows for a in (r["h"], r["p"]) if a})
    topo: dict[str, tuple[str, str]] = {}
    for chunk in _chunks(accs, 50):
        ph = ",".join("?" * len(chunk))
        for tr in _query_public(
            f"SELECT uniprot_acc a, sequence s, per_residue_topology t FROM topology_public "
            f"WHERE cohort='human_canonical' AND topology_version=? AND uniprot_acc IN ({ph})",
            [tv, *chunk],
        ):
            if tr.get("s") and tr.get("t"):
                topo[tr["a"]] = (tr["s"], tr["t"])
    logger.info("topology+sequence available for %d/%d accessions", len(topo), len(accs))

    if args.execute:
        try:
            _query_public("ALTER TABLE compara_paralog ADD COLUMN ecd_pct_similarity REAL", [])
            logger.info("added column ecd_pct_similarity")
        except Exception as exc:  # noqa: BLE001 — column may already exist
            logger.info("ALTER skipped (%s)", str(exc).split(":")[-1].strip()[:60])

    computed = wrote = skipped_noseq = none_ecd = 0
    for r in rows:
        h, p = r["h"], r["p"]
        if h not in topo or p not in topo:
            skipped_noseq += 1
            continue
        hs, ht = topo[h]
        ps, pt = topo[p]
        sim = compute_ecd_identity(
            human_topology=ht, human_sequence=hs,
            paralog_topology=pt, paralog_sequence=ps,
        ).ecd_pct_similarity
        computed += 1
        if sim is None:
            none_ecd += 1
        if args.execute:
            _query_public(
                "UPDATE compara_paralog SET ecd_pct_similarity=? "
                "WHERE paralog_version=? AND human_ensembl_gene=? AND paralog_ensembl_gene=?",
                [sim, PV, r["heg"], r["peg"]],
            )
            wrote += 1

    logger.info(
        "computed=%d (ECD-similarity NULL for %d ECD-less pairs) | skipped_no_seq=%d | wrote=%d",
        computed, none_ecd, skipped_noseq, wrote,
    )
    # Show a few examples
    shown = 0
    for r in rows:
        if shown >= 8:
            break
        h, p = r["h"], r["p"]
        if h in topo and p in topo:
            sim = compute_ecd_identity(
                human_topology=topo[h][1], human_sequence=topo[h][0],
                paralog_topology=topo[p][1], paralog_sequence=topo[p][0],
            )
            si = f"{sim.ecd_pct_similarity:.1f}" if sim.ecd_pct_similarity is not None else "—"
            ii = f"{sim.ecd_pct_identity:.1f}" if sim.ecd_pct_identity is not None else "—"
            logger.info("  %s->%s  full=%.1f  ECD id=%s  ECD sim=%s", h, p, r["fl"], ii, si)
            shown += 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
