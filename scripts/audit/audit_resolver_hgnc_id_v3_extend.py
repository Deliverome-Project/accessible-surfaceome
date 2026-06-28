"""Extend the v3 audit's affected-rows TSV in two ways without
re-running the per-symbol resolver pass:

  Gap 1 — scan ``deep_dive_run`` and ``benchmark_version`` for the
          same divergent symbols. The original v3 audit only
          enumerated ``triage_run`` rows, but the same resolver bug
          affects any D1 table that stamps a per-symbol uniprot_acc.
          Deep-dive contamination is especially load-bearing — a
          deep-dive row cites its full evidence ledger, so a wrong
          uniprot_acc propagates to every cited PMID / patent / etc.

  Gap 2 — re-validate each HGNC-ID-keyed pick by checking the
          picked entry's primary ``geneName.value`` against HGNC's
          primary ``symbol``. When they disagree, the multi-xref
          canonicalization may have landed on the wrong gene
          (HGNC's xref list contained an acc whose merge chain
          terminates at a different gene's primary). Flag those
          rows ``needs_review=true`` so a human eyeballs them
          before whitelisting the rerun.

Inputs:
  * ``data/analysis/resolver_definitive_audit_v3.tsv`` — must exist
    (produced by ``scripts/audit/audit_resolver_hgnc_id_v3.py``).

Outputs:
  * ``data/analysis/resolver_definitive_audit_v3_extended.tsv`` —
    the symbol-level TSV with two new columns:
      - ``picked_primary_name`` (the geneName.value of the
        HGNC-pick acc)
      - ``hgnc_primary_symbol`` (HGNC's primary ``symbol`` field)
      - ``needs_review`` (true when the two disagree)
  * ``data/analysis/resolver_definitive_audit_v3_d1_rows_full.tsv``
    — affected D1 rows across all three tables, one row per
    (table, run_id, model_or_version, gene_symbol).

Cost: cohort cache is warm from the v3 audit; the only new API
calls are HGNC ID re-fetches (already cached) + UniProt entry
re-fetches for ~50 symbols. Negligible — under a minute on a warm
cache.
"""
from __future__ import annotations

import csv

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import (
    _entry_primary_symbol,
    _hgnc_record_by_id,
    _uniprot_entry,
)

load_env()

IN_TSV = REPO_ROOT / "data" / "analysis" / "resolver_definitive_audit_v3.tsv"
OUT_SYMBOLS = (
    REPO_ROOT / "data" / "analysis" / "resolver_definitive_audit_v3_extended.tsv"
)
OUT_D1_ROWS = (
    REPO_ROOT
    / "data"
    / "analysis"
    / "resolver_definitive_audit_v3_d1_rows_full.tsv"
)


def _enumerate_d1_rows(symbols: list[str]) -> list[dict[str, str]]:
    """Return one row per (table, run_id_or_version, model_or_blank,
    gene_symbol, stored_uniprot_acc) tuple across triage_run,
    deep_dive_run, and benchmark_version."""

    out: list[dict[str, str]] = []
    if not symbols:
        return out
    placeholders = ",".join(["?"] * len(symbols))
    with D1Client() as d1:
        triage = d1.query(
            f"SELECT gene_symbol, run_id, model, uniprot_acc "
            f"FROM triage_run WHERE predicted_verdict IS NOT NULL "
            f"AND gene_symbol IN ({placeholders});",
            list(symbols),
        )
        for r in triage:
            out.append(
                {
                    "table": "triage_run",
                    "run_id_or_version": r.get("run_id") or "",
                    "model": r.get("model") or "",
                    "gene_symbol": r["gene_symbol"],
                    "stored_uniprot_acc": r.get("uniprot_acc") or "",
                }
            )
        deep = d1.query(
            f"SELECT gene_symbol, run_id, model, uniprot_acc "
            f"FROM deep_dive_run WHERE gene_symbol IN ({placeholders});",
            list(symbols),
        )
        for r in deep:
            out.append(
                {
                    "table": "deep_dive_run",
                    "run_id_or_version": r.get("run_id") or "",
                    "model": r.get("model") or "",
                    "gene_symbol": r["gene_symbol"],
                    "stored_uniprot_acc": r.get("uniprot_acc") or "",
                }
            )
        bench = d1.query(
            f"SELECT bench_version, gene_symbol, uniprot_acc "
            f"FROM benchmark_version WHERE gene_symbol IN ({placeholders});",
            list(symbols),
        )
        for r in bench:
            out.append(
                {
                    "table": "benchmark_version",
                    "run_id_or_version": r.get("bench_version") or "",
                    "model": "",
                    "gene_symbol": r["gene_symbol"],
                    "stored_uniprot_acc": r.get("uniprot_acc") or "",
                }
            )
    return out


def _re_validate_pick(
    *, hgnc_id: str, hgnc_pick: str, http
) -> tuple[str, str, bool]:
    """Return (picked_primary_name, hgnc_primary_symbol, needs_review).

    needs_review = True when the picked acc's primary gene name
    doesn't match HGNC's primary symbol — which can happen if HGNC's
    uniprot_ids xref contained an acc whose merge chain terminates
    at a different gene's primary record.
    """

    if not hgnc_pick:
        return ("", "", False)
    hgnc_record = _hgnc_record_by_id(hgnc_id, http=http) or {}
    hgnc_primary = (hgnc_record.get("symbol") or "").strip()
    try:
        entry = _uniprot_entry(hgnc_pick, http=http)
    except Exception:
        return ("", hgnc_primary, True)
    picked_primary = (_entry_primary_symbol(entry) or "").strip()
    needs_review = bool(
        hgnc_primary
        and picked_primary
        and picked_primary.upper() != hgnc_primary.upper()
    )
    return (picked_primary, hgnc_primary, needs_review)


def main() -> None:
    if not IN_TSV.exists():
        raise SystemExit(
            f"Missing {IN_TSV}. Run audit_resolver_hgnc_id_v3.py first."
        )

    with open(IN_TSV, encoding="utf-8") as f:
        diffs = list(csv.DictReader(f, delimiter="\t"))
    if not diffs:
        print("Base audit found zero divergences — nothing to extend.")
        return
    print(f"Read {len(diffs):,} divergent symbols from {IN_TSV.name}.", flush=True)

    # Gap 2: re-validate each pick.
    http = open_default_client()
    review_count = 0
    try:
        for d in diffs:
            picked, hgnc_primary, needs_review = _re_validate_pick(
                hgnc_id=d.get("hgnc_id", ""),
                hgnc_pick=d.get("hgnc_pick", ""),
                http=http,
            )
            d["picked_primary_name"] = picked
            d["hgnc_primary_symbol"] = hgnc_primary
            d["needs_review"] = "true" if needs_review else "false"
            if needs_review:
                review_count += 1
    finally:
        http.close()

    # Gap 1: enumerate affected D1 rows across all three tables.
    symbols = sorted({d["gene_symbol"] for d in diffs})
    print(
        f"Enumerating affected D1 rows across triage_run + deep_dive_run + "
        f"benchmark_version for {len(symbols):,} symbols...",
        flush=True,
    )
    d1_rows = _enumerate_d1_rows(symbols)

    # Attach the divergence metadata to each D1 row for the rerun
    # script's convenience.
    diff_by_sym = {d["gene_symbol"]: d for d in diffs}
    for row in d1_rows:
        meta = diff_by_sym.get(row["gene_symbol"]) or {}
        row["hgnc_id"] = meta.get("hgnc_id", "")
        row["production_pick"] = meta.get("production_pick", "")
        row["hgnc_pick"] = meta.get("hgnc_pick", "")
        row["divergence_class"] = meta.get("divergence_class", "")
        row["needs_review"] = meta.get("needs_review", "")

    # Counts per table for the summary.
    from collections import Counter

    by_table = Counter(r["table"] for r in d1_rows)

    OUT_SYMBOLS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_SYMBOLS, "w", encoding="utf-8", newline="") as f:
        if diffs:
            writer = csv.DictWriter(
                f, fieldnames=list(diffs[0].keys()), delimiter="\t"
            )
            writer.writeheader()
            writer.writerows(diffs)
    print(f"Wrote {OUT_SYMBOLS.relative_to(REPO_ROOT)}  ({len(diffs)} rows)")

    d1_rows.sort(key=lambda r: (r["table"], r["run_id_or_version"], r["gene_symbol"]))
    with open(OUT_D1_ROWS, "w", encoding="utf-8", newline="") as f:
        if d1_rows:
            writer = csv.DictWriter(
                f, fieldnames=list(d1_rows[0].keys()), delimiter="\t"
            )
            writer.writeheader()
            writer.writerows(d1_rows)
        else:
            f.write(
                "table\trun_id_or_version\tmodel\tgene_symbol\t"
                "stored_uniprot_acc\thgnc_id\tproduction_pick\thgnc_pick\t"
                "divergence_class\tneeds_review\n"
            )
    print(
        f"Wrote {OUT_D1_ROWS.relative_to(REPO_ROOT)}  ({len(d1_rows)} D1 rows)"
    )

    print()
    print(f"Divergent symbols:        {len(diffs):,}")
    print(f"  needs_review (Gap 2):   {review_count:,}")
    print()
    print(f"Affected D1 rows:         {len(d1_rows):,}")
    for table, n in by_table.most_common():
        print(f"  {table:24} {n:>5}")


if __name__ == "__main__":
    main()
