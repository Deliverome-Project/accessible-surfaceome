#!/usr/bin/env python3
"""Build per-gene CZI CellxGene enrichment JSONs (schema v2.0).

HPA-style elevation classification + percent expressing + per-tissue breakdown
with two-bucket common/rare split, capped at 30 cell types per gene.

Inputs (override via env vars):
  CZI_WMG_GZ           — path to CZI's `expression-summary-condensed-DD-MM-YY.csv.gz`
                         (the WMG backing file the cellxgene viewer reads).
                         Pull from https://github.com/chanzuckerberg/cellxgene-data-portal
  CZI_TISSUE_COUNTS    — path to (cell_type_ontology_term_id, tissue_ontology_term_id,
                         n_cells) TSV. Derive once via cellxgene_census.obs.value_counts;
                         see scripts/sync_czi_enrichment_to_d1.py docstring for the
                         recipe.
  CZI_UBERON_LABELS    — UBERON_ID → tissue label TSV.
  CZI_CL_LABELS        — CL_ID → cell-type label TSV.
  CZI_OUT_DIR          — directory to write per-gene JSON snapshots (default /tmp/czi_enrichment).

Output: per-gene `{SYMBOL}.json` snapshots in CZI_OUT_DIR plus a flat manifest TSV.
Then post-process with `scripts/fix_czi_enrichment.py` and push to D1 via
`scripts/sync_czi_enrichment_to_d1.py`.

The Ensembl→symbol map is read from the cohort file pinned in this repo.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Inputs — env-var overrides keep this runnable across machines. Defaults
# match the local cache layout the maintainer used to build the
# initial v2.0 release.
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
OUT_DIR = Path(os.environ.get("CZI_OUT_DIR", "/tmp/czi_enrichment"))
MANIFEST = OUT_DIR.parent / (OUT_DIR.name + "_manifest.tsv")
CENSUS_VERSION = "2025-11-08"
SCHEMA_VERSION = "2.1"

# Classification + selection thresholds
MIN_N_TOTAL_FOR_CLASS = 50
MIN_N_EXPRESSING = 10
MIN_PCT = 0.01
COMMON_THRESHOLD = 10_000  # v2.1: was 1000 — tighter common bucket
COMMON_TOP_N = 50  # v2.1.1: was 20 — show the long tail
RARE_TOP_N = 50  # v2.1.1: was 10
RARE_MIN_MEAN = 1.0  # v2.1.1: was 2.0
COMMON_MIN_MEAN = 1.0
TRACE_MIN_N = 1
TRACE_MIN_PCT = 0.0001
HPA_FOLD = 4.0
TOP_K_TISSUES = 20  # v2.1.2: was 3 — per-cell-type tissues list
MAX_CELL_TYPES = 100  # v2.1.1: was 30
TISSUE_MIN_TOTAL = 1_000  # v2.1.2: tissue universe filter
CELLS_BY_TISSUE_PER_TISSUE_CAP = 20  # v2.1.2: top cells per tissue


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_cl_labels() -> dict[str, str]:
    """Return CL:xxx -> human label."""
    out: dict[str, str] = {}
    with CL_LABELS.open() as f:
        header = f.readline().rstrip("\n").split("\t")
        # header may be `cell_type, cell_type_ontology_term_id` OR `cl_id, label`
        if header[0].startswith("cell_type") and "ontology" in header[1]:
            label_idx, id_idx = 0, 1
        elif header[0] == "cl_id":
            id_idx, label_idx = 0, 1
        else:
            # fallback: find which column has CL: ids
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


def load_tissue_counts() -> tuple[dict[tuple[str, str], int], dict[str, int]]:
    """Return (cl,uberon)->n and cl->n_total."""
    pair: dict[tuple[str, str], int] = {}
    cl_total: dict[str, int] = defaultdict(int)
    with TISSUE_COUNTS.open() as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            cl, ub, n = parts[0], parts[1], int(parts[2])
            pair[(cl, ub)] = n
            cl_total[cl] += n
    return pair, dict(cl_total)


def load_ens_map() -> dict[str, tuple[str, str]]:
    """ensembl_gene -> (gene_symbol, hgnc_id)."""
    out: dict[str, tuple[str, str]] = {}
    with ENS_MAP.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sym = row.get("gene_symbol") or ""
            hgnc = row.get("hgnc_id") or ""
            ens_field = row.get("ensembl_gene") or ""
            if not ens_field:
                continue
            # may be |- or ;-separated
            for ens in ens_field.replace(";", "|").split("|"):
                ens = ens.strip()
                if ens and ens.startswith("ENSG") and ens not in out:
                    out[ens] = (sym, hgnc)
    return out


# ---------- HPA classification ----------


def classify_enrichment(
    cl_means_log: dict[str, float],
    cl_n_total: dict[str, int],
) -> tuple[str, list[str], float | None]:
    """Classify on linear CP10K = expm1(log1p_cp10k).

    Only includes cell types with n_total >= MIN_N_TOTAL_FOR_CLASS.
    Returns (class, cl_ids, fold_change).
    """
    eligible = [
        (cl, math.expm1(m))
        for cl, m in cl_means_log.items()
        if cl_n_total.get(cl, 0) >= MIN_N_TOTAL_FOR_CLASS
    ]
    if len(eligible) < 2:
        # Can't classify; treat as low_specificity (or enriched if only 1 with signal)
        return "low_specificity", [], None
    eligible.sort(key=lambda kv: kv[1], reverse=True)
    linear = [v for _, v in eligible]
    cls = [c for c, _ in eligible]

    # tissue_enriched: top >= 4x 2nd
    if linear[1] > 0 and linear[0] >= HPA_FOLD * linear[1]:
        return "tissue_enriched", [cls[0]], linear[0] / linear[1] if linear[1] > 0 else None
    # special-case: 2nd is essentially zero but top > 0 -> still enriched (infinite fold)
    if linear[1] == 0 and linear[0] > 0:
        return "tissue_enriched", [cls[0]], float("inf")

    # group_enriched: find largest contiguous group of 2..5 from top whose min >= 4x next
    best_group_size = 0
    best_group_fold: float | None = None
    for g in range(5, 1, -1):  # prefer largest
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
        return (
            "group_enriched",
            cls[:best_group_size],
            best_group_fold,
        )

    # tissue_enhanced: top >= 4x average of rest
    rest = linear[1:]
    if rest:
        avg_rest = sum(rest) / len(rest)
        if avg_rest > 0 and linear[0] >= HPA_FOLD * avg_rest:
            return "tissue_enhanced", [cls[0]], linear[0] / avg_rest
        if avg_rest == 0 and linear[0] > 0:
            return "tissue_enhanced", [cls[0]], float("inf")

    return "low_specificity", [], None


# ---------- Main ----------


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading lookups...", file=sys.stderr)
    cl_labels = load_cl_labels()
    uberon_labels = load_uberon_labels()
    pair_counts, cl_total_counts = load_tissue_counts()
    ens_map = load_ens_map()
    print(
        f"  cl_labels={len(cl_labels)} uberon={len(uberon_labels)} "
        f"pair_counts={len(pair_counts)} cl_totals={len(cl_total_counts)} "
        f"ens_map={len(ens_map)}",
        file=sys.stderr,
    )

    # Stream WMG: aggregate per (ensembl, cl_id, uberon_id) -> [nnz, sum]
    t0 = time.time()
    # gene -> cl -> uberon -> [nnz, sum]
    agg: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    )

    print("Streaming WMG...", file=sys.stderr)
    n_rows = 0
    with gzip.open(WMG, "rt") as f:
        reader = csv.reader(f)
        header = next(reader)
        # header: gene, tissue, organism, cell_type, nnz, sum, sqsum
        for row in reader:
            n_rows += 1
            if n_rows % 5_000_000 == 0:
                print(f"  {n_rows:,} rows ({time.time()-t0:.0f}s)", file=sys.stderr)
            gene, tissue, _org, cl, nnz_s, sum_s, _sqsum = row
            try:
                nnz = float(nnz_s)
                ssum = float(sum_s)
            except ValueError:
                continue
            slot = agg[gene][cl][tissue]
            slot[0] += nnz
            slot[1] += ssum
    t_stream = time.time() - t0
    print(f"Stream done: {n_rows:,} rows in {t_stream:.1f}s", file=sys.stderr)

    # Build JSONs
    t1 = time.time()
    written = 0
    class_counts: Counter[str] = Counter()
    rare_examples: list[tuple[str, str, float, int]] = []  # gene, cl_label, mean, n_total

    manifest_rows: list[list[str]] = []

    for gene, cl_to_uberon in agg.items():
        sym_hgnc = ens_map.get(gene)
        if not sym_hgnc:
            continue
        symbol, hgnc = sym_hgnc
        if not symbol:
            continue

        # Per-cell-type pooled stats (across all tissues observed in WMG for this gene).
        # n_total is taken from the global tissue_counts cache.
        cl_pooled: dict[str, dict[str, float]] = {}
        cl_means_log: dict[str, float] = {}
        cl_n_total_filtered: dict[str, int] = {}

        for cl, ub_to_stats in cl_to_uberon.items():
            tot_nnz = sum(v[0] for v in ub_to_stats.values())
            tot_sum = sum(v[1] for v in ub_to_stats.values())
            if tot_nnz <= 0:
                continue
            n_total = cl_total_counts.get(cl, 0)
            if n_total <= 0:
                # We can still emit if we know n_expressing, but we need n_total.
                continue
            # mean among expressing cells (log1p CP10K) — shown in JSON
            mean_log_expressing = tot_sum / tot_nnz
            cl_pooled[cl] = {
                "n_expressing": tot_nnz,
                "sum": tot_sum,
                "mean_log": mean_log_expressing,
                "n_total": n_total,
            }
            # Use the expressing-cell mean for HPA classification, but ONLY
            # include cell types with non-trivial support — at least 10
            # expressing cells AND pct_expressing >= 1%. This avoids
            # 3-out-of-5770 spurious high-mean entries dominating the rank.
            pct_exp = tot_nnz / n_total if n_total > 0 else 0.0
            if tot_nnz >= 10 and pct_exp >= 0.01:
                cl_means_log[cl] = mean_log_expressing
                cl_n_total_filtered[cl] = n_total

        # Classification (uses FULL list with n_total >= 50)
        enr_class, enr_ids, fold = classify_enrichment(cl_means_log, cl_n_total_filtered)
        class_counts[enr_class] += 1

        # Build the top_cell_types list (two-bucket split)
        common = []  # n_total >= 1000 AND n_total >= 50
        rare = []  # n_total < 1000 AND n_total >= 50 AND mean >= 2.0
        for cl, stats in cl_pooled.items():
            if stats["n_total"] < MIN_N_TOTAL_FOR_CLASS:
                continue
            entry = {
                "cl_id": cl,
                "mean_log": stats["mean_log"],
                "n_expressing": stats["n_expressing"],
                "n_total": stats["n_total"],
            }
            if stats["n_total"] >= COMMON_THRESHOLD:
                common.append(entry)
            else:
                if stats["mean_log"] >= RARE_MIN_MEAN:
                    rare.append(entry)

        common.sort(key=lambda e: e["mean_log"], reverse=True)
        rare.sort(key=lambda e: e["mean_log"], reverse=True)

        # Top 20 common (filter to mean >= 1.0 for inclusion in main bucket)
        common_qual = [e for e in common if e["mean_log"] >= COMMON_MIN_MEAN]
        chosen_common = common_qual[:COMMON_TOP_N]
        chosen_rare = rare[:RARE_TOP_N]

        # Backfill from rare if fewer than COMMON_TOP_N qualified common
        if len(chosen_common) < COMMON_TOP_N:
            need = COMMON_TOP_N - len(chosen_common)
            # take more from rare beyond the first RARE_TOP_N (but those still must satisfy mean>=2)
            backfill = rare[RARE_TOP_N : RARE_TOP_N + need]
            # actually: spec says "backfill from rare" — simplest: extend chosen_rare to cover
            # We'll keep rare list at chosen_rare and let total cap handle it
            chosen_rare = rare[: RARE_TOP_N + need]

        # Compose, cap at MAX_CELL_TYPES, mark is_rare
        merged: list[dict] = []
        for e in chosen_common:
            merged.append({**e, "is_rare": False})
        for e in chosen_rare:
            merged.append({**e, "is_rare": True})
        # Sort by mean_log desc but keep cap; spec says 20 common + 10 rare so we already cap at 30
        merged = merged[:MAX_CELL_TYPES]

        # Sort final list by mean_log desc for readability
        merged.sort(key=lambda e: e["mean_log"], reverse=True)

        # Build tissues breakdown for each chosen cell type
        top_cell_types_out = []
        for e in merged:
            cl = e["cl_id"]
            ub_stats = cl_to_uberon.get(cl, {})
            tissues = []
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
                        "pct_expressing": round(nnz / n_total_pair, 4)
                        if n_total_pair > 0
                        else None,
                    }
                )
            tissues.sort(key=lambda t: t["n_expressing"], reverse=True)
            tissues = tissues[:TOP_K_TISSUES]

            n_exp = int(e["n_expressing"])
            n_tot = int(e["n_total"])
            pct = (n_exp / n_tot) if n_tot > 0 else 0.0
            # v2.1.1+ is_trace flag: cell type passes the universe
            # filter (n_total>=50) but fails the noise floor
            # (n_expressing >= 10 AND pct >= 1%). Viewer renders these
            # muted so the reader sees the long-tail without confusing
            # it with the qualified ranking.
            is_trace = bool(n_exp < MIN_N_EXPRESSING or pct < MIN_PCT)
            entry_out = {
                "cell_type": cl_labels.get(cl, cl),
                "cl_id": cl,
                "mean_log1p_cp10k": round(e["mean_log"], 4),
                "n_expressing": n_exp,
                "n_total": n_tot,
                "pct_expressing": round(pct, 4) if n_tot > 0 else None,
                "is_rare": bool(e["is_rare"]),
                "is_trace": is_trace,
                "tissues": tissues,
            }
            top_cell_types_out.append(entry_out)

            if e["is_rare"]:
                if len(rare_examples) < 50:
                    rare_examples.append(
                        (
                            symbol,
                            cl_labels.get(cl, cl),
                            round(e["mean_log"], 3),
                            n_tot,
                        )
                    )

        # v2.1.2: build per-tissue aggregation + reverse cells_by_tissue
        # map. This is the same data structure the single-gene script
        # produces; viewer's tissue cross-filter relies on it to find
        # cell types whose pooled mean is too low to make the global
        # top_cell_types cap (e.g. fibroblast in GPR75's vasculature).
        ub_pooled: dict[str, dict[str, float]] = {}  # ub -> {nnz, sum, n_total}
        cells_by_tissue: dict[str, list[dict]] = {}
        ub_total_counts: dict[str, int] = {}
        for (cl_pair, ub_pair), n_pair in pair_counts.items():
            ub_total_counts[ub_pair] = ub_total_counts.get(ub_pair, 0) + n_pair

        for cl, ub_to_stats in cl_to_uberon.items():
            for ub, (nnz, ssum) in ub_to_stats.items():
                if nnz <= 0:
                    continue
                # Pool for top_tissues
                slot = ub_pooled.setdefault(ub, {"nnz": 0, "sum": 0.0})
                slot["nnz"] += nnz
                slot["sum"] += ssum
                # Reverse map: cells_by_tissue[ub] = [cells expressing here]
                n_total_pair = pair_counts.get((cl, ub), 0)
                if n_total_pair < 50:
                    continue
                cell_pct = nnz / n_total_pair if n_total_pair else 0.0
                cells_by_tissue.setdefault(ub, []).append({
                    "cl_id": cl,
                    "cell_type": cl_labels.get(cl, cl),
                    "mean_log1p_cp10k": round(ssum / nnz, 4),
                    "n_expressing": int(nnz),
                    "n_total": int(n_total_pair),
                    "pct_expressing": round(min(1.0, cell_pct), 4),
                    "is_trace": bool(
                        nnz < MIN_N_EXPRESSING or cell_pct < MIN_PCT
                    ),
                })

        # Sort + cap each tissue's cell list
        for ub in cells_by_tissue:
            cells_by_tissue[ub].sort(key=lambda c: -c["n_expressing"])
            cells_by_tissue[ub] = cells_by_tissue[ub][:CELLS_BY_TISSUE_PER_TISSUE_CAP]

        # Build top_tissues rows
        top_tissues_out: list[dict] = []
        for ub, slot in ub_pooled.items():
            nnz_ub = slot["nnz"]
            ssum_ub = slot["sum"]
            n_total_ub = ub_total_counts.get(ub, 0)
            if n_total_ub < TISSUE_MIN_TOTAL:
                continue
            mean_ub = ssum_ub / nnz_ub if nnz_ub else 0.0
            pct_ub = nnz_ub / n_total_ub if n_total_ub else 0.0
            is_trace_ub = bool(
                nnz_ub < MIN_N_EXPRESSING or pct_ub < MIN_PCT
            )
            top_tissues_out.append({
                "tissue": uberon_labels.get(ub, ub),
                "uberon_id": ub,
                "mean_log1p_cp10k": round(mean_ub, 4),
                "n_expressing": int(nnz_ub),
                "n_total": int(n_total_ub),
                "pct_expressing": round(min(1.0, pct_ub), 4),
                "is_trace": is_trace_ub,
            })
        # Qualified first, then trace, each by mean DESC.
        top_tissues_out.sort(
            key=lambda t: (t["is_trace"], -t["mean_log1p_cp10k"]),
        )

        # fold_change JSON encoding (inf -> None marker)
        if fold is None:
            fold_out: float | None = None
        elif math.isinf(fold):
            fold_out = None  # sentinel "infinite" -- write as null with note
        else:
            fold_out = round(fold, 3)

        record = {
            "schema_version": SCHEMA_VERSION,
            "census_version": CENSUS_VERSION,
            "gene_symbol": symbol,
            "hgnc_id": hgnc or None,
            "ensembl_gene": gene,
            "enrichment_class": enr_class,
            "enrichment_cl_ids": enr_ids,
            "fold_change": fold_out,
            "fold_change_infinite": bool(fold is not None and math.isinf(fold)),
            "top_cell_types": top_cell_types_out,
            "top_tissues": top_tissues_out,
            "cells_by_tissue": cells_by_tissue,
        }

        out_path = OUT_DIR / f"{symbol}.json"
        with out_path.open("w") as f:
            json.dump(record, f, separators=(",", ":"))
        written += 1
        manifest_rows.append(
            [
                symbol,
                hgnc,
                gene,
                enr_class,
                ";".join(enr_ids),
                "" if fold_out is None else str(fold_out),
                str(len(top_cell_types_out)),
            ]
        )

    t_write = time.time() - t1
    print(f"JSON write done: {written} genes in {t_write:.1f}s", file=sys.stderr)

    # Manifest
    with MANIFEST.open("w") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(
            [
                "gene_symbol",
                "hgnc_id",
                "ensembl_gene",
                "enrichment_class",
                "enrichment_cl_ids",
                "fold_change",
                "n_top_cell_types",
            ]
        )
        w.writerows(manifest_rows)

    # Report
    print("\n=== STATS ===", file=sys.stderr)
    print(f"Stream time: {t_stream:.1f}s", file=sys.stderr)
    print(f"Write time:  {t_write:.1f}s", file=sys.stderr)
    print(f"Total genes written: {written}", file=sys.stderr)
    print("Class distribution:", file=sys.stderr)
    for c in ("tissue_enriched", "group_enriched", "tissue_enhanced", "low_specificity"):
        print(f"  {c}: {class_counts.get(c, 0)}", file=sys.stderr)
    print("Other classes:", file=sys.stderr)
    for c, n in class_counts.items():
        if c not in ("tissue_enriched", "group_enriched", "tissue_enhanced", "low_specificity"):
            print(f"  {c}: {n}", file=sys.stderr)

    # QC: SLC34A2, SFTPC, B2M, ROS1
    print("\n=== QC ===", file=sys.stderr)
    for sym in ("SLC34A2", "SFTPC", "B2M", "ROS1"):
        p = OUT_DIR / f"{sym}.json"
        if not p.exists():
            print(f"{sym}: MISSING", file=sys.stderr)
            continue
        with p.open() as f:
            r = json.load(f)
        print(
            f"\n{sym}: class={r['enrichment_class']} "
            f"cl_ids={r['enrichment_cl_ids']} fold={r['fold_change']} "
            f"inf={r.get('fold_change_infinite')}",
            file=sys.stderr,
        )
        for c in r["top_cell_types"][:3]:
            print(
                f"  {c['cell_type']} ({c['cl_id']}): "
                f"mean={c['mean_log1p_cp10k']} "
                f"n_exp={c['n_expressing']}/{c['n_total']} "
                f"pct={c['pct_expressing']} rare={c['is_rare']}",
                file=sys.stderr,
            )

    # Rare examples
    print("\n=== Rare high-expressor examples (first 5) ===", file=sys.stderr)
    for g, lbl, m, n in rare_examples[:5]:
        print(f"  {g} -> {lbl} mean={m} n_total={n}", file=sys.stderr)

    # Print SLC34A2 full JSON
    print("\n=== SLC34A2 FULL JSON ===", file=sys.stderr)
    slc = OUT_DIR / "SLC34A2.json"
    if slc.exists():
        with slc.open() as f:
            print(json.dumps(json.load(f), indent=2), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
