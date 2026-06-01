#!/usr/bin/env python
"""Backfill sequences + AFDB/PDB links onto existing deep-dive records.

The ``deterministic_features`` block historically shipped per-residue
topology but not the amino-acid sequence it indexes, nor the AFDB model
download URLs, nor a pointer to the representative experimental (PDB)
structure. Those were fetched at markdown-build time and never made it
into the record / API. This script fills them in for already-published
records so the API payload is self-contained.

**Additive + content-preserving.** It sets ONLY the new fields:

  * ``deterministic_features.canonical_topology.sequence`` (+ each isoform /
    ortholog / close-paralog ``.sequence``)
  * ``deterministic_features.structure.model_{cif,pdb,pae}_url``
  * ``deterministic_features.structure.representative_experimental_structure``

Every pre-existing field is left byte-for-byte untouched, so records from
earlier runs keep their exact content (and ``record_generated_at`` is
unchanged — the publish staleness guard treats the re-publish as a no-op
overwrite of the same timestamp, which it allows).

Sequence source, per entity, in priority order:
  1. public D1 ``topology_public.sequence`` (the exact DeepTMHMM input —
     length is guaranteed to match ``per_residue_topology``), then
  2. UniProt FASTA by accession (fallback when D1 has no row).
A sequence is stored ONLY when its length equals the entity's
``per_residue_topology`` length, so a misaligned sequence is never written.

Usage::

    # dry run — report what WOULD change, touch nothing
    uv run python scripts/backfill_sequences_and_links.py

    # write the JSON snapshots (data/annotations + viewer/public)
    uv run python scripts/backfill_sequences_and_links.py --execute

    # …and re-sync public D1 from the enriched records
    uv run python scripts/backfill_sequences_and_links.py --execute --sync-d1

    # restrict to specific symbols
    uv run python scripts/backfill_sequences_and_links.py --execute EGFR SRC
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import httpx

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _query_public,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import DeterministicFeatures

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

VIEWER_SNAPSHOT_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"
ANNOTATIONS_DIR = REPO_ROOT / "data" / "annotations"

_UA = "accessible-surfaceome/1.0 (backfill_sequences_and_links.py)"
_fasta_cache: dict[str, str | None] = {}
_d1_seq_cache: dict[str, str | None] = {}


# ---------------------------------------------------------------------
# Sequence lookup
# ---------------------------------------------------------------------

def _seq_from_d1(acc: str) -> str | None:
    """``topology_public.sequence`` for ``acc`` (any cohort/version).

    The sequence is the DeepTMHMM input, identical across cohorts, so we
    match either the canonical key (``uniprot_acc``) or the isoform-specific
    key (``uniprot_acc_full``) and take the newest non-null row.
    """
    if acc in _d1_seq_cache:
        return _d1_seq_cache[acc]
    seq: str | None = None
    try:
        rows = _query_public(
            "SELECT sequence FROM topology_public "
            "WHERE (uniprot_acc_full = ? OR uniprot_acc = ?) "
            "  AND sequence IS NOT NULL AND sequence != '' "
            "ORDER BY topology_version DESC LIMIT 1",
            [acc, acc],
        )
        if rows:
            seq = rows[0].get("sequence") or None
    except Exception as exc:  # noqa: BLE001 — D1 is best-effort here
        logger.warning("  ! D1 sequence lookup failed for %s: %s", acc, exc)
    _d1_seq_cache[acc] = seq
    return seq


def _seq_from_uniprot(acc: str) -> str | None:
    """Canonical/isoform sequence from UniProt's FASTA endpoint."""
    if acc in _fasta_cache:
        return _fasta_cache[acc]
    seq: str | None = None
    try:
        resp = httpx.get(
            f"https://rest.uniprot.org/uniprotkb/{acc}.fasta",
            headers={"User-Agent": _UA, "Accept": "text/plain"},
            timeout=30.0,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            seq = (
                "".join(
                    ln for ln in resp.text.splitlines() if ln and not ln.startswith(">")
                ).strip()
                or None
            )
        else:
            logger.warning("  ! UniProt FASTA %s for %s", resp.status_code, acc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("  ! UniProt FASTA fetch failed for %s: %s", acc, exc)
    _fasta_cache[acc] = seq
    return seq


def _aligned_sequence(acc: str | None, topology: str | None) -> str | None:
    """Resolve ``acc``'s sequence, but only return it when its length matches
    ``topology`` (so it lines up with the per-residue string). D1 first
    (exact input), then UniProt FASTA.
    """
    if not acc or not topology:
        return None
    want = len(topology)
    for src in (_seq_from_d1, _seq_from_uniprot):
        seq = src(acc)
        if seq and len(seq) == want:
            return seq
    return None


# ---------------------------------------------------------------------
# Per-record enrichment (additive)
# ---------------------------------------------------------------------

def enrich(rec: dict[str, Any]) -> dict[str, int]:
    """Mutate ``rec`` in place, adding only the new fields. Returns counts."""
    stats = {
        "canonical_seq": 0,
        "isoform_seq": 0,
        "ortholog_seq": 0,
        "paralog_seq": 0,
        "model_urls": 0,
        "rep_struct": 0,
    }
    df = rec.get("deterministic_features") or {}
    if not df:
        return stats

    # Canonical topology
    ct = df.get("canonical_topology") or {}
    if ct and not ct.get("sequence"):
        seq = _aligned_sequence(ct.get("uniprot_acc"), ct.get("per_residue_topology"))
        if seq:
            ct["sequence"] = seq
            stats["canonical_seq"] = 1

    # Isoform topologies
    for iso in df.get("isoform_topologies") or []:
        if iso.get("sequence"):
            continue
        seq = _aligned_sequence(iso.get("uniprot_acc"), iso.get("per_residue_topology"))
        if seq:
            iso["sequence"] = seq
            stats["isoform_seq"] += 1

    # Orthologs (mouse + cyno)
    orth = df.get("orthologs") or {}
    for species in ("mouse", "cynomolgus"):
        for o in orth.get(species) or []:
            if o.get("sequence") or not o.get("per_residue_topology"):
                continue
            seq = _aligned_sequence(
                o.get("ortholog_uniprot_acc"), o.get("per_residue_topology")
            )
            if seq:
                o["sequence"] = seq
                stats["ortholog_seq"] += 1

    # Close paralogs (only those that carry a topology row)
    for p in df.get("paralogs") or []:
        if p.get("sequence") or not p.get("per_residue_topology"):
            continue
        seq = _aligned_sequence(
            p.get("paralog_uniprot_acc"), p.get("per_residue_topology")
        )
        if seq:
            p["sequence"] = seq
            stats["paralog_seq"] += 1

    # Structure: AFDB model links + representative experimental structure
    struct = df.get("structure")
    canon_acc = (rec.get("gene") or {}).get("uniprot_acc")
    if struct is not None and canon_acc:
        from accessible_surfaceome.tools.afdb_plddt import read_afdb_model_links
        from accessible_surfaceome.tools.pdbe_structures import (
            fetch_representative_structure,
        )

        if not any(
            struct.get(k) for k in ("model_cif_url", "model_pdb_url", "model_pae_url")
        ):
            links = read_afdb_model_links(canon_acc)
            if any(links.values()):
                struct.update({k: v for k, v in links.items() if v})
                stats["model_urls"] = 1
        if not struct.get("representative_experimental_structure"):
            rep = fetch_representative_structure(canon_acc)
            if rep is not None:
                struct["representative_experimental_structure"] = json.loads(
                    rep.model_dump_json()
                )
                stats["rep_struct"] = 1
    return stats


# ---------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------

def _symbols(only: list[str]) -> list[str]:
    syms = {p.stem for p in VIEWER_SNAPSHOT_DIR.glob("*.json")}
    if only:
        want = {s.upper() for s in only}
        syms = {s for s in syms if s.upper() in want}
    return sorted(syms)


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbols", nargs="*", help="restrict to these symbols")
    ap.add_argument("--execute", action="store_true", help="write the JSON files")
    ap.add_argument(
        "--sync-d1", action="store_true", help="re-publish enriched records to D1"
    )
    args = ap.parse_args(argv)

    syms = _symbols(args.symbols)
    if not syms:
        logger.error("no matching records under %s", VIEWER_SNAPSHOT_DIR)
        return 1

    logger.info(
        "Backfilling %d record(s) | execute=%s sync_d1=%s\n",
        len(syms),
        args.execute,
        args.sync_d1,
    )
    grand: dict[str, int] = {}
    for sym in syms:
        # Enrich BOTH on-disk copies from their own content (they should be
        # identical; enriching independently keeps them so even if they drift).
        paths = [
            p
            for p in (
                VIEWER_SNAPSHOT_DIR / f"{sym}.json",
                ANNOTATIONS_DIR / f"{sym}.json",
            )
            if p.exists()
        ]
        viewer_dict: dict[str, Any] | None = None
        per_sym: dict[str, int] = {}
        for path in paths:
            rec = json.loads(path.read_text())
            stats = enrich(rec)
            # Validate ONLY the block we touch — deterministic_features — so a
            # record carrying unrelated schema drift elsewhere (a field a
            # concurrent branch added ahead of its model) doesn't block the
            # backfill. This still catches any shape error in the fields we add.
            try:
                DeterministicFeatures.model_validate(
                    rec.get("deterministic_features") or {}
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "  ✗ %s: enriched deterministic_features fails validation: %s",
                    sym,
                    exc,
                )
                return 2
            for k, v in stats.items():
                per_sym[k] = per_sym.get(k, 0) + v
            if args.execute:
                path.write_text(json.dumps(rec, indent=2))
            if path.parent == VIEWER_SNAPSHOT_DIR:
                viewer_dict = rec

        filled = ", ".join(f"{k}={v}" for k, v in per_sym.items() if v) or "nothing new"
        logger.info("  %-8s %s%s", sym, filled, "" if args.execute else "  (dry)")
        for k, v in per_sym.items():
            grand[k] = grand.get(k, 0) + v

        if args.sync_d1 and args.execute and viewer_dict is not None:
            from accessible_surfaceome.cloud.surface_annotation import (
                publish_record_dict,
            )

            res = publish_record_dict(
                viewer_dict, write_snapshot=False, push_to_d1=True
            )
            if res.d1_written:
                logger.info("    → D1 upserted %s", sym)
            else:
                logger.warning("    → D1 skipped %s: %s", sym, res.skipped_reason)

    logger.info(
        "\nTotal filled: %s",
        ", ".join(f"{k}={v}" for k, v in grand.items()) or "nothing",
    )
    if not args.execute:
        logger.info("(dry run — re-run with --execute to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
