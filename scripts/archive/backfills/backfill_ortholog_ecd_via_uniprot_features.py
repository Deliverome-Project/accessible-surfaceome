"""Backfill `compara_ortholog_ecd` NULL-ECD leakers via UniProt-curated topology.

Context: prior to PR #39's resolver fix, `resolve_uniprot_by_ensembl_gene` would
fall through to TrEMBL fragments when the reviewed-xref query missed (which is
common for mouse — UniProt frequently doesn't index Swiss-Prot's Ensembl xref).
The resolver picked stubby TrEMBL entries like `A0A0G2JGS5` (157 aa) for mouse
F3 instead of the canonical Swiss-Prot `P20352` (294 aa). Downstream:
`compara_ortholog_ecd.ortholog_uniprot_acc` points at a fragment, DeepTMHMM
labels the fragment GLOB, ECD identity is NULL.

PR #39 fixed the resolver. This script backfills the existing data using
**UniProt-curated topology features** (Signal, Transmembrane, Topological domain)
instead of re-running DeepTMHMM — which isn't installed in this worktree and
needs the DTU academic-license ZIP to set up. For Swiss-Prot entries the
curated features are *more* reliable than DeepTMHMM predictions; for TrEMBL
entries with TM annotations we infer extracellular vs cytoplasmic from the
SP/TM positions using the standard convention (SP present → mature chain starts
extracellular; no SP → starts cytoplasmic; flip orientation at each TM helix).

Steps:
  1. Query D1 for the NULL-ECD leakers (rows where human has predicted ECD
     residues but per-loop identity is NULL).
  2. For each, run the FIXED resolver (Tier 2 = reviewed gene_exact ahead of
     unreviewed xref; Tier 3 = longest unreviewed xref).
  3. If the new UniProt acc differs from the stored one:
       - Fetch UniProt JSON, derive per-residue topology.
       - INSERT OR REPLACE into `topology_public` (tool_version='uniprot_features_v1',
         topology_version=`topo_2026_05_16` so the agent picks it up).
       - UPDATE `compara_ortholog_ecd`: change ortholog_uniprot_acc + recompute
         ECD identity using the new ortholog topology.
  4. Apply to both private (surfaceome_agents) and public (surfaceome_public) D1.

Idempotent. Re-runnable. Doesn't touch rows where the new resolver agrees with
the stored acc (already correct).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime

import httpx

from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity
from accessible_surfaceome.sources.deeptmhmm import resolve_uniprot_by_ensembl_gene

logger = logging.getLogger(__name__)
API_ROOT = "https://api.cloudflare.com/client/v4"

UNIPROT_TOOL_VERSION = "uniprot_features_v1"


# ---------------------------------------------------------------------------
# UniProt-features → DeepTMHMM-style topology string
# ---------------------------------------------------------------------------


def _fetch_uniprot(acc: str, *, client: httpx.Client) -> dict | None:
    r = client.get(f"https://rest.uniprot.org/uniprotkb/{acc}?format=json", timeout=30)
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def derive_topology(uniprot_json: dict) -> dict | None:
    """Build a DeepTMHMM-style per-residue topology string from UniProt features.

    Alphabet: S = signal peptide, M = transmembrane / intramembrane, O = extracellular,
    I = cytoplasmic. Returns a dict with the topology + the summary stats expected
    by `topology_public`, or None when the entry has no sequence.
    """
    seq = (uniprot_json.get("sequence") or {}).get("value")
    if not seq:
        return None
    n = len(seq)

    sp_end = 0
    tm_spans: list[tuple[int, int]] = []  # 1-based inclusive
    topo_dom_spans: list[tuple[int, int, str]] = []  # (start, end, 'O' or 'I')
    for f in uniprot_json.get("features") or []:
        loc = f.get("location") or {}
        s = loc.get("start", {}).get("value")
        e = loc.get("end", {}).get("value")
        if not isinstance(s, int) or not isinstance(e, int):
            continue
        t = f.get("type", "")
        if t == "Signal":
            sp_end = max(sp_end, e)
        elif t in ("Transmembrane", "Intramembrane"):
            tm_spans.append((s, e))
        elif t == "Topological domain":
            desc = (f.get("description") or "").lower()
            kind = (
                "O" if ("extracellular" in desc or "lumen" in desc or "vesicular" in desc)
                else "I" if "cytoplasmic" in desc
                else None
            )
            if kind:
                topo_dom_spans.append((s, e, kind))

    # If the entry has zero topology hints AND no signal peptide, treat as GLOB
    # — but be defensive: if UniProt has only a Chain feature and nothing else,
    # the curator hasn't yet annotated topology, so we don't pretend it's
    # cytosolic. Return GLOB-ish only when the entry truly has nothing.
    has_any_topo = sp_end > 0 or tm_spans or topo_dom_spans
    has_sp = sp_end > 0

    topo = [""] * n
    # 1. Stamp signal peptide
    for i in range(sp_end):
        topo[i] = "S"
    # 2. Stamp TM helices
    for s, e in tm_spans:
        for i in range(s - 1, min(e, n)):
            topo[i] = "M"
    # 3. Stamp explicit topological_domain regions
    for s, e, kind in topo_dom_spans:
        for i in range(s - 1, min(e, n)):
            if topo[i] == "":
                topo[i] = kind
    # 4. Fill unannotated residues by inference from SP/TM crossings
    if has_any_topo:
        start_side = "O" if has_sp else "I"
        for i in range(n):
            if topo[i] != "":
                continue
            n_tm_before = sum(1 for s, e in tm_spans if e <= i)
            side = start_side
            for _ in range(n_tm_before):
                side = "I" if side == "O" else "O"
            topo[i] = side
    else:
        # No topology hints at all — leave as GLOB / cytoplasmic placeholder.
        # ECD will be NULL (consistent with DeepTMHMM's GLOB classification).
        for i in range(n):
            topo[i] = "I"

    topology_str = "".join(topo)
    if len(topology_str) != n:
        return None

    tm_helix_count = len(tm_spans)
    sp_len = sp_end
    ecd_len = topology_str.count("O")
    icd_len = topology_str.count("I")
    if has_sp and tm_helix_count > 0:
        label = "SP+TM"
    elif has_sp and tm_helix_count == 0:
        label = "SP"
    elif tm_helix_count > 0:
        label = "TM"
    else:
        label = "GLOB"

    # Terminal orientations: first/last non-S char
    def terminal(s: str, from_left: bool) -> str:
        chars = s if from_left else s[::-1]
        for ch in chars:
            if ch != "S":
                return {"O": "extracellular", "I": "cytoplasmic", "M": "transmembrane"}.get(ch, "extracellular")
        return "extracellular"

    return {
        "sequence": seq,
        "protein_length": n,
        "per_residue_topology": topology_str,
        "tm_helix_count": tm_helix_count,
        "beta_strand_count": 0,
        "signal_peptide_length": sp_len,
        "ecd_length_residues": ecd_len,
        "icd_length_residues": icd_len,
        "deeptmhmm_label": label,
        "n_terminal_orientation": terminal(topology_str, from_left=True),
        "c_terminal_orientation": terminal(topology_str, from_left=False),
        "predicted_surface_membrane": 1 if label in ("TM", "SP+TM") else 0,
        "predicted_secreted": 1 if label == "SP" else 0,
    }


# ---------------------------------------------------------------------------
# D1 helpers
# ---------------------------------------------------------------------------


def _q(client, account_id, db_id, sql, params=None):
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


_TAXON_BY_SPECIES = {"mouse": 10090, "cynomolgus": 9541}
_COHORT_BY_SPECIES = {"mouse": "mouse_ortholog", "cynomolgus": "cyno_ortholog"}


def _upsert_topology_row(client, account_id, db_id, *, topology_version, cohort,
                         hgnc_id, gene_symbol, species, uniprot_acc, topo: dict) -> None:
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    _q(client, account_id, db_id,
       "INSERT OR REPLACE INTO topology_public ("
       "topology_version, cohort, hgnc_id, uniprot_acc, uniprot_acc_full, isoform_id, "
       "gene_symbol, species, is_canonical, sequence, protein_length, deeptmhmm_label, "
       "tm_helix_count, beta_strand_count, n_terminal_orientation, c_terminal_orientation, "
       "signal_peptide_length, ecd_length_residues, icd_length_residues, "
       "per_residue_topology, predicted_surface_membrane, predicted_secreted, "
       "tool_version, retrieved_at"
       ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
       [topology_version, cohort, hgnc_id, uniprot_acc, uniprot_acc, uniprot_acc,
        gene_symbol, species, 1, topo["sequence"], topo["protein_length"],
        topo["deeptmhmm_label"], topo["tm_helix_count"], topo["beta_strand_count"],
        topo["n_terminal_orientation"], topo["c_terminal_orientation"],
        topo["signal_peptide_length"], topo["ecd_length_residues"], topo["icd_length_residues"],
        topo["per_residue_topology"], topo["predicted_surface_membrane"], topo["predicted_secreted"],
        UNIPROT_TOOL_VERSION, retrieved_at])


def _update_ecd_row(client, account_id, db_id, *, ortholog_ecd_version, human_hgnc_id,
                    species, old_uniprot, new_uniprot, new_symbol, new_ensg,
                    ecd_pct: float | None, n_loops: int) -> None:
    _q(client, account_id, db_id,
       "UPDATE compara_ortholog_ecd "
       "SET ortholog_uniprot_acc = ?, "
       "    ortholog_gene_symbol = ?, "
       "    ortholog_ensembl_gene = ?, "
       "    ecd_pct_identity = ?, "
       "    n_ecd_loops_compared = ? "
       "WHERE ortholog_ecd_version = ? AND human_hgnc_id = ? AND species = ? "
       "  AND ortholog_uniprot_acc = ?",
       [new_uniprot, new_symbol, new_ensg, ecd_pct, n_loops,
        ortholog_ecd_version, human_hgnc_id, species, old_uniprot])


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _backfill_db(client, account_id, db_id, *, label, topology_version,
                 ortholog_ecd_version, dry_run: bool, limit: int | None) -> dict:
    """Run the backfill against one D1. Returns counts."""
    leakers = _q(client, account_id, db_id,
        "SELECT eo.human_gene_symbol, eo.species, eo.human_hgnc_id, eo.human_uniprot_acc, "
        "  eo.ortholog_uniprot_acc, eo.ortholog_ensembl_gene, "
        "  tp_h.per_residue_topology AS h_topo, tp_h.sequence AS h_seq, "
        "  tp_h.ecd_length_residues AS h_ecd_len "
        "FROM compara_ortholog_ecd eo "
        "JOIN topology_public tp_h ON tp_h.uniprot_acc=eo.human_uniprot_acc "
        "  AND tp_h.cohort='human_canonical' AND tp_h.topology_version=? "
        "WHERE eo.ecd_pct_identity IS NULL "
        "  AND eo.ortholog_ecd_version=? "
        "  AND tp_h.ecd_length_residues > 0 "
        "ORDER BY eo.human_gene_symbol, eo.species",
        [topology_version, ortholog_ecd_version])
    if limit:
        leakers = leakers[:limit]
    logger.info("[%s] %d NULL-ECD leakers to inspect", label, len(leakers))

    counts = {"considered": len(leakers), "resolver_same": 0, "resolver_changed": 0,
              "ecd_computed": 0, "no_new_topology": 0, "no_resolver_match": 0,
              "updated": 0}

    for r in leakers:
        taxon = _TAXON_BY_SPECIES[r["species"]]
        cohort = _COHORT_BY_SPECIES[r["species"]]
        # Re-resolve via the FIXED resolver
        new_acc = resolve_uniprot_by_ensembl_gene(
            r["ortholog_ensembl_gene"], organism_taxon_id=taxon,
            ortholog_gene_symbol=r["human_gene_symbol"],
        )
        if not new_acc:
            counts["no_resolver_match"] += 1
            logger.info("  %-12s %-11s  resolver returned None (was %s)",
                        r["human_gene_symbol"], r["species"], r["ortholog_uniprot_acc"])
            continue

        if new_acc == r["ortholog_uniprot_acc"]:
            counts["resolver_same"] += 1
            continue

        counts["resolver_changed"] += 1
        # Fetch UniProt entry & derive topology
        uj = _fetch_uniprot(new_acc, client=client)
        topo = derive_topology(uj) if uj else None
        if not topo:
            counts["no_new_topology"] += 1
            logger.info("  %-12s %-11s  %s → %s  could not derive topology",
                        r["human_gene_symbol"], r["species"], r["ortholog_uniprot_acc"], new_acc)
            continue
        # Compute new ECD identity (human topology vs new ortholog topology)
        res = compute_ecd_identity(
            human_topology=r["h_topo"], human_sequence=r["h_seq"],
            paralog_topology=topo["per_residue_topology"], paralog_sequence=topo["sequence"],
        )
        ecd_pct = res.ecd_pct_identity
        n_loops = res.n_ecd_loops_compared

        # Pull ortholog symbol from UniProt (geneName) if available
        ortholog_symbol = ""
        try:
            ortholog_symbol = (uj.get("genes") or [{}])[0].get("geneName", {}).get("value", "")
        except Exception:
            pass
        if not ortholog_symbol:
            ortholog_symbol = r["human_gene_symbol"]  # fallback

        logger.info("  %-12s %-11s  %s → %s  topo=%s tm=%d ecd_aa=%d  →  ECD %s",
                    r["human_gene_symbol"], r["species"], r["ortholog_uniprot_acc"],
                    new_acc, topo["deeptmhmm_label"], topo["tm_helix_count"],
                    topo["ecd_length_residues"],
                    f"{ecd_pct:.2f}%" if ecd_pct is not None else "NULL")
        if ecd_pct is not None:
            counts["ecd_computed"] += 1

        if dry_run:
            continue

        # Insert/replace the ortholog topology row, then re-point the ecd row.
        _upsert_topology_row(client, account_id, db_id,
                             topology_version=topology_version, cohort=cohort,
                             hgnc_id=r["human_hgnc_id"], gene_symbol=ortholog_symbol,
                             species=r["species"], uniprot_acc=new_acc, topo=topo)
        # Re-fetch ortholog_ensembl_gene from compara_ortholog (already correct there
        # post-PR-39 metadata fix). Use the existing one as a fallback.
        co_rows = _q(client, account_id, db_id,
                     "SELECT ortholog_ensembl_gene, ortholog_gene_symbol FROM compara_ortholog "
                     "WHERE human_ensembl_gene = (SELECT human_ensembl_gene FROM compara_ortholog_ecd "
                     "  WHERE ortholog_ecd_version=? AND human_hgnc_id=? AND species=? "
                     "  AND ortholog_uniprot_acc=? LIMIT 1) "
                     "AND species=? LIMIT 1",
                     [ortholog_ecd_version, r["human_hgnc_id"], r["species"], r["ortholog_uniprot_acc"], r["species"]])
        new_ensg = (co_rows[0]["ortholog_ensembl_gene"] if co_rows else r["ortholog_ensembl_gene"])
        new_sym = (co_rows[0]["ortholog_gene_symbol"] if co_rows else ortholog_symbol)
        _update_ecd_row(client, account_id, db_id,
                        ortholog_ecd_version=ortholog_ecd_version,
                        human_hgnc_id=r["human_hgnc_id"], species=r["species"],
                        old_uniprot=r["ortholog_uniprot_acc"], new_uniprot=new_acc,
                        new_symbol=new_sym, new_ensg=new_ensg,
                        ecd_pct=ecd_pct, n_loops=n_loops)
        counts["updated"] += 1

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-version", default="topo_2026_05_16")
    parser.add_argument("--ortholog-ecd-version", default="orthologecd_topo_2026_05_16")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process at most N leakers (for smoke testing).")
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
        for name, dbid in [("private", private_id), ("public", public_id)]:
            counts = _backfill_db(client, account_id, dbid, label=name,
                                  topology_version=args.topology_version,
                                  ortholog_ecd_version=args.ortholog_ecd_version,
                                  dry_run=args.dry_run, limit=args.limit or None)
            logger.info("[%s] %s", name, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
