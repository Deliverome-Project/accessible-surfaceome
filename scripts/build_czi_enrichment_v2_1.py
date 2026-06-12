#!/usr/bin/env python3
"""Build per-gene CZI CellxGene enrichment JSONs — schema v2.1.

Differences from v2.0 (``build_czi_enrichment.py``):

* **classify-first.** v2.0 ran display thresholds before classification,
  which hid signal from the classifier (CD19 ended up `low_specificity`
  because its B-cell expression was pre-filtered to two pre-B subtypes).
  v2.1 classifies on every (cl, ub) pair that passes a lenient noise
  gate (n_expressing ≥ 10, pct ≥ 1%, n_total ≥ 50). The display lists
  keep the v2.0 thresholds — only the classifier sees the broader pool.

* **dual axis.** v2.0 only classifies on cell types. v2.1 emits
  ``cell_type_enrichment`` AND ``tissue_enrichment`` (the per-tissue
  axis schema was already in the viewer's `CellxGeneEnrichment` type;
  v2.0 just never populated it). Tissues get aggregated across all CL
  terms that express in them.

* **not_detected class.** v2.0 mislabeled 3,507 genes (incl. GPR75) as
  ``low_specificity`` whenever fewer than 2 cell types passed the
  classifier filter. v2.1 splits the empty case out as
  ``not_detected`` — "no cell type meets the CZI noise threshold,"
  which reads clearly distinct from "expressed in many cell types,
  none stands out."

* **top_tissues.** v2.0 only emitted top_cell_types; the viewer's
  v2.1-aware code already expects ``top_tissues`` (rank-DESC, capped at
  the same 30-item budget as cell types). v2.1 populates it.

* **legacy mirror.** ``enrichment_class``/``enrichment_cl_ids``/
  ``fold_change`` are kept as top-level mirrors of
  ``cell_type_enrichment.*`` so v2.0-aware readers continue to work
  through the transition.

* **gene filter.** Supports ``--genes-file <path>`` (newline-separated
  symbols) to restrict output to a subset — used for the deep-dive
  test cohort (14 genes) before committing to a full-cohort re-run.

Inputs (override via env vars): same as v2.0.

  CZI_WMG_GZ           — path to CZI's `expression-summary-condensed-DD-MM-YY.csv.gz`
  CZI_TISSUE_COUNTS    — (cl_id, uberon_id, n_cells) TSV
  CZI_UBERON_LABELS    — UBERON_ID → tissue label TSV
  CZI_CL_LABELS        — CL_ID → cell-type label TSV
  CZI_OUT_DIR          — output dir for {SYMBOL}.json (default /tmp/czi_enrichment_v2_1)
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

WMG = Path(os.environ.get(
    "CZI_WMG_GZ",
    "/Users/rebeccacarlson/Git/tess/scripts/tool-validation/.cache/expression-summary-condensed-11-09-25.csv.gz",
))
TISSUE_COUNTS = Path(os.environ.get("CZI_TISSUE_COUNTS", "/tmp/czi_cell_tissue_counts.tsv"))
UBERON_LABELS = Path(os.environ.get("CZI_UBERON_LABELS", "/tmp/uberon_to_label.tsv"))
CL_LABELS = Path(os.environ.get("CZI_CL_LABELS", "/tmp/cl_id_to_label.tsv"))
ENS_MAP = Path(
    Path(__file__).parent.parent
    / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
)
OUT_DIR = Path(os.environ.get("CZI_OUT_DIR", "/tmp/czi_enrichment_v2_1"))
MANIFEST = OUT_DIR.parent / (OUT_DIR.name + "_manifest.tsv")
CENSUS_VERSION = "2025-11-08"
SCHEMA_VERSION = "2.1"

# Classifier eligibility (lenient — captures whatever has signal).
MIN_N_TOTAL_FOR_CLASS = 50
MIN_NNZ_FOR_CLASS = 10
MIN_PCT_FOR_CLASS = 0.01

# Display thresholds (strict — only show what's worth eyeballing).
COMMON_THRESHOLD = 1000
COMMON_TOP_N = 20
RARE_TOP_N = 10
RARE_MIN_MEAN = 2.0
COMMON_MIN_MEAN = 1.0
TOP_K_TISSUES = 3
MAX_CELL_TYPES = 30
MAX_TISSUES = 30

HPA_FOLD = 4.0


# ---------- IO helpers ----------


def load_cl_labels() -> dict[str, str]:
    out: dict[str, str] = {}
    with CL_LABELS.open() as f:
        header = f.readline().rstrip("\n").split("\t")
        if header[0].startswith("cell_type") and "ontology" in header[1]:
            label_idx, id_idx = 0, 1
        elif header[0] == "cl_id":
            id_idx, label_idx = 0, 1
        else:
            id_idx = 0 if header[0].lower().startswith("cl") or "ontology" in header[0] else 1
            label_idx = 1 - id_idx
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= max(id_idx, label_idx):
                continue
            out[parts[id_idx]] = parts[label_idx]
    return out


def load_uberon_labels() -> dict[str, str]:
    out: dict[str, str] = {}
    with UBERON_LABELS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
    return out


def load_tissue_counts() -> tuple[dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
    """Return (cl,uberon)->n, cl->n_total_across_tissues, uberon->n_total_across_celltypes.

    v2.1 adds the per-UBERON total so we can compute pct_expressing at
    the tissue axis (denominator = all cells of any type in that tissue).
    """
    pair: dict[tuple[str, str], int] = {}
    cl_total: dict[str, int] = defaultdict(int)
    ub_total: dict[str, int] = defaultdict(int)
    with TISSUE_COUNTS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            cl, ub, n = parts[0], parts[1], int(parts[2])
            pair[(cl, ub)] = n
            cl_total[cl] += n
            ub_total[ub] += n
    return pair, dict(cl_total), dict(ub_total)


def load_ens_map() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    with ENS_MAP.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sym = row.get("gene_symbol") or ""
            hgnc = row.get("hgnc_id") or ""
            ens_field = row.get("ensembl_gene") or ""
            if not ens_field:
                continue
            for ens in ens_field.replace(";", "|").split("|"):
                ens = ens.strip()
                if ens and ens.startswith("ENSG") and ens not in out:
                    out[ens] = (sym, hgnc)
    return out


# ---------- HPA classification ----------


def classify_hpa(
    entities: dict[str, float],          # entity_id -> mean_log1p_cp10k
    n_totals: dict[str, int],            # entity_id -> n_total
) -> tuple[str, list[str], float | None]:
    """HPA-style classification on whichever axis you pass in.

    Returns (class, entity_ids, fold_change). `class` is one of
    `not_detected | tissue_enriched | group_enriched | tissue_enhanced
    | low_specificity`. `entity_ids` is empty for not_detected /
    low_specificity, one element for tissue_enriched / tissue_enhanced,
    2-5 elements for group_enriched. `fold_change` is None for
    not_detected / low_specificity, ``inf`` when the next-ranked entity
    is zero (the JSON encoder converts to null + a sibling
    `*_infinite: true` flag).
    """
    eligible = [
        (k, math.expm1(m))
        for k, m in entities.items()
        if n_totals.get(k, 0) >= MIN_N_TOTAL_FOR_CLASS
    ]
    # The killer split — v2.0 lumped both cases as low_specificity.
    if len(eligible) == 0:
        return "not_detected", [], None
    if len(eligible) == 1:
        # One entity meets noise + total thresholds; everything else
        # is below detection. That's the strongest possible
        # enrichment signal.
        return "tissue_enriched", [eligible[0][0]], float("inf")

    eligible.sort(key=lambda kv: kv[1], reverse=True)
    linear = [v for _, v in eligible]
    ids = [k for k, _ in eligible]

    # tissue_enriched: top >= 4× next-ranked
    if linear[1] > 0 and linear[0] >= HPA_FOLD * linear[1]:
        return "tissue_enriched", [ids[0]], linear[0] / linear[1]
    if linear[1] == 0 and linear[0] > 0:
        return "tissue_enriched", [ids[0]], float("inf")

    # group_enriched: largest group of 2-5 from top whose min >= 4× next-after-group
    best_group_size = 0
    best_group_fold: float | None = None
    for g in range(5, 1, -1):
        if g >= len(linear):
            continue
        group_min = linear[g - 1]
        next_val = linear[g]
        if next_val > 0 and group_min >= HPA_FOLD * next_val:
            best_group_size = g
            best_group_fold = group_min / next_val
            break
        if next_val == 0 and group_min > 0:
            best_group_size = g
            best_group_fold = float("inf")
            break
    if best_group_size >= 2:
        return ("group_enriched", ids[:best_group_size], best_group_fold)

    # tissue_enhanced: top >= 4× mean of rest
    rest = linear[1:]
    if rest:
        avg_rest = sum(rest) / len(rest)
        if avg_rest > 0 and linear[0] >= HPA_FOLD * avg_rest:
            return "tissue_enhanced", [ids[0]], linear[0] / avg_rest
        if avg_rest == 0 and linear[0] > 0:
            return "tissue_enhanced", [ids[0]], float("inf")

    return "low_specificity", [], None


def fold_change_payload(fold: float | None) -> tuple[float | None, bool]:
    """Serialize fold_change to (value, infinite_flag) for JSON encoding.
    JSON doesn't support inf — we write null + a sibling boolean."""
    if fold is None:
        return None, False
    if math.isinf(fold):
        return None, True
    return round(fold, 3), False


# ---------- per-gene build ----------


def build_record(
    symbol: str,
    hgnc: str,
    ensembl_gene: str,
    cl_to_uberon: dict[str, dict[str, list[float]]],
    cl_labels: dict[str, str],
    uberon_labels: dict[str, str],
    pair_counts: dict[tuple[str, str], int],
    cl_total_counts: dict[str, int],
    ub_total_counts: dict[str, int],
) -> dict:
    # ---- Per-CL pooled across all tissues ----
    cl_means_log: dict[str, float] = {}
    cl_n_total_for_class: dict[str, int] = {}
    cl_n_expressing: dict[str, int] = {}
    cl_n_total_display: dict[str, int] = {}

    for cl, ub_to_stats in cl_to_uberon.items():
        tot_nnz = sum(v[0] for v in ub_to_stats.values())
        tot_sum = sum(v[1] for v in ub_to_stats.values())
        if tot_nnz <= 0:
            continue
        n_total = cl_total_counts.get(cl, 0)
        if n_total <= 0:
            continue
        mean_log = tot_sum / tot_nnz
        cl_n_expressing[cl] = int(tot_nnz)
        cl_n_total_display[cl] = n_total
        pct = tot_nnz / n_total
        # Classifier-eligible: passes noise gate.
        if tot_nnz >= MIN_NNZ_FOR_CLASS and pct >= MIN_PCT_FOR_CLASS:
            cl_means_log[cl] = mean_log
            cl_n_total_for_class[cl] = n_total

    cl_class, cl_ids, cl_fold = classify_hpa(cl_means_log, cl_n_total_for_class)

    # ---- Per-UBERON pooled across all cell types ----
    # Build it once across the gene's WMG entries — every (cl, ub) pair
    # in cl_to_uberon contributes to the UBERON axis.
    ub_means_log: dict[str, float] = {}
    ub_pooled: dict[str, dict[str, float]] = {}
    for cl, ub_to_stats in cl_to_uberon.items():
        for ub, vals in ub_to_stats.items():
            nnz, ssum = vals
            if nnz <= 0:
                continue
            slot = ub_pooled.setdefault(ub, {"nnz": 0.0, "sum": 0.0})
            slot["nnz"] += nnz
            slot["sum"] += ssum
    ub_n_total_for_class: dict[str, int] = {}
    ub_n_expressing: dict[str, int] = {}
    ub_n_total_display: dict[str, int] = {}
    for ub, st in ub_pooled.items():
        nnz = st["nnz"]
        if nnz <= 0:
            continue
        n_total = ub_total_counts.get(ub, 0)
        if n_total <= 0:
            continue
        mean_log = st["sum"] / nnz
        ub_n_expressing[ub] = int(nnz)
        ub_n_total_display[ub] = n_total
        pct = nnz / n_total
        if nnz >= MIN_NNZ_FOR_CLASS and pct >= MIN_PCT_FOR_CLASS:
            ub_means_log[ub] = mean_log
            ub_n_total_for_class[ub] = n_total

    ub_class, ub_ids, ub_fold = classify_hpa(ub_means_log, ub_n_total_for_class)

    # ---- Build display lists ----
    # v2.0 displayed entries solely by mean rank, which let
    # pct=0.01% noise rows (n=1 of 17,571) dominate low-expression
    # genes like GPR75. v2.1 layers the same pct/nnz noise gate the
    # classifier uses onto the COMMON bucket — large cell-type pools
    # (n_total ≥ 1000) need real coverage to display, not a single
    # bright outlier. The rare bucket keeps its mean-only rule
    # because small-n cell types can't meet a pct gate without
    # losing meaningful signal.
    common: list[dict] = []
    rare: list[dict] = []
    for cl in cl_n_expressing:
        n_total = cl_n_total_display[cl]
        n_exp = cl_n_expressing[cl]
        # Recover mean even when the cell type didn't pass the
        # classifier eligibility gate (so rare/small-n cells still
        # show with their actual mean for the table).
        mean_log = cl_means_log.get(cl) or sum(
            v[1] for v in cl_to_uberon[cl].values()
        ) / max(1, sum(v[0] for v in cl_to_uberon[cl].values()))
        entry = {
            "cl_id": cl,
            "mean_log": mean_log,
            "n_expressing": n_exp,
            "n_total": n_total,
        }
        if n_total < MIN_N_TOTAL_FOR_CLASS:
            continue
        if n_total >= COMMON_THRESHOLD:
            pct = n_exp / n_total
            if pct < MIN_PCT_FOR_CLASS or n_exp < MIN_NNZ_FOR_CLASS:
                continue
            common.append(entry)
        elif mean_log >= RARE_MIN_MEAN:
            rare.append(entry)
    common.sort(key=lambda e: e["mean_log"], reverse=True)
    rare.sort(key=lambda e: e["mean_log"], reverse=True)
    common_qual = [e for e in common if e["mean_log"] >= COMMON_MIN_MEAN]
    chosen_common = common_qual[:COMMON_TOP_N]
    chosen_rare = rare[:RARE_TOP_N]
    if len(chosen_common) < COMMON_TOP_N:
        need = COMMON_TOP_N - len(chosen_common)
        chosen_rare = rare[: RARE_TOP_N + need]
    merged: list[dict] = [{**e, "is_rare": False} for e in chosen_common] + [
        {**e, "is_rare": True} for e in chosen_rare
    ]
    merged.sort(key=lambda e: e["mean_log"], reverse=True)
    merged = merged[:MAX_CELL_TYPES]

    top_cell_types: list[dict] = []
    for e in merged:
        cl = e["cl_id"]
        ub_stats = cl_to_uberon.get(cl, {})
        tissues: list[dict] = []
        for ub, vals in ub_stats.items():
            nnz, ssum = vals
            if nnz <= 0:
                continue
            n_total_pair = pair_counts.get((cl, ub), 0)
            if n_total_pair <= 0:
                continue
            mean_t = ssum / nnz
            tissues.append(
                {
                    "tissue": uberon_labels.get(ub, ub),
                    "uberon_id": ub,
                    "mean_log1p_cp10k": round(mean_t, 4),
                    "n_expressing": int(nnz),
                    "n_total": int(n_total_pair),
                    "pct_expressing": round(nnz / n_total_pair, 4),
                }
            )
        tissues.sort(key=lambda t: t["n_expressing"], reverse=True)
        tissues = tissues[:TOP_K_TISSUES]
        n_exp = int(e["n_expressing"])
        n_tot = int(e["n_total"])
        top_cell_types.append(
            {
                "cell_type": cl_labels.get(cl, cl),
                "cl_id": cl,
                "mean_log1p_cp10k": round(e["mean_log"], 4),
                "n_expressing": n_exp,
                "n_total": n_tot,
                "pct_expressing": round(n_exp / n_tot, 4) if n_tot > 0 else None,
                "is_rare": bool(e["is_rare"]),
                "is_trace": bool(n_exp < MIN_NNZ_FOR_CLASS or (n_tot > 0 and n_exp / n_tot < MIN_PCT_FOR_CLASS)),
                "tissues": tissues,
            }
        )

    # ---- Build top_tissues display list ----
    # Tissue display threshold is the same noise gate the classifier
    # uses (pct >= 1%, nnz >= 10), with n_total >= 1000 so we only
    # show well-sampled tissues. Tissues that don't clear the gate get
    # is_trace=True so the chart can render them muted rather than
    # drop them entirely.
    #
    # **Known overcount in pct_expressing.** The denominator is
    # `sum(pair_counts[(cl, ub)] for cl)` — when CZI's WMG has parent
    # and child CL terms for the same cells (e.g. "T cell" + "naive T
    # cell"), the same cell is counted in both pairs, inflating both
    # numerator and denominator. Usually they cancel, but for tissues
    # with deep CL hierarchies it doesn't — CD63 in pancreas yields
    # pct=154% (numerator overcounted more than denominator). Clamp
    # to ≤ 100% so the chart doesn't render nonsensical values;
    # tracked as a follow-up to use a per-UBERON cell-union count
    # instead of summed pair counts.
    tissue_rows: list[dict] = []
    for ub, n_exp in ub_n_expressing.items():
        n_total = ub_n_total_display[ub]
        if n_total < COMMON_THRESHOLD:
            continue
        mean_log = ub_pooled[ub]["sum"] / ub_pooled[ub]["nnz"]
        pct = min(1.0, n_exp / n_total)
        tissue_rows.append(
            {
                "tissue": uberon_labels.get(ub, ub),
                "uberon_id": ub,
                "mean_log1p_cp10k": round(mean_log, 4),
                "n_expressing": n_exp,
                "n_total": n_total,
                "pct_expressing": round(pct, 4),
                "is_trace": bool(n_exp < MIN_NNZ_FOR_CLASS or pct < MIN_PCT_FOR_CLASS),
            }
        )
    tissue_rows.sort(key=lambda r: r["mean_log1p_cp10k"], reverse=True)
    tissue_rows = tissue_rows[:MAX_TISSUES]

    # ---- Assemble record ----
    cl_fold_val, cl_fold_inf = fold_change_payload(cl_fold)
    ub_fold_val, ub_fold_inf = fold_change_payload(ub_fold)
    record = {
        "schema_version": SCHEMA_VERSION,
        "census_version": CENSUS_VERSION,
        "gene_symbol": symbol,
        "hgnc_id": hgnc or None,
        "ensembl_gene": ensembl_gene,
        # v2.1 dual-axis classification
        "cell_type_enrichment": {
            "class": cl_class,
            "cl_ids": cl_ids,
            "fold_change": cl_fold_val,
            "fold_change_infinite": cl_fold_inf,
        },
        "tissue_enrichment": {
            "class": ub_class,
            "uberon_ids": ub_ids,
            "tissue_labels": [uberon_labels.get(u, u) for u in ub_ids],
            "fold_change": ub_fold_val,
            "fold_change_infinite": ub_fold_inf,
        },
        # v2.0 legacy mirror so old readers don't break during the
        # transition. cell_type_enrichment is the source of truth.
        "enrichment_class": cl_class,
        "enrichment_cl_ids": cl_ids,
        "fold_change": cl_fold_val,
        "fold_change_infinite": cl_fold_inf,
        # Display lists
        "top_cell_types": top_cell_types,
        "top_tissues": tissue_rows,
    }
    return record


# ---------- Main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--genes-file",
        type=Path,
        help="Newline-separated gene symbols to restrict output to (default: all).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help=f"Output dir for {{SYMBOL}}.json (default: {OUT_DIR})",
    )
    args = ap.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    gene_filter: set[str] | None = None
    if args.genes_file:
        gene_filter = {
            line.strip().upper()
            for line in args.genes_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        print(f"Gene filter: {len(gene_filter)} symbols", file=sys.stderr)

    print("Loading lookups…", file=sys.stderr)
    cl_labels = load_cl_labels()
    uberon_labels = load_uberon_labels()
    pair_counts, cl_total_counts, ub_total_counts = load_tissue_counts()
    ens_map = load_ens_map()
    print(
        f"  cl_labels={len(cl_labels)} uberon={len(uberon_labels)} "
        f"pair_counts={len(pair_counts)} cl_totals={len(cl_total_counts)} "
        f"ub_totals={len(ub_total_counts)} ens_map={len(ens_map)}",
        file=sys.stderr,
    )

    # When a gene filter is in play, restrict to that subset's
    # Ensembl IDs — saves streaming time + avoids holding the full
    # cohort's aggregate dict in memory.
    keep_ens: set[str] | None = None
    if gene_filter:
        keep_ens = {ens for ens, (sym, _) in ens_map.items() if sym.upper() in gene_filter}
        print(f"  ens filter: {len(keep_ens)} Ensembl IDs match the symbol list", file=sys.stderr)

    t0 = time.time()
    agg: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    )
    print(f"Streaming WMG ({WMG.name})…", file=sys.stderr)
    n_rows = 0
    n_kept = 0
    with gzip.open(WMG, "rt") as f:
        reader = csv.reader(f)
        _header = next(reader)
        for row in reader:
            n_rows += 1
            if n_rows % 5_000_000 == 0:
                print(f"  {n_rows:,} rows ({time.time()-t0:.0f}s, kept {n_kept:,})", file=sys.stderr)
            gene, tissue, _org, cl, nnz_s, sum_s, _sqsum = row
            if keep_ens is not None and gene not in keep_ens:
                continue
            try:
                nnz = float(nnz_s)
                ssum = float(sum_s)
            except ValueError:
                continue
            slot = agg[gene][cl][tissue]
            slot[0] += nnz
            slot[1] += ssum
            n_kept += 1
    print(
        f"Stream done: {n_rows:,} rows in {time.time()-t0:.1f}s "
        f"(kept {n_kept:,} for {len(agg)} genes)",
        file=sys.stderr,
    )

    # ---- Build per-gene records ----
    t1 = time.time()
    class_counts: Counter[str] = Counter()
    tissue_class_counts: Counter[str] = Counter()
    written = 0
    manifest_rows: list[list[str]] = []
    for ensembl_gene, cl_to_uberon in agg.items():
        sym_hgnc = ens_map.get(ensembl_gene)
        if not sym_hgnc:
            continue
        symbol, hgnc = sym_hgnc
        if not symbol:
            continue
        if gene_filter is not None and symbol.upper() not in gene_filter:
            continue
        record = build_record(
            symbol,
            hgnc,
            ensembl_gene,
            cl_to_uberon,
            cl_labels,
            uberon_labels,
            pair_counts,
            cl_total_counts,
            ub_total_counts,
        )
        class_counts[record["cell_type_enrichment"]["class"]] += 1
        tissue_class_counts[record["tissue_enrichment"]["class"]] += 1
        (out_dir / f"{symbol}.json").write_text(json.dumps(record, separators=(",", ":")))
        written += 1
        manifest_rows.append([
            symbol,
            hgnc,
            ensembl_gene,
            record["cell_type_enrichment"]["class"],
            ";".join(record["cell_type_enrichment"]["cl_ids"]),
            record["tissue_enrichment"]["class"],
            ";".join(record["tissue_enrichment"]["uberon_ids"]),
            str(len(record["top_cell_types"])),
            str(len(record["top_tissues"])),
        ])
    print(f"Write done: {written} genes in {time.time()-t1:.1f}s", file=sys.stderr)

    # ---- Manifest ----
    manifest = out_dir.parent / (out_dir.name + "_manifest.tsv")
    with manifest.open("w") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow([
            "gene_symbol", "hgnc_id", "ensembl_gene",
            "cell_type_class", "cell_type_ids",
            "tissue_class", "tissue_ids",
            "n_top_cell_types", "n_top_tissues",
        ])
        w.writerows(manifest_rows)

    # ---- Report ----
    print("\n=== STATS ===", file=sys.stderr)
    print("Cell-type axis classes:", file=sys.stderr)
    for c in ("tissue_enriched", "group_enriched", "tissue_enhanced", "low_specificity", "not_detected"):
        print(f"  {c}: {class_counts.get(c, 0)}", file=sys.stderr)
    print("Tissue axis classes:", file=sys.stderr)
    for c in ("tissue_enriched", "group_enriched", "tissue_enhanced", "low_specificity", "not_detected"):
        print(f"  {c}: {tissue_class_counts.get(c, 0)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
