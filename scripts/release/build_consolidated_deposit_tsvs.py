"""Build the two consolidated TSVs for the Zenodo deposit.

The previous deposit had three separate genome-wide files
(ncbi-only, pubmed-rescue-only, single-rep benchmark). This script
collapses them to:

  1. triage-runs-genome-with-reasoning.tsv
     Single TSV with every (gene × prompt_variant × replicate) row
     from the canonical Sonnet+NCBI sweep (19,324 cells, 1 rep each)
     and the four Sonnet+PubMed rescue lanes (14,404 cells), tagged
     with ``run_id`` so the reader can split by lane. A re-triaged gene
     has an NCBI row plus its PubMed row; every other gene has 1 row.

  2. triage-benchmark-with-reasoning.tsv
     Per-replicate mainbench TSV with curated truth labels joined
     in. 147 genes × 18 (model × variant) cells × 3 reps = 7,938 rows. Each row keeps its ``replicate``
     index so a reader can see per-rep variability instead of a
     pre-aggregated majority view.

  3. deep-dive-preset-membership.tsv
     One row per deep-dive gene with its public-catalog preset membership.

All three are fetched from the public API
(``api.deliverome.org/surfaceome/v1/``) and joined client-side. No
private credentials needed. Output goes to ``--out-dir`` (default
/tmp/zenodo_deposit_consolidated, which is also update_zenodo_draft.py's
default ``--work-dir``), together with ``deposit_manifest.json``.

Step 1 of the numbered-release procedure after ``cut_data_release.py
--execute`` (see scripts/release/README.md).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import httpx

from accessible_surfaceome.release.catalog_presets import (
    INDUCTION_SUBS,
    PRESETS,
)

OUT_DIR = Path("/tmp/zenodo_deposit_consolidated")
API_BASE = "https://api.deliverome.org/surfaceome/v1"
# /v1/triage/export.tsv is parameterized by ?run_id=. There WAS a cache-key
# collision here: the deliverome.org zone excludes all query strings from the
# edge cache key, and withEdgeCache used to key on that origin, so two run_ids
# fetched in one build collided (the pubmed run came back as a copy of the
# 19,324-row ncbi run). Fixed at the Worker (index.js keys the cache on the
# internal host https://surfaceome-api.cache, which the zone rule can't match),
# so the branded domain now differentiates run_ids correctly. The collision
# guard in build_genome_consolidated stays as defense-in-depth.
EXPORT_BASE = API_BASE
# Every triage export is fetched with with_reasoning=1, which appends
# predicted_key_uncertainty + verdict_reasoning (the agent's free-text
# rationale). The deposit files are named "...-with-reasoning" but shipped
# without these columns through release 1.0.0.

GENOME_NCBI_RUN_ID = "genome_full_sonnet_ncbi_v2"
# The four PubMed-context rescue lanes. Each re-triages a slice of the genes
# the NCBI sweep called `no`; together they cover the genes the
# candidate-universe gate could otherwise drop (CLAUDE.md "run_id
# conventions"). The deposit used to carry only the first lane. The slices
# are nearly disjoint: the 74-gene optimized-cutoff lane re-ran 9 genes an
# earlier lane already held. Every row is kept, tagged by its run_id.
GENOME_PUBMED_RUN_IDS = (
    "genome_full_sonnet_pubmed_ncbi_v1",     # zero-DB ambiguous tail
    "genome_intracellular_pubmed_ncbi_v1",   # zero-DB confidently intracellular
    "genome_1db_trim_pubmed_ncbi_v1",        # 1-of-5-DB trim set
    "genome_optcut_zerodb_pubmed_ncbi_v1",   # orphans of the optimized CSPA cutoff
)
BENCH_RUN_ID = "mainbench_canonical_v2"


def _fetch_tsv(url: str) -> tuple[list[str], list[list[str]]]:
    print(f"  fetching {url} …")
    r = httpx.get(url, timeout=300.0)
    r.raise_for_status()
    lines = r.text.rstrip("\n").split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    print(f"    {len(rows):,} rows, {len(header)} columns")
    return header, rows


def build_genome_consolidated() -> Path:
    print("→ Building consolidated genome-wide TSV")
    ncbi_header, ncbi_rows = _fetch_tsv(
        f"{EXPORT_BASE}/triage/export.tsv?run_id={GENOME_NCBI_RUN_ID}&with_reasoning=1"
    )
    variant_idx = ncbi_header.index("prompt_variant")
    gene_idx = ncbi_header.index("gene_symbol")
    out_header = ["run_id", *ncbi_header]
    for r in ncbi_rows:
        r.insert(0, GENOME_NCBI_RUN_ID)
    pubmed_rows: list[list[str]] = []
    seen_genes: dict[str, str] = {}
    for run_id in GENOME_PUBMED_RUN_IDS:
        header, rows = _fetch_tsv(f"{EXPORT_BASE}/triage/export.tsv?run_id={run_id}&with_reasoning=1")
        if header != ncbi_header:
            raise SystemExit(f"genome NCBI vs {run_id} TSV headers differ — "
                             "endpoint shape changed; re-check before deposit")
        # Collision guard: if the run_id query-string cache ever collides
        # again, a fetch returns some OTHER run. Each lane is a PubMed re-run
        # (a few cells fall back to `naive` when the PubMed fetch failed), it
        # is never the size of the full sweep, and it barely overlaps the
        # other lanes.
        variants = {r[variant_idx] for r in rows}
        if "pubmed_ncbi" not in variants:
            raise SystemExit(
                f"{run_id} carries no pubmed_ncbi rows (variants={variants}) — "
                "run_id cache collision? source the export from a query-aware origin"
            )
        if len(rows) == len(ncbi_rows):
            raise SystemExit(
                f"{run_id} has the full sweep's row count ({len(ncbi_rows)}) — "
                "almost certainly a cache collision; aborting to avoid a duplicate deposit"
            )
        overlap = sorted(
            g for g in {r[gene_idx] for r in rows}
            if seen_genes.get(g, run_id) != run_id
        )
        if len(overlap) > 0.5 * len(rows):
            raise SystemExit(
                f"{run_id} shares {len(overlap)} of {len(rows)} genes with an earlier "
                "lane — a cache collision returning another lane? aborting"
            )
        if overlap:
            print(f"    {len(overlap)} genes also in an earlier lane (kept, tagged "
                  f"by run_id): {', '.join(overlap)}")
        for r in rows:
            seen_genes.setdefault(r[gene_idx], run_id)
            r.insert(0, run_id)
        pubmed_rows.extend(rows)
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
        f"{EXPORT_BASE}/triage/export.tsv?run_id={BENCH_RUN_ID}&with_reasoning=1"
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


def build_deep_dive_presets(genome_path: Path) -> Path:
    """Materialize per-gene preset membership for every deep-dive record.

    One row per gene with a ``surface_annotation`` record. Columns:

    - gene_symbol, uniprot_acc, hgnc_id, schema_version
    - in_canonical, in_likely, in_induced, in_cell_type_restricted
      (the four preset predicates from
      ``accessible_surfaceome.release.catalog_presets``)
    - induction_disease, induction_stress, induction_immune (the
      ``induction_trigger`` sub-axes — only meaningful when
      ``in_induced=1``; emitted standalone so a reanalyst can re-bucket)
    - induction_trigger (raw value)
    - surface_call_reason, state_dependence, evidence_grade,
      surface_specificity, ecd_accessibility_class, confidence — the
      input fields the predicates read, included for auditability so a
      reader can re-derive any preset locally without re-fetching the
      full annotation_json

    Reads ``/v1/genes`` (which carries ``deep_dive_filters`` and other
    catalog metadata per deep-dive gene) and applies the predicates
    in pure Python. Drift between this file and the viewer's
    ``lib/catalog-presets.ts`` is caught by
    ``tests/test_catalog_presets_mirror.py``.
    """
    print("→ Building deep-dive preset membership TSV")
    print(f"  fetching {API_BASE}/genes …")
    r = httpx.get(f"{API_BASE}/genes", timeout=60.0)
    r.raise_for_status()
    payload = r.json()
    # /v1/genes lists every published record with light metadata
    # (gene_symbol, uniprot_acc, schema_version) but no longer carries the
    # filters the predicates read. Those live on /v1/catalog as each row's
    # ``ddf`` block, keyed by ``symbol``. Reading filters from /v1/genes is
    # what made this file come out empty: every entry was skipped as "no
    # deep-dive record".
    entries = payload.get("entries") or payload.get("genes") or []
    if not entries:
        raise SystemExit("/v1/genes returned no entries — endpoint shape "
                         "changed; cannot build preset membership")
    print(f"  fetching {API_BASE}/catalog …")
    rc = httpx.get(f"{API_BASE}/catalog", timeout=120.0)
    rc.raise_for_status()
    ddf_by_symbol = {
        row["symbol"]: row["ddf"]
        for row in rc.json().get("rows", [])
        if row.get("deep_dive") and row.get("ddf")
    }
    if not ddf_by_symbol:
        raise SystemExit("/v1/catalog returned no deep-dive ``ddf`` blocks — "
                         "endpoint shape changed; cannot build preset membership")
    # hgnc_id is on neither endpoint; take it from the genome triage TSV
    # this script has already written.
    hgnc_by_symbol: dict[str, str] = {}
    with genome_path.open() as fh:
        header_g = fh.readline().rstrip("\n").split("\t")
        sym_i, hgnc_i = header_g.index("gene_symbol"), header_g.index("hgnc_id")
        for line in fh:
            cells = line.rstrip("\n").split("\t")
            hgnc_by_symbol.setdefault(cells[sym_i], cells[hgnc_i])

    # Fields surfaced for auditability — same ones the predicates read.
    AUDIT_FIELDS = (
        "induction_trigger",
        "surface_call_reason",
        "state_dependence",
        "evidence_grade",
        "surface_specificity",
        "ecd_accessibility_class",
        "confidence",
        "evidence_density",
        "surface_accessibility",
    )

    header = [
        "gene_symbol",
        "uniprot_acc",
        "hgnc_id",
        "schema_version",
        # Preset columns (1/0). Names mirror catalog-presets.ts keys.
        *[f"in_{key}" for key, _label, _pred in PRESETS],
        # Induction sub-axes — emit alongside preset columns so a
        # reanalyst doesn't have to walk the predicate registry to
        # re-bucket. Each is 1/0 against `induction_trigger` alone.
        *[f"induction_{key}" for key, _label, _pred in INDUCTION_SUBS],
        # Raw input fields the predicates read.
        *AUDIT_FIELDS,
    ]

    out_rows: list[list[str]] = []
    n_with_filters = 0
    for entry in entries:
        sym = entry.get("gene_symbol")
        if not sym:
            continue
        ddf = ddf_by_symbol.get(sym)
        if not ddf:
            # No deep-dive record (the bulk of the genome). The
            # deposit only carries genes with a deep-dive — skip.
            continue
        n_with_filters += 1
        preset_flags = ["1" if pred(ddf) else "0" for _key, _label, pred in PRESETS]
        induction_flags = [
            "1" if pred(ddf) else "0" for _key, _label, pred in INDUCTION_SUBS
        ]
        audit_values = [str(ddf.get(field) or "") for field in AUDIT_FIELDS]
        out_rows.append([
            sym,
            str(entry.get("uniprot_acc") or ""),
            str(hgnc_by_symbol.get(sym) or ""),
            str(entry.get("schema_version") or ""),
            *preset_flags,
            *induction_flags,
            *audit_values,
        ])
    out_rows.sort(key=lambda r: r[0])

    # Every published record must have filters on the catalog. A partial
    # match means the two endpoints disagree on the cohort; zero matches is
    # how this file once shipped empty without anyone noticing.
    if n_with_filters != len(entries):
        raise SystemExit(
            f"only {n_with_filters} of {len(entries)} published records have a "
            "deep-dive filter block on /v1/catalog — refusing to write a partial "
            "preset file"
        )

    out_path = OUT_DIR / "deep-dive-preset-membership.tsv"
    with out_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(out_rows)
    print(f"  wrote {out_path.name}: {len(out_rows):,} rows, "
          f"{len(header)} cols ({out_path.stat().st_size / 1024:.1f} KB) — "
          f"{n_with_filters} of {len(entries)} entries had deep_dive_filters")
    # Print per-preset counts for eyeball sanity.
    for i, (key, _label, _pred) in enumerate(PRESETS):
        col = 4 + i  # gene_symbol, uniprot, hgnc, schema, then preset flags
        n = sum(1 for r in out_rows if r[col] == "1")
        print(f"    {key:24s} {n}/{len(out_rows)}")
    return out_path


# Columns every triage file must carry. verdict_reasoning is why the files
# are called "...-with-reasoning"; error is how a refusal is told apart from
# a malformed call.
REQUIRED_TRIAGE_COLUMNS = ("predicted_key_uncertainty", "verdict_reasoning", "error")
# Written next to the TSVs. update_zenodo_draft.py reads it and refuses to sync
# a README or description whose counts disagree with the files.
MANIFEST_NAME = "deposit_manifest.json"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def validate_and_write_manifest(genome_path: Path, bench_path: Path,
                                presets_path: Path) -> Path:
    """Check the built files against what the deposit promises; fail loudly.

    Each check guards a mistake that shipped once: a deposit with only one of
    the PubMed rescue lanes, triage files named "with-reasoning" that had no
    reasoning, an empty preset file, and refusals that looked like errors.
    """
    problems: list[str] = []
    genome = _read_tsv(genome_path)
    bench = _read_tsv(bench_path)
    presets = _read_tsv(presets_path)

    for name, rows in (("genome", genome), ("benchmark", bench)):
        missing = [c for c in REQUIRED_TRIAGE_COLUMNS if c not in rows[0]]
        if missing:
            problems.append(f"{name} file lacks columns {missing}")
            continue
        answered = [r for r in rows if r["predicted_verdict"]]
        with_reasoning = sum(1 for r in answered if r["verdict_reasoning"])
        if with_reasoning < 0.99 * len(answered):
            problems.append(f"{name} file: only {with_reasoning} of {len(answered)} "
                            "answered calls carry verdict_reasoning")

    lanes = Counter(r["run_id"] for r in genome)
    expected_lanes = {GENOME_NCBI_RUN_ID, *GENOME_PUBMED_RUN_IDS}
    if set(lanes) != expected_lanes:
        problems.append(f"genome file runs {sorted(lanes)} != expected {sorted(expected_lanes)}")

    cells = Counter((r["model"], r["prompt_variant"]) for r in bench)
    n_genes = len({r["gene_symbol"] for r in bench})
    reps = max(int(r["replicate"]) for r in bench)
    short = {f"{m}/{v}": n for (m, v), n in cells.items() if n != n_genes * reps}
    if short:
        problems.append(f"benchmark cells without {n_genes} genes × {reps} reps: {short}")

    if not presets:
        problems.append("preset file is empty")

    if problems:
        raise SystemExit("deposit validation failed:\n  - " + "\n  - ".join(problems))

    manifest = {
        "files": [genome_path.name, bench_path.name, presets_path.name],
        "genome_rows": len(genome),
        "genome_runs": dict(sorted(lanes.items())),
        # The PubMed lanes overlap on a few genes, so their row total is not
        # their gene count; the README states both.
        "genome_pubmed_rows": sum(n for run, n in lanes.items() if run != GENOME_NCBI_RUN_ID),
        "genome_pubmed_genes": len(
            {r["gene_symbol"] for r in genome if r["run_id"] != GENOME_NCBI_RUN_ID}
        ),
        "benchmark_rows": len(bench),
        "benchmark_cells": len(cells),
        "benchmark_genes": n_genes,
        "benchmark_replicates": reps,
        "benchmark_refusals": sum(1 for r in bench if r["error"] == "refusal"),
        "deep_dive_records": len(presets),
    }
    out = OUT_DIR / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\n✓ deposit validated; wrote {out.name}: {json.dumps(manifest)}")
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    global OUT_DIR
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR,
                    help="where to write the TSVs + deposit_manifest.json "
                         "(default: %(default)s)")
    OUT_DIR = ap.parse_args(argv).out_dir
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    genome_path = build_genome_consolidated()
    bench_path = build_bench_multirep()
    presets_path = build_deep_dive_presets(genome_path)
    validate_and_write_manifest(genome_path, bench_path, presets_path)

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
          f"(expect 54 — 18 cells × 3 reps)")
    by_cell: dict[tuple[str, str], list[str]] = {}
    for cells in klk2_bench:
        key = (cells[header.index("model")], cells[header.index("prompt_variant")])
        by_cell.setdefault(key, []).append(cells[header.index("predicted_verdict")])
    print("  KLK2 per-cell verdict spread:")
    for (m, v), verdicts in sorted(by_cell.items()):
        short_m = m.replace("claude-", "")
        print(f"    {short_m:10s}/{v:12s}  {'/'.join(verdicts)}")

    # Reference presets_path so static-analysis doesn't flag it unused.
    # The file is the deposit artifact; the variable just keeps the
    # build's contract explicit in the main() return-flow.
    assert presets_path.exists(), f"presets file vanished: {presets_path}"

    print(f"\n  Output: {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
