# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``db_vs_sonnet_whole_proteome.{pdf,png}`` from the public repo.

Whole-genome DB ↔ Sonnet agreement plot. The 147-gene bench has hand-
curated ground truth; on the whole proteome it doesn't exist, so we use
the Sonnet (+ NCBI) triage verdict as the **reference** and ask how
often each surface DB (under its bench-optimized cutoff) and each
≥k-DB ensemble agrees with Sonnet, split by Sonnet's verdict bucket.

Soft-credit rule (same as the bench plot): DB "yes" matches Sonnet
"yes" or "contextual"; DB "no" matches Sonnet "no" only.

Four buckets per caller:
* **overall** — across all genes with a rated Sonnet verdict
* **Sonnet = yes** — sensitivity-like
* **Sonnet = contextual** — DB must yes-vote for a match
* **Sonnet = no** — specificity-like

10 callers: 5 ensembles (≥1..≥5 of the 5 surface DBs vote yes, teal
ramp) + 5 individual DBs under their optimized cutoffs (sorted desc by
overall agreement). Sonnet is the reference and does not appear as a
bar (would be 100% by construction).

Visual styling matches the in-repo ``_plotting_config`` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Data: catalog fetched live from
``https://api.deliverome.org/surfaceome/v1/catalog`` (~19,324 genes
with per-gene Sonnet+NCBI verdict); per-DB votes from
candidate_universe.tsv + db_optimized_cutoffs.tsv via
raw.githubusercontent.com.

Standalone — ``uv run make_db_vs_sonnet_whole_proteome.py``.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"
CAND_TSV = f"{BASE}/data/processed/candidate_universe/candidate_universe.tsv"
OPT_CUTOFFS_TSV = f"{BASE}/data/processed/triage_bench/db_optimized_cutoffs.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/1265c867a3bbb08efd81262789e1f013"

# ──── Inline brand styling — sentinel: brand-style-v1 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained. Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_CLAUDE_ORANGE = "#d87851"
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for ttf in sorted(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(ttf))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v1."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.size": 17,
        "axes.labelsize": 19,
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 16,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
ENSEMBLE_KS = [1, 2, 3, 4, 5]
DB_PALETTE = {label: BRAND_PALETTE[i] for i, label in enumerate(DB_LABELS)}
# Sequential teal ramp for the ≥k ensembles (light → dark = permissive → strict).
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


def _fetch_tsv(url: str) -> pd.DataFrame:
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def _vote_match(db_vote: str, sonnet: str) -> bool:
    """DB calls yes/no; Sonnet calls yes/contextual/no. Soft credit on positive side."""
    if db_vote == sonnet:
        return True
    return db_vote in ("yes", "contextual") and sonnet in ("yes", "contextual")


def main() -> None:
    _apply_brand_style()

    print(f"Fetching {CATALOG_URL} ...")
    r = httpx.get(CATALOG_URL, timeout=60)
    r.raise_for_status()
    catalog_rows = r.json()["rows"]
    print(f"  fetched {len(catalog_rows):,} catalog rows")

    cand = _fetch_tsv(CAND_TSV).set_index("uniprot_accession")
    opt = _fetch_tsv(OPT_CUTOFFS_TSV)
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt = set(opt.loc[opt["cspa_optimized"] == 1, "accession"].astype(str))

    def db_votes(acc: str) -> dict[str, bool]:
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

    records = []
    for row in catalog_rows:
        t = row.get("triage") or {}
        v = t.get("verdict")
        if v not in ("yes", "contextual", "no"):
            continue
        acc = row.get("uniprot") or ""
        rec = {"symbol": row.get("symbol", ""), "acc": acc, "sonnet": v}
        rec.update(db_votes(acc))
        records.append(rec)

    df = pd.DataFrame(records)
    print(f"\nGenes with a rated Sonnet verdict: {len(df):,}")
    print(df["sonnet"].value_counts())

    # Sort individual DBs by overall agreement.
    def _db_overall(label: str) -> float:
        n_match = sum(_vote_match("yes" if row[label] else "no", row["sonnet"])
                      for _, row in df.iterrows())
        return n_match / len(df)

    db_overall_acc = {label: _db_overall(label) for label in DB_LABELS}
    db_sorted = sorted(DB_LABELS, key=lambda d: -db_overall_acc[d])

    callers: list[tuple[str, str]] = []
    for k in ENSEMBLE_KS:
        callers.append((f"≥{k} DB", "ensemble"))
    for label in db_sorted:
        callers.append((label, "single"))

    def caller_vote(caller: str, kind: str, row: pd.Series) -> str:
        if kind == "single":
            return "yes" if row[caller] else "no"
        k = int(caller.lstrip("≥").rstrip(" DB"))
        return "yes" if sum(bool(row[d]) for d in DB_LABELS) >= k else "no"

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
        width=0.92,
        ax=ax,
    )

    n_callers = len(caller_order)
    n_buckets = len(BUCKETS)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.4
    for caller_idx in range(n_callers):
        shift = gap if caller_idx >= 5 else 0
        for j in range(n_buckets):
            patch = ax.patches[caller_idx * n_buckets + j]
            patch.set_x(patch.get_x() + shift)

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
                fontsize=8, color=BRAND_INK,
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

    totals = {
        row["bucket"]: row["n_total"]
        for _, row in plot_df.iterrows()
        if row["caller"] == caller_order[0]
    }
    subtitle = (
        f"n(overall) = {totals.get('overall', 0):,}  ·  "
        f"n(yes) = {totals.get('yes', 0):,}  ·  "
        f"n(contextual) = {totals.get('contextual', 0):,}  ·  "
        f"n(no) = {totals.get('no', 0):,}  "
        f"(whole protein-coding proteome with a rated Sonnet verdict)"
    )
    ax.text(
        0.5, -0.18, subtitle,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=11, color=BRAND_NEUTRAL,
    )
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    out_pdf = Path("db_vs_sonnet_whole_proteome.pdf")
    out_png = Path("db_vs_sonnet_whole_proteome.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
