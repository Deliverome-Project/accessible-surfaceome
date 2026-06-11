"""Build v2.1 JSON for a SINGLE gene (default GPR75) so the new tissue
classification + lower-threshold common bucket can be inspected on
one page without re-streaming the full WMG file for 19k genes.

The full-cohort build will follow once the shape is validated by eye.
"""
from __future__ import annotations
import csv, gzip, json, math, os, sys, time
from collections import defaultdict

GENE_SYMBOL = os.environ.get("GENE_SYMBOL", "GPR75")
# GPR75 = ENSG00000119737. Override via env if running for a different gene.
ENSG_TARGET = os.environ.get("ENSG_TARGET", "ENSG00000119737")
HGNC_ID = os.environ.get("HGNC_ID", "HGNC:4526")

WMG = "/Users/rebeccacarlson/Git/tess/scripts/tool-validation/.cache/expression-summary-condensed-11-09-25.csv.gz"
TISSUE_COUNTS = "/tmp/czi_cell_tissue_counts.tsv"
UBERON_LABELS = "/tmp/uberon_to_label.tsv"
CL_LABELS = "/tmp/cl_id_to_label.tsv"

OUT_PATH = f"/tmp/czi_enrichment/{GENE_SYMBOL}.json"
CENSUS_VERSION = "2025-11-08"
SCHEMA_VERSION = "2.1"

# Filters / caps
MIN_N_TOTAL_CLASS = 50
MIN_N_EXPRESSING = 10
MIN_PCT = 0.01
COMMON_THRESHOLD = 10_000  # v2.1: was 1000
COMMON_TOP_N = 20
RARE_TOP_N = 10
RARE_MIN_MEAN = 2.0
TISSUE_MIN_TOTAL = 1_000


def load_labels():
    cl = {}
    with open(CL_LABELS) as f:
        r = csv.reader(f, delimiter="\t")
        next(r, None)
        for row in r:
            if len(row) >= 2:
                cl[row[0]] = row[1]
    ub = {}
    with open(UBERON_LABELS) as f:
        r = csv.reader(f, delimiter="\t")
        next(r, None)
        for row in r:
            if len(row) >= 2:
                ub[row[0]] = row[1]
    return cl, ub


def load_counts():
    # (cl_id, ub_id) -> n
    pair = {}
    cl_total = defaultdict(int)
    ub_total = defaultdict(int)
    with open(TISSUE_COUNTS) as f:
        r = csv.reader(f, delimiter="\t")
        next(r, None)
        for row in r:
            if len(row) < 3:
                continue
            cl_id, ub_id, n = row[0], row[1], int(row[2])
            pair[(cl_id, ub_id)] = n
            cl_total[cl_id] += n
            ub_total[ub_id] += n
    return pair, dict(cl_total), dict(ub_total)


def classify_hpa(items):
    """Items: list of dicts {id, mean (log1p), n_total, n_expressing, pct}.
    Returns (class, ids, fold)."""
    qualified = [
        x for x in items
        if x["n_total"] >= MIN_N_TOTAL_CLASS
        and x["n_expressing"] >= MIN_N_EXPRESSING
        and x["pct"] >= MIN_PCT
    ]
    if len(qualified) == 0:
        return "low_specificity", [], None
    qualified.sort(key=lambda x: -x["mean"])
    linear = [math.expm1(x["mean"]) for x in qualified]
    ids = [x["id"] for x in qualified]
    # tissue_enriched: top / 2nd >= 4
    if len(linear) >= 2 and linear[1] > 0 and linear[0] / linear[1] >= 4:
        return "tissue_enriched", [ids[0]], linear[0] / linear[1]
    # group_enriched: contiguous group of 2-5 where min(group) / next >= 4
    for size in range(5, 1, -1):  # try largest first
        if len(linear) > size and linear[size] > 0:
            if linear[size - 1] / linear[size] >= 4:
                return "group_enriched", ids[:size], linear[size - 1] / linear[size]
    # tissue_enhanced: top / mean(rest) >= 4
    rest = linear[1:]
    if rest:
        avg_rest = sum(rest) / len(rest)
        if avg_rest > 0 and linear[0] / avg_rest >= 4:
            return "tissue_enhanced", [ids[0]], linear[0] / avg_rest
    return "low_specificity", [], None


def main():
    cl_labels, ub_labels = load_labels()
    pair_counts, cl_totals, ub_totals = load_counts()

    # Stream WMG once, keep only target gene rows.
    # Structure: per (cl_id, ub_id) -> {nnz, sum}
    by_cl_ub = defaultdict(lambda: {"nnz": 0.0, "sum": 0.0})

    t0 = time.time()
    seen = 0
    kept = 0
    with gzip.open(WMG, "rt") as f:
        r = csv.reader(f)
        next(r)  # header
        for row in r:
            seen += 1
            if row[0] != ENSG_TARGET:
                continue
            kept += 1
            ub, cl = row[1], row[3]
            nnz = int(row[4])
            ssum = float(row[5])
            key = (cl, ub)
            d = by_cl_ub[key]
            d["nnz"] += nnz
            d["sum"] += ssum
            if seen % 5_000_000 == 0:
                print(f"  scanned {seen/1e6:.1f}M rows ({time.time()-t0:.0f}s) kept={kept}", flush=True)
    print(f"stream done: {seen} rows scanned, {kept} kept in {time.time()-t0:.0f}s")

    # Roll up per-cl_id and per-uberon_id
    by_cl = defaultdict(lambda: {"nnz": 0.0, "sum": 0.0, "tissues": []})
    by_ub = defaultdict(lambda: {"nnz": 0.0, "sum": 0.0})

    for (cl, ub), d in by_cl_ub.items():
        c = by_cl[cl]
        c["nnz"] += d["nnz"]
        c["sum"] += d["sum"]
        n_total_pair = pair_counts.get((cl, ub), 0)
        c["tissues"].append({
            "uberon_id": ub,
            "tissue": ub_labels.get(ub, ub),
            "n_expressing": int(d["nnz"]),
            "n_total": n_total_pair,
            "mean": (d["sum"] / d["nnz"]) if d["nnz"] else 0.0,
            "pct": min(1.0, d["nnz"] / n_total_pair) if n_total_pair else 0.0,
        })
        u = by_ub[ub]
        u["nnz"] += d["nnz"]
        u["sum"] += d["sum"]

    # Build per-cell-type rows
    cell_rows = []
    for cl, d in by_cl.items():
        n_tot_cl = cl_totals.get(cl, 0)
        nnz = d["nnz"]
        ssum = d["sum"]
        mean = (ssum / nnz) if nnz else 0.0
        pct = min(1.0, nnz / n_tot_cl) if n_tot_cl else 0.0
        # sort + cap tissues for this cell type
        tissues = sorted(d["tissues"], key=lambda t: -t["n_expressing"])[:3]
        cell_rows.append({
            "cl_id": cl,
            "cell_type": cl_labels.get(cl, cl),
            "mean_log1p_cp10k": round(mean, 4),
            "n_expressing": int(nnz),
            "n_total": int(n_tot_cl),
            "pct_expressing": round(pct, 4),
            "tissues": [{
                "tissue": t["tissue"],
                "uberon_id": t["uberon_id"],
                "mean_log1p_cp10k": round(t["mean"], 4),
                "n_expressing": int(t["n_expressing"]),
                "n_total": int(t["n_total"]),
                "pct_expressing": round(t["pct"], 4),
            } for t in tissues],
        })

    # Classify cell-type level
    cell_class_items = [{
        "id": r["cl_id"],
        "mean": r["mean_log1p_cp10k"],
        "n_total": r["n_total"],
        "n_expressing": r["n_expressing"],
        "pct": r["pct_expressing"],
    } for r in cell_rows]
    ct_class, ct_ids, ct_fold = classify_hpa(cell_class_items)
    print(f"cell_type_enrichment: class={ct_class} fold={ct_fold} ids={ct_ids[:3]}")

    # Build per-tissue rows
    tissue_rows = []
    for ub, d in by_ub.items():
        n_tot_ub = ub_totals.get(ub, 0)
        nnz = d["nnz"]
        mean = (d["sum"] / nnz) if nnz else 0.0
        pct = min(1.0, nnz / n_tot_ub) if n_tot_ub else 0.0
        tissue_rows.append({
            "tissue": ub_labels.get(ub, ub),
            "uberon_id": ub,
            "mean_log1p_cp10k": round(mean, 4),
            "n_expressing": int(nnz),
            "n_total": int(n_tot_ub),
            "pct_expressing": round(pct, 4),
        })

    tissue_class_items = [{
        "id": r["uberon_id"],
        "mean": r["mean_log1p_cp10k"],
        "n_total": r["n_total"],
        "n_expressing": r["n_expressing"],
        "pct": r["pct_expressing"],
    } for r in tissue_rows if r["n_total"] >= TISSUE_MIN_TOTAL]
    tis_class, tis_ids, tis_fold = classify_hpa(tissue_class_items)
    print(f"tissue_enrichment:    class={tis_class} fold={tis_fold} ids={tis_ids[:3]}")

    # Sort + cap top_cell_types: 20 common (n_total >= 10k) + 10 rare (rest, mean>=2)
    cell_rows_qualified = [r for r in cell_rows
                           if r["n_expressing"] >= MIN_N_EXPRESSING
                           and r["pct_expressing"] >= MIN_PCT]
    cell_rows_qualified.sort(key=lambda r: -r["mean_log1p_cp10k"])
    common = [r for r in cell_rows_qualified if r["n_total"] >= COMMON_THRESHOLD][:COMMON_TOP_N]
    rare = [r for r in cell_rows_qualified
            if r["n_total"] < COMMON_THRESHOLD and r["mean_log1p_cp10k"] >= RARE_MIN_MEAN][:RARE_TOP_N]
    for r in common: r["is_rare"] = False
    for r in rare: r["is_rare"] = True
    top_cell_types = common + rare

    # Sort + cap top_tissues. Include BOTH qualified and trace tissues
    # in one ranked list so the reader sees the long tail for low-
    # expression genes (GPR75 has only 4 qualified tissues but ~10
    # trace tissues that still carry signal — pleura/forelimb at high
    # mean but n_expressing < 10).
    #
    # is_trace = passes n_total >= TISSUE_MIN_TOTAL but fails the
    # MIN_N_EXPRESSING or MIN_PCT noise filter. Viewer renders trace
    # rows muted with a badge.
    eligible = [r for r in tissue_rows if r["n_total"] >= TISSUE_MIN_TOTAL]
    for r in eligible:
        r["is_trace"] = (
            r["n_expressing"] < MIN_N_EXPRESSING
            or r["pct_expressing"] < MIN_PCT
        )
    # Two-tier sort: qualified tissues first (by mean DESC), then
    # trace (by mean DESC). Otherwise a 4-cell pleura at mean 2.3
    # outranks a 20k-cell brain at mean 1.97 — wrong story for the
    # reader. Within each tier, mean ordering tells the magnitude
    # story.
    top_tissues = sorted(
        eligible,
        key=lambda r: (r["is_trace"], -r["mean_log1p_cp10k"]),
    )[:15]

    rec = {
        "schema_version": SCHEMA_VERSION,
        "census_version": CENSUS_VERSION,
        "gene_symbol": GENE_SYMBOL,
        "hgnc_id": HGNC_ID,
        "ensembl_gene": ENSG_TARGET,
        "cell_type_enrichment": {
            "class": ct_class,
            "cl_ids": ct_ids,
            "fold_change": round(ct_fold, 2) if ct_fold is not None else None,
        },
        "tissue_enrichment": {
            "class": tis_class,
            "uberon_ids": tis_ids,
            "tissue_labels": [ub_labels.get(u, u) for u in tis_ids],
            "fold_change": round(tis_fold, 2) if tis_fold is not None else None,
        },
        # Back-compat (mirrors cell-type enrichment for older viewer readers)
        "enrichment_class": ct_class,
        "enrichment_cl_ids": ct_ids,
        "fold_change": round(ct_fold, 2) if ct_fold is not None else None,
        "top_cell_types": top_cell_types,
        "top_tissues": top_tissues,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(rec, f, separators=(",", ":"))
    print(f"wrote {OUT_PATH}  top_cell_types={len(top_cell_types)} top_tissues={len(top_tissues)}")


if __name__ == "__main__":
    main()
