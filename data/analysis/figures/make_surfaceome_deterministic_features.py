# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``surfaceome_deterministic_features.{pdf,png}``.

**Supplementary Fig 14.** Distribution of twelve deterministic per-gene
features across the surfaceome, faceted by the REAL deep-dive
surface-accessibility tier collapsed into four comparison groups, plus a fifth
facet — the full Sonnet dual-triage surface pool:

  * canonical      — group == 'canonical' (high-confidence surface);
  * likely         — group == 'likely';
  * low            — group == 'low' (low/moderate accessibility, weak evidence);
  * uncertain / no — group ∈ {uncertain, no} (ambiguous-to-negative);
  * Sonnet dual triage — every gene the two-stage Sonnet triage
    (genome_full_sonnet_ncbi_v2 plus the four PubMed rescue lanes) called
    yes/contextual (all 4,628, each with topology). A DIFFERENT category: broader, and
    its det features come from the genome-wide D1 tables (topology_public,
    compara_*, schweke_homomer_public, surface_bind_*) rather than the
    deep-dive records, since most of these genes are not deep-dived. Same
    DeepTMHMM / Compara / Schweke computation, ~100% topology coverage.

The 5-tier deep-dive verdict comes from ``_dd_assign_bucket`` where the gene
has a published record. Genes not yet deep-dived (``group == 'pending'``) are
EXCLUDED from the deep-dive tiers (and are already absent from the bundled TSV).

The 4×3 panel grid compares each feature across the five facets. The three
CONTINUOUS features — TM-helix count, protein length, ECD length — are shown as
violins; the nine BOOLEAN features (signal peptide, N/C-terminus extracellular,
mouse + cyno 1:1 ortholog presence, Schweke-2024 homo-oligomer state,
alt-isoform topology change, concerning paralog, extracellular surface-bind
site) as per-facet fraction bars. The features are pre-joined into a single
bundled TSV by ``scripts/build_figure_tsvs.py`` so the gist is a one-TSV
reproduction unit.

The deep-dive-tier features are sourced from the deep-dive RECORDS (full
coverage per deep-dived gene, fixing the prior DeepTMHMM-M1-only coverage bias);
the Sonnet pool's features come from the genome-wide D1 tables (topology 100%).

Full deep-dive cohort (5,332 genes); the `canonical` tier uses the PR #130 gate.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist runs
standalone — ``uv run make_surfaceome_deterministic_features.py``.
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

# Published reproduction gist — embedded into output PNG Source / PDF
# Subject metadata (mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/57cf3cc3db903ab39bc0ba315ce5e4d5"

# Single bundled per-figure TSV — one tidy row per gene with the bucket
# assignment + the nine deterministic feature columns the panels read.
DATA_TSV = f"{BASE}/data/processed/figures/surfaceome_deterministic_features.tsv"

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
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3."""
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
        "font.size": 15,
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
        "xtick.labelsize": 16.5,
        "ytick.labelsize": 16.5,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 16.5,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# === Facet definitions: four deep-dive tiers + the Sonnet dual-triage pool ===
# The 5-tier deep-dive spectrum collapsed to four comparison facets by pooling
# only the two weakest tiers (uncertain + no), plus a FIFTH facet — the full
# Sonnet dual-triage surface pool (terracotta). Tier colours follow the
# canonical deep-dive confidence spectrum: green (canonical) → teal (likely) →
# amber-tan (low) → neutral (uncertain/no). Genes still in the `pending` tier
# (not yet deep-dived) are excluded before this map is applied.
GROUPS = ["canonical", "likely", "low", "uncertain_no", "sonnet_dual_triage"]
GROUP_LABEL = {
    "canonical":    "canonical",
    "likely":       "likely",
    "low":          "low",
    "uncertain_no": "uncertain / no",
    "sonnet_dual_triage": "Sonnet dual triage",
}
GROUP_COLOR = {
    "canonical":    "#2E7A55",  # success green — high-confidence surface
    "likely":       "#3D6B60",  # teal-mid — likely surface
    "low":          "#C99A5B",  # amber-tan — low/moderate access, weak evidence
    "uncertain_no": "#9C8C88",  # lifted neutral — ambiguous-to-negative tiers
    "sonnet_dual_triage": "#d87851",  # Sonnet terracotta — the full triage pool
}

# Raw deep-dive tiers that collapse into the `uncertain_no` facet.
UNCERTAIN_NO_TIERS = ("uncertain", "no")


def assign_facet(group: str) -> str | None:
    """Map a raw ``group`` value to one of the five comparison facets.

    The four leftmost facets are deep-dive tiers (from the records); the fifth,
    ``sonnet_dual_triage``, is the FULL Sonnet dual-triage surface pool (det
    features from the genome-wide D1 tables), placed rightmost.

    Returns ``None`` for ``pending`` (not yet deep-dived) or any value outside
    the known spectrum, so those rows are dropped from the comparison.
    """
    if group == "canonical":
        return "canonical"
    if group == "likely":
        return "likely"
    if group == "low":
        return "low"
    if group in UNCERTAIN_NO_TIERS:
        return "uncertain_no"
    if group == "sonnet_dual_triage":
        return "sonnet_dual_triage"
    return None


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Sibling-first: read the bundled TSV next to this script (the gist
    case), else the in-repo path. No network fetch — the gist is the single
    citable reproduction unit."""
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


def _embed_source_in_metadata(out_path: Path, url: str) -> None:
    """Write the gist URL into the PNG's Source tEXt chunk so the URL
    travels with the file."""
    if out_path.suffix == ".png":
        try:
            from PIL import Image, PngImagePlugin
            img = Image.open(out_path)
            meta = PngImagePlugin.PngInfo()
            for k, v in img.info.items():
                if isinstance(v, (str, bytes)):
                    meta.add_text(k, v if isinstance(v, str) else v.decode("latin-1", "ignore"))
            meta.add_text("Source", url)
            img.save(out_path, "PNG", pnginfo=meta)
        except Exception:  # noqa: BLE001 — best-effort
            pass


def _panel_label(ax: plt.Axes, letter: str, title: str) -> None:
    """Panel letter (Manrope ExtraBold, weight 800) + the panel's metric as a
    title above the axes — frees the y-label column so value labels fit."""
    n_extra = title.count("\n")
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction", xytext=(0, 8),
                textcoords="offset points", fontsize=18, va="bottom", ha="left",
                color=BRAND_INK)
    ax.annotate(letter, xy=(0, 1), xycoords="axes fraction",
                xytext=(-10, 8 + 21.5 * n_extra), textcoords="offset points",
                fontsize=25, fontweight=800, va="bottom", ha="right", color=BRAND_INK)


def render(feats: pd.DataFrame, out_dir: Path) -> Path:
    _apply_brand_style()

    facet_labels = [GROUP_LABEL[g] for g in GROUPS]
    facet_colors = [GROUP_COLOR[g] for g in GROUPS]

    fig, axes = plt.subplots(4, 3, figsize=(15, 14.5))
    axes = axes.flatten()

    # Each panel is (column, kind, label) where kind ∈ {violin, frac_bool}.
    # Continuous features → violins; boolean 0/1 features → fraction bars.
    # Fourth element is the fixed y-axis range so the panels read on a common,
    # honest scale: continuous violins get feature-appropriate caps (a: TM-helix
    # 0–30, b: protein length 0–7k, c: ECD length 0–5k) and every boolean
    # fraction panel (d–l) is pinned to a true 0–100%.
    panels = [
        ("tm_helix_count",      "violin",    "Number of TM helices", (0, 30)),
        ("protein_length",      "violin",    "Protein length (residues)", (0, 7000)),
        ("ecd_length_residues", "violin",    "ECD length (residues)", (0, 5000)),
        ("has_signal_peptide",  "frac_bool", "% with signal peptide", (0, 100)),
        ("n_term_extracellular", "frac_bool", "% N-terminus extracellular", (0, 100)),
        ("c_term_extracellular", "frac_bool", "% C-terminus extracellular", (0, 100)),
        ("mouse_has_one2one",   "frac_bool", "% with mouse 1:1 ortholog", (0, 100)),
        ("cyno_has_one2one",    "frac_bool", "% with cyno 1:1 ortholog", (0, 100)),
        ("schweke_homomer",     "frac_bool", "% homo-oligomer (Schweke 2024)", (0, 100)),
        ("alt_iso_diff_topo",   "frac_bool", "% with alt isoform of\ndifferent topology", (0, 100)),
        ("has_concerning_paralog", "frac_bool", "% concerning paralog\n(ECD 40%+ id)", (0, 100)),
        ("has_ec_surface_bind_site", "frac_bool", "% with 1+ extracellular\nsurface-bind site", (0, 100)),
    ]

    letters = "abcdefghijkl"
    for ax, letter, (col, kind, label, ylim) in zip(axes, letters, panels):
        if kind == "violin":
            data = [
                feats.loc[feats["facet"] == g, col].astype(float).dropna().tolist()
                for g in GROUPS
            ]
            positions = list(range(len(GROUPS)))
            parts = ax.violinplot(
                data, positions=positions, showmedians=True,
                showextrema=False, widths=0.82,
            )
            for body, color in zip(parts["bodies"], facet_colors):
                body.set_facecolor(color)
                body.set_edgecolor("none")
                body.set_alpha(0.9)
            if "cmedians" in parts:
                parts["cmedians"].set_color("white")
                parts["cmedians"].set_linewidth(1.6)
            ax.set_xticks(positions)
            ax.set_xticklabels(facet_labels, rotation=35, ha="right", rotation_mode="anchor")
            ax.set_xlim(-0.6, len(GROUPS) - 0.4)
            ax.set_ylim(*ylim)
        elif kind == "frac_bool":
            ys = []
            ns = []
            for g in GROUPS:
                sub = feats[feats["facet"] == g][col]
                sub_clean = pd.to_numeric(sub, errors="coerce").dropna()
                n = len(sub_clean)
                positive = (sub_clean.astype(int) == 1).sum()
                ys.append(100 * positive / n if n else 0)
                ns.append(n)
            ax.bar(range(len(GROUPS)), ys, color=facet_colors, edgecolor="none")
            # True 0–100 axis (spine + ticks stop at 100); headroom above it so
            # every value+n label sits above its bar without clipping.
            for i, (y, n_) in enumerate(zip(ys, ns)):
                ax.text(i, y + 1.5, f"{y:.0f}%\nn={n_}", ha="center", va="bottom",
                        fontsize=13.5, color=facet_colors[i])
            ax.set_ylim(ylim[0], ylim[1] * 1.15)
            ax.set_yticks(range(0, 101, 25))
            ax.spines["left"].set_bounds(*ylim)
            ax.set_xlim(-0.5, len(GROUPS) - 0.5)
            ax.set_xticks(range(len(GROUPS)))
            ax.set_xticklabels(facet_labels, rotation=35, ha="right", rotation_mode="anchor")

        ax.tick_params(axis="x", labelsize=16.5)
        for tl in ax.get_xticklabels():
            tl.set_horizontalalignment("right")
        sns.despine(ax=ax, top=True, right=True)
        # Tier names only under the bottom row; the legend keys the colours.
        if letter not in letters[-3:]:
            ax.tick_params(axis="x", labelbottom=False)
        _panel_label(ax, letter, label)

    # 12 panels fill the 4×3 grid; hide any spare cell if a panel is dropped.
    for extra in axes[len(panels):]:
        extra.set_visible(False)

    plt.tight_layout(rect=(0, 0, 1, 0.96), w_pad=0.4)

    # Single legend at top — four deep-dive tiers + the Sonnet dual-triage pool.
    # Drawn after tight_layout and anchored just under the rect top (0.96)
    # so it sits just above row 1 rather than floating over a gap.
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g],
                      label=GROUP_LABEL[g].replace("\n", " "))
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="lower center", ncol=5, frameon=False,
        bbox_to_anchor=(0.5, 0.945), fontsize=16.5,
        title="Deep-dive tier / Sonnet dual-triage pool", title_fontsize=18,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / "surfaceome_deterministic_features.pdf"
    png = out_dir / "surfaceome_deterministic_features.png"
    fig.savefig(pdf, metadata={"Subject": GIST_URL})
    fig.savefig(png, metadata={"Source": GIST_URL})
    _embed_source_in_metadata(png, GIST_URL)
    plt.close(fig)
    return pdf


def main() -> None:
    feats = _fetch_tsv(DATA_TSV)
    print(f"Deep-dive tier universe (all groups): {len(feats)}")
    print(feats["group"].value_counts().to_string())
    # Collapse the raw per-gene tier to the 5-facet comparison; `pending`
    # (not yet deep-dived) maps to NaN and is dropped.
    feats["facet"] = feats["group"].map(assign_facet)
    feats = feats[feats["facet"].notna()].copy()
    print(f"\nDeep-dived genes compared (pending excluded): {len(feats)}")
    print(feats["facet"].value_counts().reindex(GROUPS).to_string())
    out = render(feats, Path(__file__).parent)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
