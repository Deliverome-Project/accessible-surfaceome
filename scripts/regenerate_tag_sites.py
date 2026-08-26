"""Batch driver: (re)generate the per-gene tag-sites JSON from source.

For each requested gene it runs the deterministic pipeline on the CANONICAL AFDB
model (now including terminal + C-term snorkel sites) AND, for each isoform AFDB
serves a model for, runs the gates on the isoform's OWN model and classifies the
sites shared-vs-unique (``tag_sites.isoform``). The result is written to
``viewer/public/tag-sites/{SYMBOL}.json``, PRESERVING any literature-retrieved
sites already in the file (only the deterministic sites + isoform_pins are
replaced). Then run ``scripts/sync_tag_sites_to_d1.py`` to publish to D1.

Sources (all in-repo / public):
  * sequence + per-residue topology: the committed DeepTMHMM 3line predictions
    (canonical + human isoforms), same as the benchmark;
  * AlphaFold models: AFDB, fetched by accession (canonical + AF-{isoform}-F1),
    cached under ``data/cache/afdb_pdb/`` (gitignored);
  * UniProt feature veto: fetched live (best-effort).

Gene set (pick one):
  --gene SYMBOL ACC        one gene (repeatable)
  --manifest genes.tsv     TSV with `symbol<TAB>acc` per line
  (default)                every gene that already has a tag-sites JSON

    uv run python scripts/regenerate_tag_sites.py --gene TFRC P02786 --dry-run
    uv run python scripts/regenerate_tag_sites.py --manifest genes.tsv
    uv run python scripts/regenerate_tag_sites.py            # refresh existing
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from accessible_surfaceome.tag_sites import features as F
from accessible_surfaceome.tag_sites.run import run_gene, run_isoform_pins, run_ortholog_pins
from accessible_surfaceome.tools.afdb_plddt import read_afdb_model_links

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "data/external/deeptmhmm_surfaceome_predictions"
CANON_3LINE = PRED / "human_canonical_non_hla/predicted_topologies.3line"
ISO_3LINE = PRED / "human_isoforms_from_afdb_non_hla/predicted_topologies.3line"
OUT_DIR = ROOT / "viewer/public/tag-sites"
PDB_CACHE = ROOT / "data/cache/afdb_pdb"
# Public API record is the source of ortholog seq/topology/acc — the same data the
# viewer's ortholog tiles read (deterministic_features.orthologs).
API_BASE = os.environ.get("SURFACEOME_API_BASE", "https://api.deliverome.org/surfaceome").rstrip("/")

log = logging.getLogger("regenerate_tag_sites")


def _json_default(o):
    """Coerce numpy scalars (int64/float64 from the gates + isoform alignment)
    to native Python so json.dumps can serialize the isoform_pins/sites."""
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def parse_3line(path: Path) -> dict[str, tuple[str, str]]:
    """DeepTMHMM 3line -> {accession: (sequence, topology_string)}. Header is
    ``>sp|ACC|NAME | LABEL`` (ACC carries the isoform ``-N`` suffix for isoforms)."""
    recs: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return recs
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines) - 2:
        if lines[i].startswith(">"):
            acc = lines[i].split("|")[1]
            recs[acc] = (lines[i + 1].strip(), lines[i + 2].strip())
            i += 3
        else:
            i += 1
    return recs


def af_pdb(acc: str) -> str:
    """Fetch + cache the AFDB PDB for ``acc`` (canonical OR ``ACC-N`` isoform).
    Raises when AFDB serves no model (the caller skips that structure)."""
    PDB_CACHE.mkdir(parents=True, exist_ok=True)
    path = PDB_CACHE / f"{acc}.pdb"
    if not path.exists():
        url = read_afdb_model_links(acc).get("model_pdb_url")
        if not url:
            raise RuntimeError(f"AFDB has no model for {acc}")
        urllib.request.urlretrieve(url, path)
    return str(path)


def _hazard(acc: str) -> set[int]:
    try:
        return F.hazard_residues(F.fetch_uniprot_features(acc))
    except Exception as ex:  # noqa: BLE001 — best-effort veto
        log.warning("  UniProt features unavailable for %s (%s) -> empty veto", acc, type(ex).__name__)
        return set()


def orthologs_for(symbol: str) -> list[tuple[str, str, str]]:
    """[(ortholog_acc, seq, topology_str), ...] for the CANONICAL mouse + cyno
    one-to-one orthologs of ``symbol``, read from the public API record (the same
    ``deterministic_features.orthologs`` the viewer's ortholog tiles use). Uses the
    ortholog's OWN per-residue topology (its own residue frame, matching its AFDB
    model). Best-effort: empty on any fetch/shape failure — ortholog pins are an
    overlay, never a hard dependency of the deterministic run."""
    try:
        req = urllib.request.Request(
            f"{API_BASE}/v1/genes/{symbol}",
            headers={"accept": "application/json", "user-agent": "Mozilla/5.0 (regenerate_tag_sites)"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed API host
            rec = json.loads(r.read())
    except Exception as ex:  # noqa: BLE001
        log.warning("  ortholog record fetch failed for %s (%s) -> no ortholog pins", symbol, type(ex).__name__)
        return []
    orth = (rec.get("deterministic_features") or {}).get("orthologs") or {}
    out: list[tuple[str, str, str]] = []
    for species in ("mouse", "cynomolgus"):
        for o in orth.get(species) or []:
            if not isinstance(o, dict) or not o.get("is_canonical"):
                continue
            acc, seq, topo = (
                o.get("ortholog_uniprot_acc"),
                o.get("sequence"),
                o.get("per_residue_topology"),
            )
            if acc and seq and topo and len(seq) == len(topo):
                out.append((acc, seq, topo))
            break  # canonical ortholog only
    return out


def isoforms_for(acc: str, iso_map: dict[str, tuple[str, str]]) -> list[tuple[str, str, str]]:
    """[(isoform_id, seq, topo), ...] for the isoforms of ``acc`` present in the
    isoform 3line (keyed by ``ACC-N``)."""
    out = []
    for iso_id, (seq, topo) in iso_map.items():
        base = iso_id.split("-")[0]
        if base == acc and iso_id != acc:
            out.append((iso_id, seq, topo))
    return sorted(out)


def _existing_non_deterministic(path: Path) -> list[dict]:
    """Literature / validated sites already in the file (preserved across a
    deterministic regeneration)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [
        s for s in data.get("sites", [])
        if isinstance(s, dict) and s.get("provenance") != "deterministic_computed"
    ]


def regenerate_gene(
    symbol: str, acc: str, *, canon: dict[str, tuple[str, str]],
    iso_map: dict[str, tuple[str, str]], out_dir: Path, dry_run: bool,
) -> dict[str, int] | None:
    if acc not in canon:
        log.warning("skip %s (%s): not in canonical 3line topology", symbol, acc)
        return None
    seq, topo_s = canon[acc]
    topo = {i + 1: c for i, c in enumerate(topo_s)}
    try:
        pdb = af_pdb(acc)
    except Exception as ex:  # noqa: BLE001
        log.warning("skip %s (%s): AFDB canonical model unavailable (%s)", symbol, acc, ex)
        return None
    hazard = _hazard(acc)

    # Canonical deterministic sites (incl. terminals) via run_gene into a temp dir
    # (temp starts empty, so its payload holds ONLY the fresh deterministic set).
    with tempfile.TemporaryDirectory() as tmp:
        payload = run_gene(
            symbol, acc, sequence=seq, topology=topo, ortholog_seqs=[],
            pdb_path=pdb, hazard_res=hazard, out_dir=tmp,
        )
    det_sites = payload["sites"]

    # Per-isoform pins (gates on each isoform's OWN AFDB model, classified).
    isos = isoforms_for(acc, iso_map)
    pins = run_isoform_pins(
        symbol, acc, canonical_sequence=seq, canonical_sites=det_sites,
        isoforms=isos, fetch_pdb=af_pdb, hazard_for=None,
    ) if isos else []

    # Per-ortholog pins (gates on each ortholog's OWN AFDB model, classified vs
    # human canonical). Keyed by ortholog acc; rendered on the ortholog's own
    # structure at its own residue axis. Best-effort (orthologs sourced from the API).
    orths = orthologs_for(symbol)
    opins = run_ortholog_pins(
        symbol, acc, canonical_sequence=seq, canonical_sites=det_sites,
        orthologs=orths, fetch_pdb=af_pdb, hazard_for=None,
    ) if orths else []

    out_path = out_dir / f"{symbol}.json"
    kept = _existing_non_deterministic(out_path)          # preserve literature sites
    sites = sorted(kept + det_sites, key=lambda s: s["site_id"])
    result = {
        "has_data": len(sites) > 0,
        "gene_symbol": symbol,
        "uniprot_acc": acc,
        "sites": sites,
        "isoform_pins": sorted(pins, key=lambda p: p["site_id"]),
        "ortholog_pins": sorted(opins, key=lambda p: p["site_id"]),
    }
    n_term = sum(1 for s in det_sites if s.get("det_path") in ("terminal", "snorkel"))
    summary = {
        "deterministic": len(det_sites), "terminal_or_snorkel": n_term,
        "literature_kept": len(kept), "isoforms_run": len(isos),
        "isoform_pins": len(pins),
        "isoform_unique": sum(1 for p in pins if p.get("classification") == "unique"),
        "orthologs_run": len(orths), "ortholog_pins": len(opins),
        "ortholog_unique": sum(1 for p in opins if p.get("classification") == "unique"),
    }
    if dry_run:
        log.info("[dry-run] %s %s -> %s", symbol, acc, summary)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, default=_json_default) + "\n")
        log.info("wrote %s -> %s", out_path.relative_to(ROOT), summary)
    return summary


def _gene_list(args) -> list[tuple[str, str]]:
    if args.gene:
        return [(s, a) for s, a in args.gene]
    if args.manifest:
        genes = []
        for line in Path(args.manifest).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sym, _, acc = line.partition("\t")
            if sym and acc:
                genes.append((sym.strip(), acc.strip()))
        return genes
    # default: refresh every gene that already has a tag-sites JSON
    genes = []
    for p in sorted(OUT_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            if d.get("gene_symbol") and d.get("uniprot_acc"):
                genes.append((d["gene_symbol"], d["uniprot_acc"]))
        except (json.JSONDecodeError, OSError):
            continue
    return genes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene", nargs=2, metavar=("SYMBOL", "ACC"), action="append",
                    help="one gene (repeatable)")
    ap.add_argument("--manifest", help="TSV of symbol<TAB>acc")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--limit", type=int, default=0, help="cap number of genes (0 = all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    canon = parse_3line(CANON_3LINE)
    iso_map = parse_3line(ISO_3LINE)
    genes = _gene_list(args)
    if args.limit:
        genes = genes[: args.limit]
    log.info("regenerating %d gene(s) (canonical 3line: %d accs, isoform 3line: %d)%s",
             len(genes), len(canon), len(iso_map), "  [dry-run]" if args.dry_run else "")

    out_dir = Path(args.out_dir)
    totals = {"genes": 0, "det": 0, "term": 0, "pins": 0, "unique": 0, "opins": 0, "ounique": 0}
    for symbol, acc in genes:
        s = regenerate_gene(symbol, acc, canon=canon, iso_map=iso_map,
                            out_dir=out_dir, dry_run=args.dry_run)
        if s:
            totals["genes"] += 1
            totals["det"] += s["deterministic"]
            totals["term"] += s["terminal_or_snorkel"]
            totals["pins"] += s["isoform_pins"]
            totals["unique"] += s["isoform_unique"]
            totals["opins"] += s.get("ortholog_pins", 0)
            totals["ounique"] += s.get("ortholog_unique", 0)
    log.info(
        "done: %d genes | %d deterministic (%d terminal/snorkel) | %d isoform pins (%d unique) "
        "| %d ortholog pins (%d unique)",
        totals["genes"], totals["det"], totals["term"], totals["pins"], totals["unique"],
        totals["opins"], totals["ounique"],
    )
    if not args.dry_run and totals["genes"]:
        log.info("next: uv run python scripts/sync_tag_sites_to_d1.py --version <YYYY-MM-DD>")


if __name__ == "__main__":
    main()
