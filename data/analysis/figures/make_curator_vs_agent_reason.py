# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``curator_vs_agent_reason.{pdf,png}`` — the SurfaceBench
curator-vs-agent reason confusion matrix.

For each of the 147 SurfaceBench genes, plots the curator's
hand-assigned ``ground_truth_reason`` against the production
triage agent's ``predicted_reason`` (Sonnet 4.6 + NCBI context).
Both axes draw from the same closed 19-value ``TriageReason`` enum,
so the diagonal is exact-reason agreement; off-diagonal cells split
into within-bucket reassignments (same Yes/Contextual/No bucket,
different reason) and cross-bucket flips (the cells that matter
most for verdict accuracy).

The in-repo canonical figure at
``data/analysis/figures/curator_vs_agent_reason.pdf`` is a 3-panel
composite: (a) bucket-strict accuracy across 10 model variants,
(b) per-reason accuracy across 4 frontier configs, (c) the
confusion matrix this script renders. The full 3-panel composite
is produced by ``scripts/curator_vs_agent_reason.py`` in the
project repo; this gist mirror ships the confusion matrix alone
since that's the analytical core readers cite from Figure S4.

Standalone — ``uv run make_curator_vs_agent_reason.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per (gene × model × prompt_variant ×
# replicate) on the 147-gene bench, with ground_truth_reason +
# predicted_reason denormalized. Produced by
# scripts/build_figure_tsvs.py. Gist bundles this TSV next to the
# script; the figure reads only from the sibling — no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/curator_vs_agent_reason.tsv"

# Published reproduction gist (embedded into output PNG Source /
# PDF Subject metadata — mirrors save_figure in _plotting_config.py).
# Filled at gist-creation time; the placeholder stays harmless until then.
GIST_URL = "https://gist.github.com/beccajcarlson/c98fe6646ba8b967767d072657da31b7"

# Production-pipeline model + variant: Sonnet 4.6 with NCBI context.
PROD_MODEL = "claude-sonnet-4-6"
PROD_VARIANT = "ncbi"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"
BUCKET_COLOR = {"yes": "#2E7A55", "contextual": "#C07830", "no": "#6F5D5A"}
DIAGONAL_HIGHLIGHT = "#BC3C4C"


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
        "font.size": 14, "axes.labelsize": 16, "axes.titlesize": 0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-", "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False, "legend.fontsize": 12,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
    })


# Closed TriageReason enum — yes / contextual / no bucket order.
REASONS_ORDERED = [
    # YES
    "classical_surface_receptor", "multipass_with_exposed_loops",
    "gpi_anchored", "extracellular_face_protein", "stable_complex_partner",
    # CONTEXTUAL
    "stable_surface_attachment", "cell_state_induced",
    "tissue_restricted_surface", "lysosomal_exocytosis", "dual_localization",
    # NO
    "cytoplasmic", "nuclear", "mitochondrial_internal", "endomembrane_resident",
    "nuclear_envelope", "secreted_only", "inner_leaflet_anchored",
    "pmhc_only_intracellular", "other",
]
BUCKET = {r: "yes" for r in REASONS_ORDERED[:5]}
BUCKET.update({r: "contextual" for r in REASONS_ORDERED[5:10]})
BUCKET.update({r: "no" for r in REASONS_ORDERED[10:]})

LABEL_SHORT = {
    "classical_surface_receptor":   "classical\nsurf rcptr",
    "multipass_with_exposed_loops": "multipass\nexp loops",
    "gpi_anchored":                 "GPI\nanchored",
    "extracellular_face_protein":   "ECF\nprotein",
    "stable_complex_partner":       "stable cplx\npartner",
    "stable_surface_attachment":    "stable surf\nattachment",
    "cell_state_induced":           "cell-state\ninduced",
    "tissue_restricted_surface":    "tissue\nrestricted",
    "lysosomal_exocytosis":         "lysosomal\nexocytosis",
    "dual_localization":            "dual\nlocalization",
    "cytoplasmic":                  "cytoplasmic",
    "nuclear":                      "nuclear",
    "mitochondrial_internal":       "mito\ninternal",
    "endomembrane_resident":        "endomem\nresident",
    "nuclear_envelope":             "nuclear\nenvelope",
    "secreted_only":                "secreted\nonly",
    "inner_leaflet_anchored":       "inner leaflet\nanchored",
    "pmhc_only_intracellular":      "pMHC\nonly",
    "other":                        "other",
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


def _build_matrix(data: pd.DataFrame) -> tuple[np.ndarray, int, int, dict]:
    """(curator × agent) reason count matrix + which genes landed in
    each off-diagonal cell (for gene-name annotations on the figure)."""
    sub = data[(data["model"] == PROD_MODEL) & (data["prompt_variant"] == PROD_VARIANT)]
    # Match mainbench_canonical_v2's collapse rule (see
    # scripts/export_mainbench_to_tsv.py:_collapse_to_majority): pick
    # the majority predicted_verdict across replicates, then take the
    # representative_reason from the FIRST replicate within that
    # majority-verdict group. (Plain mode-of-reason diverges on 3 cells
    # — FN1, JAK2, LAMP3 — where 2 reps share a different reason than
    # the rep that happens to be the verdict-majority representative.)
    def _representative_reason(group: pd.DataFrame) -> str:
        majority_verdict = group["predicted_verdict"].value_counts().index[0]
        in_majority = group[group["predicted_verdict"] == majority_verdict]
        return in_majority.sort_values("replicate").iloc[0]["predicted_reason"]

    per_gene = sub.groupby("gene_symbol").apply(
        lambda g: pd.Series({
            "ground_truth_reason": g["ground_truth_reason"].iloc[0],
            "predicted_reason": _representative_reason(g),
        }),
        include_groups=False,
    ).dropna()

    n = len(REASONS_ORDERED)
    idx_of = {r: i for i, r in enumerate(REASONS_ORDERED)}
    m = np.zeros((n, n), dtype=int)
    cell_genes: dict[tuple[int, int], list[str]] = {}
    n_match = 0
    for gene, row in per_gene.iterrows():
        c, a = row["ground_truth_reason"], row["predicted_reason"]
        if c not in idx_of or a not in idx_of:
            continue
        i, j = idx_of[c], idx_of[a]
        m[i, j] += 1
        cell_genes.setdefault((i, j), []).append(gene)
        if c == a:
            n_match += 1
    return m, len(per_gene), n_match, cell_genes


def _bucket_boundaries() -> list[int]:
    bounds, prev = [], None
    for i, r in enumerate(REASONS_ORDERED):
        b = BUCKET[r]
        if prev is not None and b != prev:
            bounds.append(i)
        prev = b
    return bounds


def main() -> None:
    _apply_brand_style()
    data = _fetch_tsv(DATA_TSV)
    m, n_joined, n_match, cell_genes = _build_matrix(data)
    n = m.shape[0]

    fig, ax = plt.subplots(figsize=(12, 11))
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, cmap=cmap, vmin=0, vmax=max(m.max(), 1),
        cbar_kws={"label": "genes", "shrink": 0.55},
        linewidths=0.4, linecolor="white",
        annot=False, ax=ax, square=True,
    )

    # Overlay diagonal-cell highlights + counts; off-diagonal cells get
    # a count + the gene names below (when ≤ 3 fit).
    for i in range(n):
        for j in range(n):
            v = int(m[i, j])
            if v == 0:
                continue
            on_diag = i == j
            if on_diag:
                ax.add_patch(mpatches.Rectangle(
                    (j, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT, lw=1.6,
                ))
            txt_color = "white" if v >= max(m.max() * 0.65, 8) else BRAND_INK
            ax.text(
                j + 0.5, i + 0.42, str(v),
                ha="center", va="center", fontsize=11,
                fontweight="bold" if on_diag else "normal", color=txt_color,
            )
            if not on_diag:
                genes = cell_genes.get((i, j), [])
                # 3 gene names fit comfortably in a cell; more → just count
                if 1 <= len(genes) <= 3:
                    ax.text(
                        j + 0.5, i + 0.74, ", ".join(genes),
                        ha="center", va="center", fontsize=8,
                        fontstyle="italic", color=BRAND_NEUTRAL,
                    )

    # Bucket separators (after yes / contextual)
    for x in _bucket_boundaries():
        ax.axvline(x, color=BRAND_NEUTRAL, lw=1.2, alpha=0.55)
        ax.axhline(x, color=BRAND_NEUTRAL, lw=1.2, alpha=0.55)

    ax.set_xticks(np.arange(n) + 0.5)
    ax.set_yticks(np.arange(n) + 0.5)
    ax.set_xticklabels([LABEL_SHORT[r] for r in REASONS_ORDERED],
                        rotation=35, ha="right", rotation_mode="anchor")
    ax.set_yticklabels([LABEL_SHORT[r] for r in REASONS_ORDERED], rotation=0)
    # Color tick labels by bucket to read the YES/contextual/no axes faster
    for axis_ticks, getter in [(ax.get_xticklabels(), lambda r: r),
                                (ax.get_yticklabels(), lambda r: r)]:
        for tick, reason in zip(axis_ticks, REASONS_ORDERED, strict=True):
            b = BUCKET[getter(reason)]
            tick.set_color(BUCKET_COLOR[b])
            tick.set_fontweight("semibold")

    ax.set_xlabel("Agent predicted_reason (Sonnet 4.6 + NCBI)")
    ax.set_ylabel("Curator\nground_truth_reason")

    # Footer: agreement headline + bucket legend
    legend_handles = [
        mpatches.Patch(color=BUCKET_COLOR["yes"], label="yes-bucket reasons"),
        mpatches.Patch(color=BUCKET_COLOR["contextual"], label="contextual-bucket reasons"),
        mpatches.Patch(color=BUCKET_COLOR["no"], label="no-bucket reasons"),
        mpatches.Patch(facecolor="none", edgecolor=DIAGONAL_HIGHLIGHT, lw=1.6,
                       label="diagonal (reason agrees)"),
    ]
    ax.legend(
        handles=legend_handles, loc="upper center",
        bbox_to_anchor=(0.5, -0.18), ncols=4, frameon=False, fontsize=11,
    )

    fig.suptitle(
        f"Exact reason agreement: {n_match}/{n_joined}  ({100 * n_match / n_joined:.1f}%)",
        y=0.95, fontsize=15, fontweight="semibold",
    )

    # Belt-and-suspenders despine: the brand rcParams set
    # axes.spines.top/right=False but we call explicitly for parity
    # with the canonical generator's style test.
    sns.despine(ax=ax, top=False, right=False)
    out_pdf = Path("curator_vs_agent_reason.pdf")
    out_png = Path("curator_vs_agent_reason.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  ({n_joined} genes; {n_match} on diagonal)")


if __name__ == "__main__":
    main()
