#!/usr/bin/env python3
"""Build the genome-wide catalog the surfaceome viewer's index page consumes
as an *offline snapshot* — the committed fallback used when the public
Worker's ``/v1/catalog`` endpoint is unreachable.

Same shape and same join logic as
``scripts/upload_candidate_universe_to_d1.py``, so a build that
short-circuits to the snapshot looks identical to one served by the
Worker.

Inputs (canonical, same as the uploader):

    1. data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv
       — 19,325 protein-coding genes (one row per gene_symbol).
    2. data/processed/candidate_universe/candidate_universe.tsv
       — per-gene surface-flag table (7 *_surface_flag columns).
       LEFT-joined onto (1) on gene_symbol_resolved; genes absent
       from the universe get all-zero flags.
    3. data/triage/{SYMBOL}.json
       — Haiku triage verdicts (~120 genes today).
    4. viewer/public/data/surfaceome/{SYMBOL}.json
       — deep-dive SurfaceomeRecord set.

For each gene the catalog row carries the **5 gating DB flags only**
(uniprot, go, surfy, cspa, hpa) — DeepTMHMM and COMPARTMENTS are
auxiliary signals upstream and are filtered out of the public catalog
(see src/accessible_surfaceome/merge/__init__.py for the gate).

Output:

    viewer/public/data/catalog.json
        {"generated_at": "...", "universe_version": "...",
         "n_rows": int, "rows": [...]}

    viewer/public/data/triage/{SYMBOL}.json
        Per-symbol triage projection (verdict / reason / reasoning).

This artifact is committed so Cloudflare Pages builds without
network access can still produce a working viewer. Re-run whenever
the triageable list, candidate universe, triage corpus, or
deep-dive set changes.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAGEABLE_TSV = REPO_ROOT / (
    "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv"
)
CANDIDATE_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
TRIAGE_DIR = REPO_ROOT / "data/triage"
DEEP_DIVE_DIR = REPO_ROOT / "viewer/public/data/surfaceome"

VIEWER_DATA = REPO_ROOT / "viewer/public/data"
CATALOG_OUT = VIEWER_DATA / "catalog.json"
TRIAGE_OUT_DIR = VIEWER_DATA / "triage"


def _flag(row: dict[str, Any] | None, name: str) -> int:
    if row is None:
        return 0
    v = str(row.get(name) or "").strip()
    if not v or v in {"NA", "nan", "None"}:
        return 0
    try:
        return 1 if int(float(v)) else 0
    except ValueError:
        return 0


def _int(row: dict[str, Any], name: str) -> int:
    v = str(row.get(name) or "").strip()
    if not v:
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def _load_candidate_universe_index() -> dict[str, dict[str, Any]]:
    by_sym: dict[str, dict[str, Any]] = {}
    with CANDIDATE_TSV.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol_resolved") or r.get("gene_symbol") or "").strip()
            if not sym:
                continue
            n_sources = _int(r, "n_sources_surface")
            existing = by_sym.get(sym)
            if existing is None or n_sources > _int(existing, "n_sources_surface"):
                by_sym[sym] = r
    return by_sym


def _load_deep_dive_idents() -> dict[str, dict[str, str]]:
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


def _build_rows(
    cu_by_sym: dict[str, dict[str, Any]],
    triage: dict[str, dict[str, Any]],
    deep_dives: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    covered: set[str] = set()
    seen: set[str] = set()
    with TRIAGEABLE_TSV.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            sym = (r.get("gene_symbol") or "").strip()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            cu = cu_by_sym.get(sym)
            uni = ((cu or {}).get("uniprot_accession") or "").strip()
            f_uniprot = _flag(cu, "uniprot_surface_flag")
            f_go      = _flag(cu, "go_surface_flag")
            f_surfy   = _flag(cu, "surfy_surface_flag")
            f_cspa    = _flag(cu, "cspa_surface_flag")
            f_hpa     = _flag(cu, "hpa_surface_flag")
            n_sources = f_uniprot + f_go + f_surfy + f_cspa + f_hpa
            row = {
                "symbol": sym,
                "uniprot": uni,
                "n_sources": n_sources,
                "db": {
                    "uniprot": f_uniprot,
                    "go": f_go,
                    "surfy": f_surfy,
                    "cspa": f_cspa,
                    "hpa": f_hpa,
                },
                "triage": None,
                "deep_dive": sym in deep_dives,
            }
            t = triage.get(sym)
            if t is not None:
                row["triage"] = {"verdict": t["verdict"], "reason": t["reason"]}
            rows.append(row)
            covered.add(sym)

    # Deep-dive genes that aren't in triageable.tsv (e.g. HSPA1A — duplicated
    # locus that NCBI lists separately) still belong in the table.
    for sym, ident in deep_dives.items():
        if sym in covered:
            continue
        row = {
            "symbol": sym,
            "uniprot": ident["uniprot_acc"],
            "n_sources": 0,
            "db": {"uniprot": 0, "go": 0, "surfy": 0, "cspa": 0, "hpa": 0},
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
    cu_by_sym = _load_candidate_universe_index()
    triage = _load_triage()
    deep_dives = _load_deep_dive_idents()
    rows = _build_rows(cu_by_sym, triage, deep_dives)

    catalog = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "universe_version": "snapshot_local",
        "bench_version": None,
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
