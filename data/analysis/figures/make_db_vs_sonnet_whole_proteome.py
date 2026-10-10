# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``db_vs_sonnet_whole_proteome.{pdf,png}`` from the public repo.

Whole-genome DB ↔ Sonnet agreement plot. The 147-gene bench has hand-
curated ground truth; on the whole proteome it doesn't exist, so we use
the production two-tier Sonnet triage verdict as the **reference**: an
NCBI first pass, with 379 genes upgraded from "no" to "yes"/"contextual"
by the PubMed second-pass rescue (``verdict_source == "pubmed_rescue"``
in the TSV). We ask how often each surface DB (under its bench-optimized
cutoff) and each k+-DB ensemble agrees with Sonnet, split by Sonnet's
verdict bucket.

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

Data: a single TSV, db_vs_sonnet_whole_proteome.tsv (19,324
protein-coding genes, one row each: five per-DB surface flags, the
optimized UniProt/CSPA flags, and the Sonnet verdict), read from next
to this script (gist case) or from the in-repo
data/processed/figures/db_vs_sonnet_whole_proteome.tsv (dev case). It
is built by scripts/build_figure_tsvs.py from whole_proteome_catalog.tsv
and db_optimized_cutoffs.tsv. The gist's HEAD commit SHA is the SWHID
for the whole reproduction unit (script + data + README).

Standalone — ``uv run make_db_vs_sonnet_whole_proteome.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Single per-figure TSV: full proteome catalog (~19k rows) with
# uniprot_optimized + cspa_optimized recalibrated flags denormalized
# in alongside the 5 per-DB flags + sonnet_verdict. Produced by
# scripts/build_figure_tsvs.py. Gist bundles this TSV next to the
# script; the figure reads only from the sibling — no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/db_vs_sonnet_whole_proteome.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/1265c867a3bbb08efd81262789e1f013"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
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
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3.
    v2: bumped sizes ~25% + explicit medium weight (avoids ExtraLight default
    that matplotlib picks from the Manrope variable file). Companion to the
    static Manrope-{Regular,Medium,SemiBold,Bold}.ttf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": ["Manrope", "DejaVu Sans"],
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "semibold",
        "font.size": 16,
        "axes.labelsize": 18,
        "axes.labelweight": "semibold",
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
# Grey ramp for the k+ ensembles, light → dark as more databases must agree
# (permissive union → strict intersection). Neutral so the ensembles can't be
# mistaken for any single database's brand colour; shared by S5 and S6.
ENSEMBLE_PALETTE = {
    1: "#CFCFCF",  # 1+ DB: the union
    2: "#A7A7A7",
    3: "#7E7E7E",
    4: "#565656",
    5: "#2E2E2E",  # 5+ DB: the strict intersection
}

BUCKETS = ["overall", "yes", "contextual", "no"]
BUCKET_LABEL = {
    "overall":    "overall",
    "yes":        "Sonnet = yes",
    "contextual": "Sonnet = contextual\n(yes-vote = match)",
    "no":         "Sonnet = no\n(no-vote = match)",
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def _vote_match(db_vote: str, sonnet: str) -> bool:
    """DB calls yes/no; Sonnet calls yes/contextual/no. Soft credit on positive side."""
    if db_vote == sonnet:
        return True
    return db_vote in ("yes", "contextual") and sonnet in ("yes", "contextual")


def main() -> None:
    _apply_brand_style()

    # Single bundled TSV: one row per protein-coding gene with the
    # ``*_surface_flag`` columns, the production Sonnet verdict, and
    # uniprot_optimized + cspa_optimized denormalized in. The
    # set-construction below derives the uniprot_opt / cspa_opt accession
    # sets from those row-level flags.
    catalog = _fetch_tsv(DATA_TSV)
    print(f"  loaded {len(catalog):,} catalog rows; sonnet = claude-sonnet-4-6")

    uniprot_opt = set(catalog.loc[catalog["uniprot_optimized"] == 1, "uniprot_acc"].astype(str))
    cspa_opt    = set(catalog.loc[catalog["cspa_optimized"]    == 1, "uniprot_acc"].astype(str))

    records = []
    for row in catalog.itertuples(index=False):
        v = (str(getattr(row, "sonnet_verdict", "") or "")).strip()
        if v not in ("yes", "contextual", "no"):
            continue
        acc = str(getattr(row, "uniprot_acc", "") or "")
        rec = {
            "symbol": str(getattr(row, "hgnc_symbol", "") or ""),
            "acc": acc,
            "sonnet": v,
            "UniProt": acc in uniprot_opt,
            "CSPA": acc in cspa_opt,
            "GO CC": int(getattr(row, "go_surface_flag", 0) or 0) == 1,
            "HPA": int(getattr(row, "hpa_surface_flag", 0) or 0) == 1,
            "SURFY": int(getattr(row, "surfy_surface_flag", 0) or 0) == 1,
        }
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

    # Ensembles are labelled "k+ DB" (k or more DBs vote yes), matching the
    # canonical generator.
    callers: list[tuple[str, str]] = []
    for k in ENSEMBLE_KS:
        callers.append((f"{k}+ DB", "ensemble"))
    for label in db_sorted:
        callers.append((label, "single"))

    def caller_vote(caller: str, kind: str, row: pd.Series) -> str:
        if kind == "single":
            return "yes" if row[caller] else "no"
        k = int(caller.split("+")[0])
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
        (ENSEMBLE_PALETTE[int(c[0].split("+")[0])] if c[1] == "ensemble"
         else DB_PALETTE[c[0]])
        for c in callers
    ]

    # Wider figure (was 17) so the 10-bar clusters in the dense
    # "Sonnet = no" bucket — where 4 ensemble bars all sit at ~100% —
    # spread out enough for their bar-top % labels to read distinctly.
    fig, ax = plt.subplots(figsize=(14, 7))
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
                ha="center", va="bottom", rotation=90,
                fontsize=14, color=BRAND_INK,
            )

    ax.set_xlabel("")
    ax.set_ylabel("Fraction agreeing with\nSonnet triage verdict")
    ax.set_ylim(0, 1.22)  # headroom for the vertical bar-top % labels
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl} ({overall_acc[lbl]:.0%})" for lbl in caller_order]
    # Column-major fill: ensembles on the first row, single DBs on the second.
    order = [0, 5, 1, 6, 2, 7, 3, 8, 4, 9]
    handles, legend_labels = [handles[k] for k in order], [legend_labels[k] for k in order]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall agreement)", title_fontsize=18,
        loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=5,
        frameon=False, fontsize=16, columnspacing=1.6,
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
        fontsize=14, color=BRAND_NEUTRAL,
    )
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    out_pdf = Path("db_vs_sonnet_whole_proteome.pdf")
    out_png = Path("db_vs_sonnet_whole_proteome.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
