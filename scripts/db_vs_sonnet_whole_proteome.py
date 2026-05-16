"""DB ↔ Sonnet agreement on the whole proteome under bench-optimized cutoffs.

Whole-genome analog of the 147-gene-bench `db_correctness_by_class`
figure. The bench has hand-curated ground truth; on the whole proteome
it doesn't exist, so we use **Sonnet (+ NCBI)'s triage verdict as the
reference** and ask: for each surface DB (under its bench-optimized
cutoff) and each ≥k-DB ensemble, what fraction of genes does it agree
with Sonnet on, split by Sonnet's verdict bucket.

Soft-credit rule (same as the bench plot): a DB "yes" matches Sonnet
"yes" *or* Sonnet "contextual"; a DB "no" matches Sonnet "no" only.

Buckets:
  * overall    — across all genes with a rated Sonnet verdict
  * yes        — only Sonnet-yes genes (sensitivity-like)
  * contextual — only Sonnet-contextual genes (DB must vote yes for match)
  * no         — only Sonnet-no genes (specificity-like)

Sonnet is the reference and does not appear as a bar — it would be 100%
by construction.

# Reproduction:
#   Public gist (reader-side standalone, PEP 723 deps):
#   https://gist.github.com/beccajcarlson/1265c867a3bbb08efd81262789e1f013
#   Reader-side mirror script:
#   data/analysis/figures/make_db_vs_sonnet_whole_proteome.py.

Run:
    uv run python scripts/db_vs_sonnet_whole_proteome.py
"""
from __future__ import annotations

from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
CAND_TSV = ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
OPT_CUTOFFS_TSV = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
OUT_DIR = ROOT / "data/analysis/figures"  # promoted to canonical figures dir

DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
ENSEMBLE_KS = [1, 2, 3, 4, 5]

DB_PALETTE = {label: CATEGORICAL_PALETTE[i] for i, label in enumerate(DB_LABELS)}

# Sequential teal ramp for the ≥k ensembles (light → dark = strict → permissive).
ENSEMBLE_PALETTE = {
    1: "#7AAB9F",  # teal-light  (≥1 = permissive union)
    2: "#4D8A80",
    3: "#3D6B60",
    4: "#244840",
    5: "#152E28",  # teal-deep   (≥5 = strict intersection)
}

BUCKETS = ["overall", "yes", "contextual", "no"]
BUCKET_LABEL = {
    "overall":    "overall",
    "yes":        "Sonnet = yes",
    "contextual": "Sonnet = contextual\n(yes-vote = match)",
    "no":         "Sonnet = no\n(no-vote = match)",
}


def _vote_match(db_vote: str, sonnet: str) -> bool:
    """DB calls yes/no; Sonnet calls yes/contextual/no. Soft credit on positive side."""
    if db_vote == sonnet:
        return True
    return db_vote in ("yes", "contextual") and sonnet in ("yes", "contextual")


def main() -> None:
    print(f"Fetching {CATALOG_URL} ...")
    r = httpx.get(CATALOG_URL, timeout=60.0)
    r.raise_for_status()
    body = r.json()
    catalog_rows = body["rows"]
    models = body.get("models") or []
    # Catalog ``row_schema=3``: each row carries ``tr: [variant_0, ..., variant_N]``
    # where each variant is ``[verdict, reason]`` or None. The figure uses
    # the canonical Sonnet (+ NCBI) variant — resolve its index from the
    # ``models`` array. Falls back to index 1 (historic default).
    sonnet_idx = next(
        (i for i, m in enumerate(models) if "sonnet" in (m or "").lower()),
        1,
    )
    print(f"  fetched {len(catalog_rows):,} catalog rows; "
          f"sonnet variant = {models[sonnet_idx] if sonnet_idx < len(models) else '?'} (idx {sonnet_idx})")

    cand = pd.read_csv(CAND_TSV, sep="\t").set_index("uniprot_accession")
    opt = pd.read_csv(OPT_CUTOFFS_TSV, sep="\t")
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt = set(opt.loc[opt["cspa_optimized"] == 1, "accession"].astype(str))

    def db_votes(acc: str) -> dict[str, bool]:
        """Per-protein dict {DB_LABEL → bool} under OPTIMIZED cutoffs."""
        out = {label: False for label in DB_LABELS}
        if not acc:
            return out
        out["UniProt"] = acc in uniprot_opt
        out["CSPA"] = acc in cspa_opt
        if acc in cand.index:
            row = cand.loc[acc]
            out["GO CC"] = row["go_surface_flag"] == 1
            out["HPA"] = row["hpa_surface_flag"] == 1
            out["SURFY"] = row["surfy_surface_flag"] == 1
        return out

    # Build per-gene table: symbol, acc, Sonnet verdict, per-DB vote bools
    records = []
    for row in catalog_rows:
        tr = row.get("tr") or []
        entry = tr[sonnet_idx] if 0 <= sonnet_idx < len(tr) else None
        v = entry[0] if entry and isinstance(entry, list) and entry else None
        if v not in ("yes", "contextual", "no"):
            continue
        acc = row.get("uniprot") or ""
        rec = {"symbol": row.get("symbol", ""), "acc": acc, "sonnet": v}
        rec.update(db_votes(acc))
        records.append(rec)

    df = pd.DataFrame(records)
    print(f"\nGenes with a rated Sonnet verdict: {len(df):,}")
    counts = df["sonnet"].value_counts()
    for v in ("yes", "contextual", "no"):
        print(f"  Sonnet = {v:11s}  {counts.get(v, 0):>6,}")

    # First compute overall agreement per single DB so we can sort them.
    def _db_overall(label: str) -> float:
        n_match = sum(_vote_match("yes" if row[label] else "no", row["sonnet"])
                      for _, row in df.iterrows())
        return n_match / len(df)

    db_overall_acc = {label: _db_overall(label) for label in DB_LABELS}
    db_sorted = sorted(DB_LABELS, key=lambda d: -db_overall_acc[d])

    # Build caller list: ensembles first (color by k), then individual DBs sorted desc.
    callers: list[tuple[str, str]] = []
    for k in ENSEMBLE_KS:
        callers.append((f"≥{k} DB", "ensemble"))
    for label in db_sorted:
        callers.append((label, "single"))

    def caller_vote(caller: str, kind: str, row: pd.Series) -> str:
        if kind == "single":
            return "yes" if row[caller] else "no"
        # ensemble: ≥k DBs vote yes
        k = int(caller.lstrip("≥").rstrip(" DB"))
        return "yes" if sum(bool(row[d]) for d in DB_LABELS) >= k else "no"

    # Compute agreement rates per (caller, bucket).
    rows_long: list[dict] = []
    overall_acc: dict[str, float] = {}
    for caller_label, kind in callers:
        for bucket in BUCKETS:
            sub = df if bucket == "overall" else df[df["sonnet"] == bucket]
            if sub.empty:
                continue
            n_match = sum(
                _vote_match(caller_vote(caller_label, kind, r), r["sonnet"])
                for _, r in sub.iterrows()
            )
            frac = n_match / len(sub)
            if bucket == "overall":
                overall_acc[caller_label] = frac
            rows_long.append({
                "caller": caller_label,
                "bucket": bucket,
                "bucket_label": BUCKET_LABEL[bucket],
                "fraction": frac,
                "n_total": len(sub),
            })

    plot_df = pd.DataFrame(rows_long)

    print("\nOverall agreement with Sonnet (across whole proteome):")
    for caller_label, _ in callers:
        print(f"  {caller_label:10s}  {overall_acc[caller_label]*100:5.1f}%")

    # ─── Figure ───
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)

    caller_order = [c[0] for c in callers]
    palette = [
        (ENSEMBLE_PALETTE[int(c[0].lstrip("≥").rstrip(" DB"))] if c[1] == "ensemble"
         else DB_PALETTE[c[0]])
        for c in callers
    ]

    fig, ax = plt.subplots(figsize=(17, 6.5))
    sns.barplot(
        data=plot_df,
        x="bucket_label", y="fraction",
        hue="caller",
        order=[BUCKET_LABEL[b] for b in BUCKETS],
        hue_order=caller_order,
        palette=palette,
        edgecolor="none", saturation=1.0,
        width=0.92,  # wider bars (default ≈0.8) so % labels above don't overlap
        ax=ax,
    )

    # Insert a gap between the ensemble group and the individual-DB group, per bucket.
    n_callers = len(caller_order)
    n_buckets = len(BUCKETS)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.4
    for caller_idx in range(n_callers):
        # 0..4 = ensembles (no shift); 5..9 = individual DBs (shift +gap)
        shift = gap if caller_idx >= 5 else 0
        for j in range(n_buckets):
            patch = ax.patches[caller_idx * n_buckets + j]
            patch.set_x(patch.get_x() + shift)

    # Per-bar pct annotation.
    for i, caller_label in enumerate(caller_order):
        for j, bucket in enumerate(BUCKETS):
            patch = ax.patches[i * n_buckets + j]
            cell = plot_df[(plot_df["caller"] == caller_label) & (plot_df["bucket"] == bucket)]
            if cell.empty:
                continue
            frac = cell.iloc[0]["fraction"]
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + 0.01,
                f"{frac:.0%}",
                ha="center", va="bottom",
                fontsize=8, color=COLORS["dark"],
            )

    ax.set_xlabel("")
    ax.set_ylabel("Fraction agreeing with Sonnet (+ NCBI) verdict")
    ax.set_ylim(0, 1.14)

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl}  ({overall_acc[lbl]:.0%})" for lbl in caller_order]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall agreement)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=10,
    )

    # Subtitle with per-bucket sample sizes.
    totals = {
        row["bucket"]: row["n_total"]
        for _, row in plot_df.iterrows()
        if row["caller"] == caller_order[0]
    }
    subtitle = (
        f"n(overall) = {totals.get('overall', 0):,}  ·  "
        f"n(yes) = {totals.get('yes', 0):,}  ·  "
        f"n(contextual) = {totals.get('contextual', 0):,}  "
        f"(whole protein-coding proteome with a rated Sonnet verdict)"
    )
    ax.text(
        0.5, -0.18, subtitle,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=11, color=COLORS["neutral"],
    )

    sns.despine(ax=ax, top=True, right=True)

    save_figure(
        fig, filename="db_vs_sonnet_whole_proteome",
        output_dir=str(OUT_DIR), formats=["pdf", "png"],
        gist_url="https://gist.github.com/beccajcarlson/1265c867a3bbb08efd81262789e1f013",
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
