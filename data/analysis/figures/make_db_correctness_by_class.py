# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``db_correctness_by_class.{pdf,png}`` from the public repo.

For 6 callers (5 DBs + Sonnet+NCBI), grouped bars showing
overall accuracy + per-verdict-bucket accuracy (yes / contextual /
no) on the 147-gene bench.

DB cutoffs are the **trade-off-audit optimized** versions (see
``scripts/triage_bench_db_barplot.py::_optimized_uniprot_accs`` /
``_optimized_cspa_accs`` and the ``db_cutoff_tradeoff`` figure):

  * **UniProt — TM+signal**: admit any accession with a transmembrane
    domain, a signal peptide, OR a strict surface subcellular term
    (looser than canonical; rescues more bench positives without
    hurting the no-class).
  * **CSPA — HC-only**: admit only the high-confidence flag (drops
    ``putative`` + ``unspecific`` rows; stricter than canonical, lifts
    precision against the no-class).
  * **GO CC / HPA / SURFY**: canonical baselines (audit didn't surface
    a better cutoff).

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available + whitegrid + despine +
transparent facecolor at 300 DPI). The styling block is inlined so the
gist runs standalone without depending on the project's plotting module.

Standalone — ``uv run make_db_correctness_by_class.py``.
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

# Published reproduction gist (embedded into the output PNG's Source
# tEXt chunk + PDF's Subject info field — same pattern as the canonical
# save_figure helper in src/accessible_surfaceome/audit/_plotting_config.py
# so the figure carries its source URL even when dragged into a Substack
# draft or copied to Slack). Read back with `exiftool figure.png | grep Source`,
# or in Python: `from PIL import Image; Image.open(p).info["Source"]`.
GIST_URL = "https://gist.github.com/beccajcarlson/2bb4f7aac629535982c142bc2032e04d"

# Single per-figure TSV: one row per (gene × model × prompt_variant ×
# replicate) with everything denormalized in (ground_truth_verdict,
# uniprot_acc, 5 per-DB *_surface_flag columns, uniprot_optimized,
# cspa_optimized, predicted_verdict, is_match). Produced by
# scripts/build_figure_tsvs.py. Gist bundles this TSV next to the
# script; the figure reads ONLY from the sibling — no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/db_correctness_by_class.tsv"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_gists_styling.py.
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
    """Register Manrope (and Playfair) from the repo's ``assets/fonts/``
    when running inside a checkout. External readers without the repo
    fall back to the next entry in ``font.sans-serif`` — typically
    DejaVu Sans — without erroring."""
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",  # repo checkout
        Path.cwd() / "assets" / "fonts",                            # cwd run
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001 — best-effort
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style` — kept self-contained
    so the gist runs without the in-repo plotting module. Sentinel:
    brand-style-v3.
    v2: bumped sizes ~25% + explicit medium weight (avoids ExtraLight default
    that matplotlib picks from the Manrope variable file). Companion to the
    static Manrope-{regular,medium,semibold,bold}.otf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 20,
        "axes.labelsize": 20,
        "axes.labelweight": "medium",
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
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 20,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
DB_PALETTE = {
    "UniProt":         BRAND_PALETTE[0],  # maroon-light
    "GO CC":           BRAND_PALETTE[1],  # teal-mid
    "HPA":             BRAND_PALETTE[2],  # amber-bright
    "SURFY":           BRAND_PALETTE[3],  # lavender-bright
    "CSPA":            BRAND_PALETTE[4],  # maroon-dark
    "Sonnet (+ IDs)": BRAND_CLAUDE_ORANGE,
}
COLUMNS = ["overall", "yes", "contextual", "no"]
COLUMN_LABEL = {
    "overall":    "overall\n(all 147 proteins)",
    "yes":        "yes",
    "contextual": "contextual\n(yes-vote = correct)",
    "no":         "no",
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
    if url.startswith(BASE + "/"):
        local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
        if local.is_file():
            return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local. "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def _vote_correct(vote: str, truth: str) -> bool:
    if vote == truth:
        return True
    return vote in ("yes", "contextual") and truth in ("yes", "contextual")


def main() -> None:
    # Single bundled per-rep TSV with everything denormalized:
    #   - per-gene truth + uniprot_acc
    #   - 5 per-DB *_surface_flag columns (uniprot/go/surfy/cspa/hpa)
    #   - uniprot_optimized + cspa_optimized recalibrated flags
    #   - per-cell sonnet predicted_verdict + per-rep is_match
    data = _fetch_tsv(DATA_TSV)

    # Derive per-gene tables by groupby(first) — the per-DB flags +
    # truth + acc are identical across reps of the same gene, so any
    # row works as a representative.
    gene_first = data.groupby("gene_symbol", sort=False).first()
    truth_by_gene = gene_first["ground_truth_verdict"].to_dict()
    acc_by_gene   = gene_first["uniprot_acc"].to_dict()

    # Per-gene per-DB flag lookup (deterministic across all (model,
    # variant, rep) rows of the same gene).
    db_flags = gene_first[[
        "uniprot_optimized", "cspa_optimized",
        "go_surface_flag", "hpa_surface_flag", "surfy_surface_flag",
    ]]

    def _vote(gene: str, source: str) -> str:
        if gene not in db_flags.index:
            return "no"
        row = db_flags.loc[gene]
        if source == "UniProt":
            return "yes" if row["uniprot_optimized"] == 1 else "no"
        if source == "CSPA":
            return "yes" if row["cspa_optimized"] == 1 else "no"
        flag_col = {
            "GO CC":  "go_surface_flag",
            "HPA":    "hpa_surface_flag",
            "SURFY":  "surfy_surface_flag",
        }[source]
        return "yes" if row[flag_col] == 1 else "no"

    # Display order: LLM cell first, then DBs sorted by overall accuracy
    # (descending) — matches the canonical generator's convention so the
    # strongest source sits next to the LLM bar.
    # Sonnet/ncbi per-cell predicted_verdict: take the first row per gene
    # (predicted_verdict is per-cell so identical across that cell's reps).
    sonnet_ncbi = (
        data[(data["model"] == "claude-sonnet-4-6") & (data["prompt_variant"] == "ncbi")]
        .groupby("gene_symbol", sort=False)["predicted_verdict"].first().to_dict()
    )
    sonnet_label = "Sonnet (+ IDs)"

    def _overall_acc(caller_label: str) -> float:
        if caller_label == sonnet_label:
            def vote_fn(g):
                return sonnet_ncbi.get(g) or "no"
        else:
            def vote_fn(g, lbl=caller_label):
                return _vote(g, lbl)
        genes = list(truth_by_gene)
        n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
        return n_correct / len(genes)

    db_labels_sorted = sorted(DB_LABELS, key=lambda lbl: -_overall_acc(lbl))
    callers_in_plot = [sonnet_label, *db_labels_sorted]

    # Sonnet per-bucket MEAN-of-replicate fraction — the Sonnet bar height in
    # each bucket is the mean across the 3 replicates (not the majority-vote
    # fraction), so the bar lines up with the overlaid points + SEM. DB callers
    # are deterministic and keep their exact majority fraction.
    sonnet_rep_frac: dict[str, float] = {}
    try:
        _s = data[(data["model"] == "claude-sonnet-4-6")
                   & (data["prompt_variant"] == "ncbi")].copy()
        _s["is_match"] = _s["is_match"].astype(int)
        _s["truth"] = _s["gene_symbol"].map(truth_by_gene)
        _rep_ids = sorted(_s["replicate"].unique())
        for bucket in COLUMNS:
            sub = _s if bucket == "overall" else _s[_s["truth"] == bucket]
            per_rep = [sub[sub["replicate"] == rid]["is_match"].mean()
                       for rid in _rep_ids if len(sub[sub["replicate"] == rid])]
            if per_rep:
                sonnet_rep_frac[bucket] = sum(per_rep) / len(per_rep)
    except Exception:  # noqa: BLE001
        sonnet_rep_frac = {}

    rows = []
    for caller_label in callers_in_plot:
        if caller_label == sonnet_label:
            def vote_fn(g):
                return sonnet_ncbi.get(g) or "no"
        else:
            def vote_fn(g, lbl=caller_label):
                return _vote(g, lbl)
        for bucket in COLUMNS:
            genes = (
                list(truth_by_gene)
                if bucket == "overall"
                else [g for g, t in truth_by_gene.items() if t == bucket]
            )
            if not genes:
                continue
            n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
            frac = n_correct / len(genes)
            # Sonnet bar = mean-of-reps fraction (when available).
            if caller_label == sonnet_label and bucket in sonnet_rep_frac:
                frac = sonnet_rep_frac[bucket]
            rows.append({
                "caller": caller_label,
                "bucket": bucket,
                "bucket_label": COLUMN_LABEL[bucket],
                "n_correct": n_correct,
                "n_total": len(genes),
                "fraction": frac,
            })
    df = pd.DataFrame(rows)

    _apply_brand_style()
    overall = {row["caller"]: row["fraction"]
               for row in rows if row["bucket"] == "overall"}
    totals = {row["bucket"]: row["n_total"]
              for row in rows if row["caller"] == sonnet_label and row["bucket"] != "overall"}

    fig, ax = plt.subplots(figsize=(11, 5.5))
    palette = [DB_PALETTE[c] for c in callers_in_plot]
    sns.barplot(
        data=df,
        x="bucket_label", y="fraction",
        hue="caller",
        order=[COLUMN_LABEL[c] for c in COLUMNS],
        hue_order=callers_in_plot,
        palette=palette,
        edgecolor="none", saturation=1.0,
        ax=ax,
    )

    # Insert a small visible gap between the single LLM bar and the
    # 5-DB cluster within each column group. Mirrors the canonical
    # generator's layout (scripts/triage_bench_db_barplot.py).
    n_col = len(COLUMNS)
    n_callers = len(callers_in_plot)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.6
    for caller_idx in range(1, n_callers):
        for j in range(n_col):
            patch = ax.patches[caller_idx * n_col + j]
            patch.set_x(patch.get_x() + gap)

    # Per-bar percentage annotations.
    for i, caller in enumerate(callers_in_plot):
        for j, bucket in enumerate(COLUMNS):
            patch = ax.patches[i * n_col + j]
            frac = df[(df["caller"] == caller) & (df["bucket"] == bucket)].iloc[0]["fraction"]
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + 0.01,
                f"{frac:.0%}",
                ha="center", va="bottom",
                fontsize=11, color=BRAND_INK,
            )

    # Overlay individual-replicate accuracy + SEM on the Sonnet bars (caller
    # index 0, one patch per bucket). DB callers are deterministic — no
    # overlay. Per-bucket per-rep accuracy from the replicates TSV.
    try:
        srep = data[(data["model"] == "claude-sonnet-4-6")
                    & (data["prompt_variant"] == "ncbi")].copy()
        srep["is_match"] = srep["is_match"].astype(int)
        srep["truth"] = srep["gene_symbol"].map(truth_by_gene)
        rep_ids = sorted(srep["replicate"].unique())
        for j, bucket in enumerate(COLUMNS):
            patch = ax.patches[0 * n_col + j]  # Sonnet caller, this bucket
            xc = patch.get_x() + patch.get_width() / 2
            sub = srep if bucket == "overall" else srep[srep["truth"] == bucket]
            accs = []
            for rid in rep_ids:
                cell = sub[sub["replicate"] == rid]
                if len(cell):
                    accs.append(cell["is_match"].mean())
            if len(accs) >= 2:
                m = sum(accs) / len(accs)
                sd = (sum((v - m) ** 2 for v in accs) / (len(accs) - 1)) ** 0.5
                sem = sd / (len(accs) ** 0.5)
                ax.errorbar(xc, m, yerr=sem, fmt="none", ecolor=BRAND_INK,
                            elinewidth=1.0, capsize=2.5, capthick=1.0, zorder=5)
                for k, av in enumerate(accs):
                    jitter = (k - (len(accs) - 1) / 2) * (patch.get_width() * 0.22)
                    ax.scatter(xc + jitter, av, s=14, color=BRAND_INK,
                               edgecolor="white", linewidth=0.4, zorder=6, alpha=0.9)
    except Exception:  # noqa: BLE001
        pass  # best-effort overlay

    ax.set_xlabel("")
    ax.set_ylabel("Fraction correctly\nclassified")
    ax.set_ylim(0, 1.14)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl}  ({overall[lbl]:.0%})" for lbl in callers_in_plot]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall acc.)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )

    # n-per-class subtitle. Pushed below the x-tick labels (which are
    # multi-line for the "overall" + "contextual" columns) so the subtitle
    # doesn't collide with the "(all 147 proteins)" / "(yes-vote = correct)"
    # second lines.
    subtitle_parts = [f"n(overall) = {sum(totals.values())}"]
    subtitle_parts += [f"n({v}) = {totals[v]}" for v in ["yes", "contextual", "no"]]
    ax.text(
        0.5, -0.34, "  ·  ".join(subtitle_parts),
        transform=ax.transAxes, ha="center", va="top",
        fontsize=13, color=BRAND_NEUTRAL,
    )
    sns.despine(ax=ax, top=True, right=True)

    out_pdf = Path("db_correctness_by_class.pdf")
    out_png = Path("db_correctness_by_class.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    n_uniprot_opt = int(db_flags["uniprot_optimized"].sum())
    n_cspa_opt    = int(db_flags["cspa_optimized"].sum())
    print(f"Wrote {out_pdf} + {out_png}  ({len(df)} (caller, bucket) cells; "
          f"UniProt TM+signal n={n_uniprot_opt:,}, CSPA HC-only n={n_cspa_opt:,})")


if __name__ == "__main__":
    main()
