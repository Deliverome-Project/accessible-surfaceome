"""Batch driver: (re)generate the per-gene LITERATURE tag-sites JSON from the
NEW multi-stage tag-site literature agent.

This is the literature-side mirror of ``scripts/regenerate_tag_sites.py`` (which
regenerates the DETERMINISTIC sites). For each requested control gene it:

  1. Fetches the public API record
     (``https://api.deliverome.org/surfaceome/v1/genes/{SYMBOL}``) with a browser
     User-Agent header (Cloudflare 403s the default urllib UA) and extracts the
     canonical UniProt accession, canonical sequence, and per-residue topology
     string from ``deterministic_features.canonical_topology``.
  2. Fetches the reviewed UniProt entry for that accession
     (``https://rest.uniprot.org/uniprotkb/{acc}.json``) for the protein name and
     synonyms — the public API record carries NO approved-name / alias field, so
     UniProt is the authoritative source for ``protein_name`` + ``aliases``
     (recommended full name, short names, alternative names, CD-antigen names,
     and gene-name synonyms), deduped and excluding the gene symbol.
  3. Runs the multi-stage literature agent
     (``agents.tag_site.runner.run_tag_site_agent``, mode="production") and
     converts to the viewer shape (``to_viewer_sites`` -> provenance
     "literature_retrieved").
  4. Loads ``viewer/public/tag-sites/{SYMBOL}.json``, REPLACES its
     literature_retrieved sites with the fresh ones, PRESERVES every
     deterministic_computed site plus ``isoform_pins`` / ``ortholog_pins`` /
     gene fields, recomputes ``has_data``, and writes back (sites sorted by
     ``site_id``, matching the sibling deterministic regen).

The 12 controls default set is the tag-viewer positive-control panel. Every
quote a shipped site cites is span-verified BY CONSTRUCTION inside the agent —
this script never authors a quote.

    .venv/bin/python scripts/regenerate_tag_site_lit.py --gene TFRC --dry-run
    .venv/bin/python scripts/regenerate_tag_site_lit.py --gene TFRC --gene EGFR
    .venv/bin/python scripts/regenerate_tag_site_lit.py            # all 12
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

# Load ANTHROPIC_API_KEY (and friends) from .env BEFORE importing the agent.
from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.runner import (  # noqa: E402
    run_tag_site_agent,
    to_viewer_sites,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "viewer/public/tag-sites"
API_BASE = "https://api.deliverome.org/surfaceome"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
# Cloudflare 403s the default urllib UA; a browser UA gets through.
UA_HEADERS = {"user-agent": "Mozilla/5.0 (lit-regen)", "accept": "application/json"}

# The tag-viewer positive-control panel.
CONTROLS = [
    "TMEM123", "CD19", "AXL", "MET", "EGFR", "LDLR",
    "CD22", "TNFRSF17", "ERBB2", "NECTIN4", "FOLH1", "TFRC",
]

log = logging.getLogger("regenerate_tag_site_lit")

_VALIDATION_RE = re.compile(r"validation:\s*([^;\]]+)")


def _get_json(url: str, *, timeout: int = 90) -> Any:
    req = urllib.request.Request(url, headers=UA_HEADERS)  # noqa: S310 - fixed hosts
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_record(symbol: str) -> dict[str, Any]:
    return _get_json(f"{API_BASE}/v1/genes/{symbol}")


def extract_from_record(rec: dict[str, Any]) -> tuple[str, str, str]:
    """(uniprot_accession, sequence, per_residue_topology) from the API record.

    The public API record has NO top-level ``uniprot_acc`` (it is null); the
    canonical accession lives under ``gene.uniprot_acc`` and is echoed in
    ``deterministic_features.canonical_topology``. The canonical sequence + the
    per-residue topology STRING (O/I/M/S alphabet) both live in
    ``canonical_topology``.
    """
    gene = rec.get("gene") or {}
    ct = (rec.get("deterministic_features") or {}).get("canonical_topology") or {}
    acc = gene.get("uniprot_acc") or ct.get("uniprot_acc")
    seq = ct.get("sequence")
    topo = ct.get("per_residue_topology")
    if not acc:
        raise ValueError("no uniprot accession in record (gene.uniprot_acc / canonical_topology)")
    if not seq or not topo:
        raise ValueError("canonical_topology missing sequence or per_residue_topology")
    if len(seq) != len(topo):
        raise ValueError(f"sequence ({len(seq)}) / topology ({len(topo)}) length mismatch")
    return acc, seq, topo


def fetch_uniprot_names(acc: str) -> tuple[str, list[str]]:
    """(protein_name, alias_candidates) from the reviewed UniProt entry.

    protein_name = recommendedName.fullName (falls back to the first
    submittedName, then the accession). alias_candidates gathers the recommended
    short names, every alternativeName (full + short), the CD-antigen names, and
    the gene-name synonyms — the raw pool the caller dedupes into ``aliases``.
    The API record carries none of these, so UniProt is the authoritative source.
    """
    d = _get_json(f"{UNIPROT_BASE}/{acc}.json")
    pd = d.get("proteinDescription") or {}
    rn = pd.get("recommendedName") or {}
    protein_name = (rn.get("fullName") or {}).get("value")

    cands: list[str] = []
    cands += [s.get("value") for s in rn.get("shortNames") or []]
    for a in pd.get("alternativeNames") or []:
        fn = (a.get("fullName") or {}).get("value")
        if fn:
            cands.append(fn)
        cands += [s.get("value") for s in a.get("shortNames") or []]
    cands += [c.get("value") for c in pd.get("cdAntigenNames") or []]

    if not protein_name:
        for s in pd.get("submissionNames") or []:
            fn = (s.get("fullName") or {}).get("value")
            if fn:
                protein_name = fn
                break
    if not protein_name:
        protein_name = acc

    # Gene-name synonyms (a stand-in for the "previous symbols" the record lacks).
    for g in d.get("genes") or []:
        cands += [s.get("value") for s in g.get("synonyms") or []]

    return protein_name, [c for c in cands if c]


def build_aliases(gene_symbol: str, protein_name: str, candidates: list[str]) -> list[str]:
    """Deduped [protein_name, *candidates] excluding the gene symbol (case-insensitive)."""
    seen: set[str] = set()
    out: list[str] = []
    for x in [protein_name, *candidates]:
        if not x:
            continue
        k = x.strip()
        if not k or k.upper() == gene_symbol.upper():
            continue
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
    return out


def _validation_of(site: dict[str, Any]) -> str | None:
    m = _VALIDATION_RE.search(site.get("rationale") or "")
    return m.group(1).strip() if m else None


def _quote_of(site: dict[str, Any]) -> str | None:
    for s in site.get("sources") or []:
        claim = s.get("claim")
        if claim:
            return claim
    return None


def _print_lit_sites(symbol: str, sites: list[dict[str, Any]]) -> None:
    """STEP-4 per-site detail for the report."""
    if not sites:
        print("    (no literature sites returned)")
        return
    for s in sites:
        quote = _quote_of(s)
        pmid = None
        for src in s.get("sources") or []:
            if src.get("pmid"):
                pmid = src["pmid"]
                break
        qshow = f'"{quote[:120]}"' if quote else "<<NO QUOTE>>"
        print(
            f"    - {s.get('residue_label')}  kind={s.get('site_kind')}  "
            f"validation={_validation_of(s)}  pmid={pmid}  "
            f"quote_present={bool(quote)}"
        )
        print(f"        quote: {qshow}")


def regenerate_gene(symbol: str, *, dry_run: bool) -> dict[str, Any]:
    """Run the lit agent for one control; merge into (or, dry-run, just report)
    the viewer JSON. Returns a summary dict for the batch report."""
    out_path = OUT_DIR / f"{symbol}.json"
    summary: dict[str, Any] = {"symbol": symbol, "ok": False, "error": None}

    # Baseline lit count from the current file.
    file_data: dict[str, Any] | None = None
    baseline_lit = 0
    file_acc = None
    if out_path.exists():
        file_data = json.loads(out_path.read_text())
        baseline_lit = sum(
            1 for s in file_data.get("sites", [])
            if s.get("provenance") == "literature_retrieved"
        )
        file_acc = file_data.get("uniprot_acc")
    summary["baseline_lit"] = baseline_lit

    # 1. Public API record -> acc / seq / topology.
    rec = fetch_record(symbol)
    acc, seq, topo = extract_from_record(rec)
    summary["uniprot_acc"] = acc
    if file_acc and file_acc != acc:
        log.warning("  %s: record acc %s != viewer-file acc %s (using record acc for agent)",
                    symbol, acc, file_acc)

    # 2. UniProt -> protein_name + aliases.
    protein_name, cands = fetch_uniprot_names(acc)
    aliases = build_aliases(symbol, protein_name, cands)
    summary["protein_name"] = protein_name
    summary["aliases"] = aliases
    log.info("  %s (%s): protein_name=%r aliases=%r", symbol, acc, protein_name, aliases)

    # 3. Run the multi-stage literature agent, convert to viewer shape.
    result = run_tag_site_agent(
        gene_symbol=symbol,
        protein_name=protein_name,
        uniprot_accession=acc,
        aliases=aliases,
        sequence=seq,
        topology=topo,
        mode="production",
    )
    # Use the viewer file's own acc for the site records when present, so the new
    # lit sites match the file (they are expected to be identical anyway).
    lit_sites = to_viewer_sites(result, uniprot_acc=(file_acc or acc))
    summary["new_lit"] = len(lit_sites)
    summary["lit_sites"] = lit_sites
    log.info("  %s: agent returned %d literature site(s)", symbol, len(lit_sites))

    # 4. Merge: keep non-lit (deterministic) sites + pins + gene fields; swap lit.
    if not dry_run:
        if file_data is None:
            summary["error"] = "viewer JSON not found; cannot merge"
            log.error("  %s: %s", symbol, summary["error"])
            return summary
        kept = [
            s for s in file_data.get("sites", [])
            if s.get("provenance") != "literature_retrieved"
        ]
        merged = sorted(kept + lit_sites, key=lambda s: s["site_id"])
        file_data["sites"] = merged
        file_data["has_data"] = len(merged) > 0
        out_path.write_text(json.dumps(file_data, indent=2) + "\n")
        summary["kept_deterministic"] = len(kept)
        summary["total_sites"] = len(merged)
        log.info("  %s: wrote %s (det kept=%d, lit=%d, total=%d)",
                 symbol, out_path.relative_to(ROOT), len(kept), len(lit_sites), len(merged))

    summary["ok"] = True
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gene", action="append", metavar="SYMBOL",
                    help="one control gene symbol (repeatable); default = all 12")
    ap.add_argument("--dry-run", action="store_true",
                    help="run the agent + print results but do NOT write files")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Quiet the per-request httpx chatter; keep the agent's own INFO lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    genes = args.gene if args.gene else list(CONTROLS)
    log.info("regenerating LITERATURE tag-sites for %d gene(s)%s: %s",
             len(genes), "  [dry-run]" if args.dry_run else "", ", ".join(genes))

    summaries: list[dict[str, Any]] = []
    for symbol in genes:
        log.info("\n=== %s ===", symbol)
        try:
            summaries.append(regenerate_gene(symbol, dry_run=args.dry_run))
        except Exception as ex:  # noqa: BLE001 - report per-gene, keep going
            log.exception("  %s FAILED: %s", symbol, ex)
            summaries.append({"symbol": symbol, "ok": False, "error": f"{type(ex).__name__}: {ex}",
                              "baseline_lit": None, "new_lit": None, "lit_sites": []})

    # ---- STEP-4 REPORT ----
    print("\n" + "=" * 78)
    print("LITERATURE TAG-SITE REGENERATION REPORT" + ("  [DRY-RUN — no files written]" if args.dry_run else ""))
    print("=" * 78)
    for s in summaries:
        sym = s["symbol"]
        if not s.get("ok"):
            print(f"\n{sym}: ERROR -> {s.get('error')}")
            continue
        base = s.get("baseline_lit")
        new = s.get("new_lit")
        flag = "  <-- ZERO SITES" if not new else ""
        print(f"\n{sym} ({s.get('uniprot_acc')}): baseline lit={base}  ->  new lit={new}{flag}")
        _print_lit_sites(sym, s.get("lit_sites") or [])

    # Flags
    print("\n" + "-" * 78)
    zero = [s["symbol"] for s in summaries if s.get("ok") and not s.get("new_lit")]
    errored = [s["symbol"] for s in summaries if not s.get("ok")]
    if zero:
        print(f"GENES RETURNING ZERO LITERATURE SITES: {', '.join(zero)}")
    if errored:
        print(f"GENES THAT ERRORED: {', '.join(errored)}")
    if not zero and not errored:
        print("All genes returned >=1 literature site with no errors.")
    print("-" * 78)


if __name__ == "__main__":
    sys.exit(main())
