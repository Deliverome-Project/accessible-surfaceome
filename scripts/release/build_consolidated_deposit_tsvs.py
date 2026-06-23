"""Build the two consolidated TSVs for the Zenodo deposit.

The previous deposit had three separate genome-wide files
(ncbi-only, pubmed-rescue-only, single-rep benchmark). This script
collapses them to:

  1. triage-runs-genome-with-reasoning.tsv
     Single TSV with every (gene × prompt_variant × replicate) row
     from BOTH the canonical Sonnet+NCBI sweep (~19,324 cells, 1 rep
     each) and the Sonnet+PubMed rescue lane (~2,626 cells, 1 rep
     each), tagged with ``run_id`` so the reader can split by lane.
     For the 2,624 genes in the rescue slice that's 2 rows per gene
     (one NCBI, one PubMed); for the remaining ~16,700 it's 1 row.

  2. triage-benchmark-with-reasoning.tsv
     Per-replicate mainbench TSV with curated truth labels joined
     in. 147 genes × (Haiku 4 variants + Sonnet 4 variants + Opus 2
     variants) × 3 reps ≈ 4,400 rows. Each row keeps its ``replicate``
     index so a reader can see per-rep variability instead of a
     pre-aggregated majority view.

Both TSVs are fetched from the public API
(``api.deliverome.org/surfaceome/v1/``) and joined client-side. No
private credentials needed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import httpx

OUT_DIR = Path("/tmp/zenodo_deposit_consolidated")
API_BASE = "https://api.deliverome.org/surfaceome/v1"

GENOME_NCBI_RUN_ID = "genome_full_sonnet_ncbi_v2"
GENOME_PUBMED_RUN_ID = "genome_full_sonnet_pubmed_ncbi_v1"
BENCH_RUN_ID = "mainbench_canonical_v2"


def _fetch_tsv(url: str) -> tuple[list[str], list[list[str]]]:
    print(f"  fetching {url} …")
    r = httpx.get(url, timeout=60.0)
    r.raise_for_status()
    lines = r.text.rstrip("\n").split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    print(f"    {len(rows):,} rows, {len(header)} columns")
    return header, rows


def build_genome_consolidated() -> Path:
    print("→ Building consolidated genome-wide TSV")
    ncbi_header, ncbi_rows = _fetch_tsv(
        f"{API_BASE}/triage/export.tsv?run_id={GENOME_NCBI_RUN_ID}"
    )
    pubmed_header, pubmed_rows = _fetch_tsv(
        f"{API_BASE}/triage/export.tsv?run_id={GENOME_PUBMED_RUN_ID}"
    )
    if ncbi_header != pubmed_header:
        raise SystemExit("genome NCBI vs PubMed TSV headers differ — "
                         "endpoint shape changed; re-check before deposit")

    out_header = ["run_id", *ncbi_header]
    for r in ncbi_rows: r.insert(0, GENOME_NCBI_RUN_ID)
    for r in pubmed_rows: r.insert(0, GENOME_PUBMED_RUN_ID)
    # Sort by gene_symbol (col 1 after run_id insertion), then prompt_variant
    # so paired ncbi/pubmed rows for the same gene sit adjacent.
    gene_col = out_header.index("gene_symbol")
    variant_col = out_header.index("prompt_variant")
    merged = sorted(ncbi_rows + pubmed_rows, key=lambda r: (r[gene_col], r[variant_col]))

    out_path = OUT_DIR / "triage-runs-genome-with-reasoning.tsv"
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(out_header)
        w.writerows(merged)
    print(f"  wrote {out_path.name}: {len(merged):,} rows "
          f"({len(ncbi_rows):,} ncbi + {len(pubmed_rows):,} pubmed), "
          f"{len(out_header)} cols ({out_path.stat().st_size / 1024**2:.1f} MB)")
    return out_path


def build_bench_multirep() -> Path:
    print("→ Building multi-rep benchmark TSV")
    triage_header, triage_rows = _fetch_tsv(
        f"{API_BASE}/triage/export.tsv?run_id={BENCH_RUN_ID}"
    )
    # The triage export carries per-rep predictions; join curated truth
    # per gene from /v1/benchmark (one row per gene with truth_verdict/
    # truth_signal/truth_reason).
    print(f"  fetching {API_BASE}/benchmark …")
    bench_resp = httpx.get(f"{API_BASE}/benchmark", timeout=60.0)
    bench_resp.raise_for_status()
    bench_json = bench_resp.json()
    entries = bench_json.get("entries", [])
    truth: dict[str, tuple[str, str, str, str]] = {}
    for g in entries:
        sym = g.get("gene_symbol")
        if not sym:
            continue
        truth[sym] = (
            g.get("truth_verdict") or "",
            g.get("truth_signal") or "",
            g.get("truth_reason") or "",
            g.get("class") or "",
        )
    print(f"  loaded truth + class for {len(truth):,} genes "
          f"(bench_version {bench_json.get('bench_version')})")
    if not truth:
        raise SystemExit("could not parse /v1/benchmark truth labels — "
                         "endpoint shape changed")

    gene_col = triage_header.index("gene_symbol")
    out_header = ["truth_verdict", "truth_signal", "truth_reason",
                  "truth_class", *triage_header]
    out_rows: list[list[str]] = []
    missing_truth: set[str] = set()
    for r in triage_rows:
        sym = r[gene_col]
        if sym not in truth:
            missing_truth.add(sym)
            tv, ts, tr_, tc = "", "", "", ""
        else:
            tv, ts, tr_, tc = truth[sym]
        out_rows.append([tv, ts, tr_, tc, *r])
    if missing_truth:
        print(f"  ⚠ {len(missing_truth)} genes in mainbench have no truth label "
              f"(joined as empty): {sorted(missing_truth)[:5]}…")
    # Sort by (gene_symbol, model, prompt_variant, replicate). After
    # the 4-col truth prefix, triage cols start at index 4.
    out_rows.sort(key=lambda r: (
        r[4 + triage_header.index("gene_symbol")],
        r[4 + triage_header.index("model")],
        r[4 + triage_header.index("prompt_variant")],
        int(r[4 + triage_header.index("replicate")] or "0"),
    ))

    out_path = OUT_DIR / "triage-benchmark-with-reasoning.tsv"
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(out_header)
        w.writerows(out_rows)
    print(f"  wrote {out_path.name}: {len(out_rows):,} rows, "
          f"{len(out_header)} cols ({out_path.stat().st_size / 1024**2:.2f} MB)")
    return out_path


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    genome_path = build_genome_consolidated()
    bench_path = build_bench_multirep()

    # Sanity checks.
    print("\n→ Sanity-checking KLK2 in both files")
    with genome_path.open() as fh:
        klk2_rows = [line.split("\t") for line in fh.read().split("\n")
                     if line.startswith("genome_full_sonnet_") and "\tKLK2\t" in line]
    print(f"  genome consolidated: KLK2 rows = {len(klk2_rows)} "
          f"(expect 2 — 1 ncbi + 1 pubmed)")
    for row in klk2_rows:
        print(f"    {row[0]:36s} verdict={row[14]:11s} reason={row[15]}")

    with bench_path.open() as fh:
        header = fh.readline().split("\t")
        sym_idx = header.index("gene_symbol")
        klk2_bench = []
        for line in fh:
            cells = line.rstrip("\n").split("\t")
            if cells[sym_idx] == "KLK2":
                klk2_bench.append(cells)
    print(f"  bench multi-rep:     KLK2 rows = {len(klk2_bench)} "
          f"(expect ~30 — 10 cells × 3 reps)")
    by_cell: dict[tuple[str, str], list[str]] = {}
    for cells in klk2_bench:
        key = (cells[header.index("model")], cells[header.index("prompt_variant")])
        by_cell.setdefault(key, []).append(cells[header.index("predicted_verdict")])
    print(f"  KLK2 per-cell verdict spread:")
    for (m, v), verdicts in sorted(by_cell.items()):
        short_m = m.replace("claude-", "").replace("-4-", "4")
        print(f"    {short_m:10s}/{v:12s}  {'/'.join(verdicts)}")

    print(f"\n  Output: {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
