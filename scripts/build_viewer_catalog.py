#!/usr/bin/env python3
"""Build the genome-wide catalog the surfaceome viewer's index page consumes.

Joins three canonical sources, keyed on UniProt accession (1:1) and
gene symbol (1:many fall-through):

    1. data/processed/candidate_universe/candidate_universe.tsv
       -- per-(UniProt, gene) row with 7 DB surface flags + n_sources.
    2. data/triage/{SYMBOL}.json (or {UNIPROT}.json)
       -- Haiku triage verdict + reason + reasoning text per gene.
    3. viewer/public/data/surfaceome/{SYMBOL}.json
       -- presence flag: this gene has a deep-dive record.

Writes:

    viewer/public/data/catalog.json
        {"generated_at": "...", "n_rows": int, "rows": [...]}

    viewer/public/data/triage/{SYMBOL}.json
        Lightweight triage projection (verdict / reason / reasoning)
        for the triage-only row click-through. Skipped when no triage
        record exists for that symbol.

This is a derived artifact — committed so Cloudflare Pages doesn't
have to run Python in CI. Re-run whenever the candidate universe,
triage corpus, or deep-dive set changes.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
TRIAGE_DIR = REPO_ROOT / "data/triage"
DEEP_DIVE_DIR = REPO_ROOT / "viewer/public/data/surfaceome"

VIEWER_DATA = REPO_ROOT / "viewer/public/data"
CATALOG_OUT = VIEWER_DATA / "catalog.json"
TRIAGE_OUT_DIR = VIEWER_DATA / "triage"

# DB columns in the candidate-universe TSV that correspond to surface-vote
# signals. Order is the canonical 7 (patent_handle is deep-dive only).
DB_COLS = [
    ("uniprot", "uniprot_surface_flag"),
    ("go", "go_surface_flag"),
    ("surfy", "surfy_surface_flag"),
    ("cspa", "cspa_surface_flag"),
    ("hpa", "hpa_surface_flag"),
    ("deeptmhmm", "deeptmhmm_surface_flag"),
    ("compartments", "compartments_surface_flag"),
]


def _as_int_flag(v: str) -> int:
    """Tolerant 0/1 flag parse. Empty / 'NA' → 0."""
    if not v or v in {"NA", "nan", "None"}:
        return 0
    try:
        return 1 if int(float(v)) else 0
    except (TypeError, ValueError):
        return 0


def _load_triage() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not TRIAGE_DIR.exists():
        return out
    for p in TRIAGE_DIR.glob("*.json"):
        with p.open() as f:
            j = json.load(f)
        gene = j.get("gene") or {}
        sym = gene.get("hgnc_symbol") or p.stem
        out[sym] = {
            "verdict": j.get("verdict"),
            "reason": j.get("reason"),
            "verdict_reasoning": j.get("verdict_reasoning"),
            "uniprot_acc": gene.get("uniprot_acc"),
            "hgnc_id": gene.get("hgnc_id"),
            "model_path": j.get("model_path"),
        }
    return out


def _load_deep_dive_idents() -> dict[str, dict[str, str]]:
    """Read each deep-dive record's identifying block so deep-dive
    genes that don't appear in candidate_universe (e.g. HSPA1A —
    conditional surface, doesn't pass the universe gate) still surface
    as a catalog row."""
    out: dict[str, dict[str, str]] = {}
    if not DEEP_DIVE_DIR.exists():
        return out
    for p in DEEP_DIVE_DIR.glob("*.json"):
        try:
            with p.open() as f:
                j = json.load(f)
        except json.JSONDecodeError:
            continue
        gene = j.get("gene") or {}
        sym = gene.get("hgnc_symbol") or p.stem
        out[sym] = {
            "hgnc_id": gene.get("hgnc_id", ""),
            "uniprot_acc": gene.get("uniprot_acc", ""),
        }
    return out


def _build_rows(
    triage: dict[str, dict[str, Any]],
    deep_dives: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    covered: set[str] = set()

    with CANDIDATE_TSV.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol_resolved") or r.get("gene_symbol") or "").strip()
            uni = (r.get("uniprot_accession") or "").strip()
            if not sym and not uni:
                continue
            db = {k: _as_int_flag(r.get(col, "0")) for k, col in DB_COLS}
            n_sources = int(float(r.get("n_sources_surface", "0") or "0"))
            row: dict[str, Any] = {
                "symbol": sym or uni,
                "uniprot": uni,
                "n_sources": n_sources,
                "db": db,
                "triage": None,
                "deep_dive": sym in deep_dives,
            }
            t = triage.get(sym)
            if t is not None:
                # Long reasoning lives in the per-symbol triage file;
                # the catalog row only carries the verdict + reason so
                # the index payload stays small enough to load fast.
                row["triage"] = {
                    "verdict": t["verdict"],
                    "reason": t["reason"],
                }
            rows.append(row)
            if sym:
                covered.add(sym)

    # Deep-dive genes that don't appear in the candidate universe still
    # belong in the table — they're the strongest accessibility records
    # we have. Synthesize a row from the deep-dive JSON's identifier
    # block (no DB flags — they failed the union gate).
    zero_db = {k: 0 for k, _ in DB_COLS}
    for sym, ident in deep_dives.items():
        if sym in covered:
            continue
        row = {
            "symbol": sym,
            "uniprot": ident["uniprot_acc"],
            "n_sources": 0,
            "db": dict(zero_db),
            "triage": None,
            "deep_dive": True,
        }
        t = triage.get(sym)
        if t is not None:
            row["triage"] = {"verdict": t["verdict"], "reason": t["reason"]}
        rows.append(row)
        covered.add(sym)

    rows.sort(
        key=lambda r: (
            not r["deep_dive"],
            -1 * r["n_sources"],
            r["symbol"],
        )
    )
    return rows


def main() -> None:
    deep_dives = _load_deep_dive_idents()
    triage = _load_triage()
    rows = _build_rows(triage, deep_dives)

    catalog = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_rows": len(rows),
        "n_with_triage": sum(1 for r in rows if r["triage"]),
        "n_with_deep_dive": sum(1 for r in rows if r["deep_dive"]),
        "rows": rows,
    }
    VIEWER_DATA.mkdir(parents=True, exist_ok=True)
    CATALOG_OUT.write_text(json.dumps(catalog, indent=0))

    TRIAGE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sym, t in triage.items():
        (TRIAGE_OUT_DIR / f"{sym}.json").write_text(json.dumps(t, indent=2))

    print(
        f"wrote {CATALOG_OUT.relative_to(REPO_ROOT)} "
        f"({len(rows)} rows, {catalog['n_with_triage']} triage, "
        f"{catalog['n_with_deep_dive']} deep_dive)"
    )


if __name__ == "__main__":
    main()
