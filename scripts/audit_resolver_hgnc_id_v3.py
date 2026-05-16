"""Resolver-collision audit v3 — symbol-keyed vs HGNC-ID-keyed.

Even after the v2 fix (commit ``abace597``) made
``_uniprot_search_by_symbol`` prefer the primary-name match, three
residual failure modes still apply because the entry point is still
a gene symbol:

  1. **Primary-name collisions across reviewed entries.** When two
     reviewed UniProt entries share a primary ``geneName.value``
     (e.g. across HLA / Ig / TCR gene-segment families), the symbol
     resolver returns whichever the UniProt server ranks first;
     order is not promised stable.
  2. **HGNC fallback's silent ``uniprot_ids[0]``.** The fallback at
     ``gene_lookup.py:191-193`` takes the first acc HGNC lists,
     which is HGNC's listing order, not the canonical-isoform pick.
  3. **Symbol-reassignment drift.** When HGNC re-assigns a symbol
     between cohort snapshot and resolver runtime, a symbol-keyed
     query returns the gene the symbol points to *now*, not the
     gene the cohort row meant.

The new ``resolve_by_hgnc_id`` (added in this PR) sidesteps all
three by keying on the stable HGNC ID. This script audits how many
existing D1 triage rows have a UniProt acc that differs between the
two paths.

Inputs:
  * ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv``
    — gene_symbol → hgnc_id mapping for the cohort.
  * D1 ``triage_run`` table — all rows with a non-null
    ``predicted_verdict``, regardless of ``run_id``. Earlier
    audits restricted to ``genome_full_sonnet_ncbi_v1``; this one
    catches every sweep that called the pre-rewrite resolver.

Outputs:
  * ``data/analysis/resolver_definitive_audit_v3.tsv`` — one row per
    divergent symbol with: gene_symbol, hgnc_id, production_pick
    (what the current resolver returns), hgnc_pick (what
    ``resolve_by_hgnc_id`` returns), production_primary_name,
    divergence_class, n_affected_d1_rows.
  * ``data/analysis/resolver_definitive_audit_v3_d1_rows.tsv`` —
    one row per affected (run_id, model, gene_symbol) tuple in D1,
    so Phase 4's targeted re-run can iterate it directly.

Cost: bounded by the HGNC + UniProt API caches (already warm from
prior sweeps via ``_TTL["hgnc"] = 90`` days, ``_TTL["uniprot"] =
30`` days). First run on a cold cache: ~30 minutes for the 19,464
cohort rows over 8 parallel workers. Cached re-runs: <1 minute.
"""
from __future__ import annotations

import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import (
    _entry_primary_symbol,
    _hgnc_record_by_id,
    _TTL,
    _uniprot_search_by_symbol,
    resolve_by_hgnc_id,
)

load_env()

COHORT_TSV = (
    REPO_ROOT
    / "data"
    / "external"
    / "ncbi_gene_info"
    / "Homo_sapiens.protein_coding.with_hgnc.tsv"
)
OUT_SYMBOLS = REPO_ROOT / "data" / "analysis" / "resolver_definitive_audit_v3.tsv"
OUT_D1_ROWS = (
    REPO_ROOT / "data" / "analysis" / "resolver_definitive_audit_v3_d1_rows.tsv"
)

# Workers parallelize HGNC + UniProt API hits. Both endpoints handle
# the load fine; CachedHTTP serializes per-URL so cache writes don't
# race.
N_WORKERS = 8


def _load_cohort_mapping() -> dict[str, str]:
    """gene_symbol → hgnc_id from the canonical NCBI cohort file."""

    out: dict[str, str] = {}
    with open(COHORT_TSV, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sym = row.get("gene_symbol")
            hgnc_id = row.get("hgnc_id")
            if sym and hgnc_id:
                out[sym] = hgnc_id
    return out


def _hgnc_pick(hgnc_id: str, *, http) -> tuple[str | None, str]:
    """Return (canonical_acc, classification) for an HGNC ID.

    Delegates to ``resolve_by_hgnc_id`` so the audit always tracks
    whatever the real resolver does — including the Class B
    fallback (UniProt symbol search when HGNC's xref is empty),
    the picker's primary-name preference, merge-chain follow, and
    deleted-Swiss-Prot drop. Hand-rolled reimplementations of the
    resolver inside the audit silently drift from production.

    The ``classification`` is preserved as a coarse bucket for
    downstream divergence-class assignment: we re-fetch the HGNC
    record just to count xref entries (cached, free).
    """

    try:
        hgnc = _hgnc_record_by_id(hgnc_id, http=http)
    except httpx.HTTPStatusError as e:
        return None, f"hgnc_http_{e.response.status_code}"
    if not hgnc:
        return None, "no_record"
    uniprot_ids = list(hgnc.get("uniprot_ids") or [])
    n_xref = len(uniprot_ids)

    try:
        bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    except LookupError:
        return None, "no_uniprot_xref" if n_xref == 0 else "all_candidates_dropped"
    except httpx.HTTPStatusError as e:
        return None, f"uniprot_http_{e.response.status_code}"

    if n_xref == 0:
        klass = "fallback_symbol_search"
    elif n_xref == 1:
        klass = "single_xref"
    else:
        klass = "multi_xref"
    return bundle.uniprot_acc, klass


def _classify(
    *,
    production_pick: str | None,
    hgnc_pick: str | None,
    production_primary_name: str,
    sym: str,
    hgnc_class: str,
) -> str:
    """Bucket the divergence by likely root cause."""

    if production_pick is None and hgnc_pick is not None:
        return "production_missed_hgnc_caught"
    if production_pick is not None and hgnc_pick is None:
        return "production_caught_hgnc_missed"
    if hgnc_class == "multi_xref":
        return "multi_xref_canonical_pick_disagrees"
    if production_primary_name.upper() != sym.upper():
        # Production fell back to a synonym match (no entry where
        # `sym` is the primary name); HGNC ID went straight to the
        # canonical entry.
        return "synonym_fallback_vs_canonical"
    return "primary_name_collision_or_isoform"


def main() -> None:
    cohort = _load_cohort_mapping()
    print(f"Cohort: {len(cohort):,} symbols with HGNC IDs", flush=True)

    with D1Client() as d1:
        rows = d1.query(
            "SELECT DISTINCT gene_symbol, run_id, model "
            "FROM triage_run WHERE predicted_verdict IS NOT NULL;",
            [],
        )
    d1_rows_by_symbol: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        d1_rows_by_symbol.setdefault(r["gene_symbol"], []).append(
            (r["run_id"], r["model"])
        )
    audited_symbols = sorted(d1_rows_by_symbol.keys())
    print(
        f"D1: {len(rows):,} (gene_symbol, run_id, model) rows over "
        f"{len(audited_symbols):,} unique symbols",
        flush=True,
    )

    http = open_default_client()
    print_lock = threading.Lock()
    done = [0]
    diffs: list[dict[str, str]] = []
    no_hgnc_in_cohort: list[str] = []
    errors: list[tuple[str, str]] = []
    start = time.time()

    def check(sym: str) -> tuple[str, str, dict[str, str] | None]:
        hgnc_id = cohort.get(sym)
        if not hgnc_id:
            return ("no_hgnc_in_cohort", sym, None)
        try:
            production_pick = _uniprot_search_by_symbol(sym, http=http)
            hgnc_pick, hgnc_class = _hgnc_pick(hgnc_id, http=http)
        except Exception as e:
            return ("error", sym, {"msg": str(e)[:200]})

        # Capture production's primary_name for classification:
        production_primary_name = "?"
        if production_pick:
            try:
                payload = http.get_json(
                    "https://rest.uniprot.org/uniprotkb/search",
                    source="uniprot",
                    ttl_days=_TTL["uniprot"],
                    params={
                        "query": (
                            f"gene_exact:{sym} AND organism_id:9606 "
                            "AND reviewed:true"
                        ),
                        "fields": "accession,gene_names",
                        "format": "json",
                        "size": "25",
                    },
                )
                results = (payload or {}).get("results") or []
                for entry in results:
                    if entry.get("primaryAccession") == production_pick:
                        production_primary_name = (
                            _entry_primary_symbol(entry) or "?"
                        )
                        break
            except Exception:
                pass

        if production_pick == hgnc_pick:
            return ("same", sym, None)

        klass = _classify(
            production_pick=production_pick,
            hgnc_pick=hgnc_pick,
            production_primary_name=production_primary_name,
            sym=sym,
            hgnc_class=hgnc_class,
        )
        return (
            "diff",
            sym,
            {
                "gene_symbol": sym,
                "hgnc_id": hgnc_id,
                "production_pick": production_pick or "",
                "production_primary_name": production_primary_name,
                "hgnc_pick": hgnc_pick or "",
                "hgnc_class": hgnc_class,
                "divergence_class": klass,
                "n_affected_d1_rows": str(len(d1_rows_by_symbol.get(sym, []))),
            },
        )

    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(check, sym): sym for sym in audited_symbols}
        for fut in as_completed(futures):
            kind, sym, payload = fut.result()
            if kind == "diff":
                assert payload is not None
                diffs.append(payload)
            elif kind == "no_hgnc_in_cohort":
                no_hgnc_in_cohort.append(sym)
            elif kind == "error":
                assert payload is not None
                errors.append((sym, payload["msg"]))
            with print_lock:
                done[0] += 1
                if done[0] % 500 == 0 or done[0] == len(audited_symbols):
                    elapsed = time.time() - start
                    rate = done[0] / elapsed if elapsed > 0 else 0.0
                    eta = (len(audited_symbols) - done[0]) / rate if rate > 0 else 0
                    print(
                        f"  [{done[0]:>6}/{len(audited_symbols)}]  "
                        f"diffs={len(diffs)}  no_hgnc={len(no_hgnc_in_cohort)}  "
                        f"errors={len(errors)}  rate={rate:.0f}/s  eta={eta:.0f}s",
                        flush=True,
                    )

    print()
    print(f"Audited symbols:        {len(audited_symbols):,}")
    print(f"Divergent (need rerun): {len(diffs):,}")
    print(f"No HGNC ID in cohort:   {len(no_hgnc_in_cohort):,}")
    print(f"Errors:                 {len(errors):,}")
    print()

    diffs.sort(key=lambda d: (d["divergence_class"], d["gene_symbol"]))
    OUT_SYMBOLS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_SYMBOLS, "w", encoding="utf-8", newline="") as f:
        if diffs:
            writer = csv.DictWriter(f, fieldnames=list(diffs[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(diffs)
        else:
            f.write("gene_symbol\thgnc_id\tproduction_pick\tproduction_primary_name\thgnc_pick\thgnc_class\tdivergence_class\tn_affected_d1_rows\n")
    print(f"Wrote {OUT_SYMBOLS.relative_to(REPO_ROOT)}  ({len(diffs)} rows)")

    affected_d1: list[dict[str, str]] = []
    for d in diffs:
        sym = d["gene_symbol"]
        for run_id, model in d1_rows_by_symbol.get(sym, []):
            affected_d1.append(
                {
                    "gene_symbol": sym,
                    "run_id": run_id,
                    "model": model,
                    "hgnc_id": d["hgnc_id"],
                    "production_pick": d["production_pick"],
                    "hgnc_pick": d["hgnc_pick"],
                    "divergence_class": d["divergence_class"],
                }
            )
    affected_d1.sort(key=lambda r: (r["run_id"], r["model"], r["gene_symbol"]))
    with open(OUT_D1_ROWS, "w", encoding="utf-8", newline="") as f:
        if affected_d1:
            writer = csv.DictWriter(f, fieldnames=list(affected_d1[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(affected_d1)
        else:
            f.write("gene_symbol\trun_id\tmodel\thgnc_id\tproduction_pick\thgnc_pick\tdivergence_class\n")
    print(
        f"Wrote {OUT_D1_ROWS.relative_to(REPO_ROOT)}  "
        f"({len(affected_d1)} D1 rows across {len({(r['run_id'], r['model']) for r in affected_d1})} (run_id, model) pairs)"
    )

    if errors:
        print()
        print("First 10 errors:")
        for sym, msg in errors[:10]:
            print(f"  {sym}: {msg}")

    http.close()


if __name__ == "__main__":
    main()
