"""Recompute ECD identity for compara_ortholog_ecd rows where the algorithm
now produces a value but the stored value is NULL.

Background: a small number of NULL-ECD rows in ``compara_ortholog_ecd`` are
stale — both the human and the ortholog topology rows are present in
``topology_public`` and ``compute_ecd_identity()`` runs cleanly today, but
the row stored at sweep time still has NULL. Rather than re-run the whole
topology sweep, this script re-computes the per-loop identity in-process and
UPDATE-s only the affected rows. Idempotent.

Today's only known stale cases are PTPRZ1 mouse + cyno (the protein has 1
huge extracellular loop on both sides; the algorithm produces 76.5% / 97.0%).
Other NULL-ECD leakers either have a fragment ortholog UniProt picked by the
old resolver (fixed for future sweeps in deeptmhmm.py.resolve_uniprot_by_ensembl_gene;
existing data needs a DeepTMHMM re-run to backfill, tracked separately) or
are genuine DeepTMHMM mis-classifications (real upstream noise).

Usage::

    uv run python scripts/recompute_stale_ecd_rows.py --dry-run
    uv run python scripts/recompute_stale_ecd_rows.py --execute
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import httpx

from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

logger = logging.getLogger(__name__)
API_ROOT = "https://api.cloudflare.com/client/v4"


def _query(client: httpx.Client, account_id: str, db_id: str, sql: str,
           params: list | None = None) -> list[dict]:
    r = client.post(
        f"{API_ROOT}/accounts/{account_id}/d1/database/{db_id}/query",
        json={"sql": sql, "params": params or []},
        timeout=120,
    )
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"D1 query failed: {payload}")
    return payload["result"][0]["results"]


def _scan_and_update(client: httpx.Client, account_id: str, db_id: str,
                     *, label: str, topology_version: str,
                     ortholog_ecd_version: str, dry_run: bool) -> None:
    rows = _query(client, account_id, db_id,
        "SELECT eo.human_hgnc_id, eo.species, eo.human_uniprot_acc, eo.ortholog_uniprot_acc, "
        "  tp_h.per_residue_topology AS h_topo, tp_h.sequence AS h_seq, "
        "  tp_o.per_residue_topology AS o_topo, tp_o.sequence AS o_seq, "
        "  eo.human_gene_symbol "
        "FROM compara_ortholog_ecd eo "
        "JOIN topology_public tp_h ON tp_h.uniprot_acc=eo.human_uniprot_acc "
        "  AND tp_h.cohort='human_canonical' AND tp_h.topology_version=? "
        "JOIN topology_public tp_o ON tp_o.uniprot_acc=eo.ortholog_uniprot_acc "
        "  AND tp_o.topology_version=? "
        "  AND ((eo.species='mouse' AND tp_o.cohort='mouse_ortholog') "
        "       OR (eo.species='cynomolgus' AND tp_o.cohort='cyno_ortholog')) "
        "WHERE eo.ecd_pct_identity IS NULL "
        "  AND eo.ortholog_ecd_version=? "
        "  AND tp_h.ecd_length_residues > 0 ",
        [topology_version, topology_version, ortholog_ecd_version])

    logger.info("[%s] %d NULL-ECD candidates have both topologies present", label, len(rows))

    updates: list[tuple[str, float, int]] = []  # (gene_symbol_for_log, ecd_pct, n_loops)
    update_params: list[list] = []
    for r in rows:
        res = compute_ecd_identity(
            human_topology=r["h_topo"], human_sequence=r["h_seq"],
            paralog_topology=r["o_topo"], paralog_sequence=r["o_seq"],
        )
        if res.ecd_pct_identity is None:
            continue
        updates.append((r["human_gene_symbol"] or "?", res.ecd_pct_identity, res.n_ecd_loops_compared))
        update_params.append([
            res.ecd_pct_identity, res.n_ecd_loops_compared,
            ortholog_ecd_version, r["human_hgnc_id"], r["species"], r["ortholog_uniprot_acc"],
        ])

    logger.info("[%s] %d / %d would update:", label, len(updates), len(rows))
    for sym, pct, n in updates:
        logger.info("  %-12s ecd=%.2f%% n_loops=%d", sym, pct, n)

    if dry_run or not updates:
        return

    for p in update_params:
        _query(client, account_id, db_id,
               "UPDATE compara_ortholog_ecd SET ecd_pct_identity=?, n_ecd_loops_compared=? "
               "WHERE ortholog_ecd_version=? AND human_hgnc_id=? AND species=? AND ortholog_uniprot_acc=?",
               p)
    logger.info("[%s] wrote %d updates", label, len(update_params))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-version", default="topo_2026_05_16")
    parser.add_argument("--ortholog-ecd-version", default="orthologecd_topo_2026_05_16")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true")
    grp.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"].strip()
    token = os.environ["CLOUDFLARE_API_TOKEN"].strip()
    public_id = os.environ["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"].strip()
    private_id = os.environ["CLOUDFLARE_D1_SURFACEOME_AGENTS_ID"].strip()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(headers=headers) as client:
        _scan_and_update(client, account_id, private_id, label="private",
                         topology_version=args.topology_version,
                         ortholog_ecd_version=args.ortholog_ecd_version,
                         dry_run=args.dry_run)
        _scan_and_update(client, account_id, public_id, label="public",
                         topology_version=args.topology_version,
                         ortholog_ecd_version=args.ortholog_ecd_version,
                         dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
