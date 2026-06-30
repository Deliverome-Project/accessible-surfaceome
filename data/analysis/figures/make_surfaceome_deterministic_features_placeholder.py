# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``surfaceome_deterministic_features_placeholder.{pdf,png}``.

**MOCK supplementary figure (Supp Fig 13).** Distribution of seven
deterministic per-gene features across the Sonnet-positive surfaceome,
faceted into three buckets. The deep-dive hues are MOCKED from Sonnet
verdicts for now — they'll be replaced once the deep-dive runs over the
full surfaceome:

  * triage_yes               = Sonnet verdict 'yes' (non-high confidence)
  * deep_dive_high_conf      = Sonnet 'yes' + high confidence (placeholder
                               for the deep-dive high-confidence surface
                               bucket)
  * deep_dive_likely_surface = Sonnet verdict 'contextual'

The 3×3 panel grid compares each feature across the three buckets:
TM-helix count, protein length, signal peptide, N/C-terminus
extracellular, mouse + cyno 1:1 high-confidence ortholog presence,
Schweke-2024 homo-oligomer state, and alt-isoform topology change. The
features are pre-joined into a single bundled TSV by
``scripts/build_figure_tsvs.py`` so the gist is a one-TSV reproduction
unit.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist runs
standalone — ``uv run make_surfaceome_deterministic_features_placeholder.py``.
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
# assignment + the seven deterministic feature columns the panels read.
DATA_TSV = f"{BASE}/data/processed/figures/surfaceome_deterministic_features_placeholder.tsv"

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
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 12,
        "axes.labelsize": 12,
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
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 11,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# === Group definitions (placeholders — replace with deep-dive when ready) ===
GROUPS = ["triage_yes", "deep_dive_high_conf", "deep_dive_likely_surface"]
GROUP_LABEL = {
    "triage_yes":               "Triage yes",
    "deep_dive_high_conf":      "Deep dive — high-conf surface",
    "deep_dive_likely_surface": "Deep dive — likely surface",
}
# Sequential teal: darker = more confident (same convention as the
# ADC-source stacking in positive_control_db_coverage_bars).
GROUP_COLOR = {
    "triage_yes":               "#7AAB9F",  # teal-light
    "deep_dive_high_conf":      "#244840",  # teal-darkest
    "deep_dive_likely_surface": "#4D8A80",  # teal-medium
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Sibling-only: bundled TSV must sit next to this script. No
    network fetch — the gist is the single citable reproduction unit."""
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


def render(feats: pd.DataFrame, out_dir: Path) -> Path:
    _apply_brand_style()

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    axes = axes.flatten()

    # Each panel is (column, kind, label) where kind ∈ {boxplot, frac_bool}.
    panels = [
        ("tm_helix_count",                   "boxplot",   "Number of TM helices"),
        ("protein_length",                   "boxplot",   "Protein length (residues)"),
        ("has_signal_peptide",               "frac_bool", "% with signal peptide"),
        ("n_term_extracellular",             "frac_bool", "% N-terminus extracellular"),
        ("c_term_extracellular",             "frac_bool", "% C-terminus extracellular"),
        ("mouse_has_one2one_high_confidence", "frac_bool", "% with mouse 1:1 ortholog (high-conf)"),
        ("cyno_has_one2one_high_confidence", "frac_bool", "% with cyno 1:1 ortholog (high-conf)"),
        ("schweke_homomer",                  "frac_bool", "% homo-oligomer (Schweke 2024)"),
        ("alt_iso_diff_topo",                "frac_bool", "% with alt isoform of different topology"),
    ]

    for ax, (col, kind, label) in zip(axes, panels):
        if kind == "boxplot":
            data = []
            for g in GROUPS:
                vals = feats.loc[feats["group"] == g, col].dropna().tolist()
                data.append(vals)
            bp = ax.boxplot(
                data, tick_labels=[GROUP_LABEL[g] for g in GROUPS], patch_artist=True,
                medianprops=dict(color="white", linewidth=1.5),
                showfliers=False,
            )
            for patch, g in zip(bp["boxes"], GROUPS):
                patch.set_facecolor(GROUP_COLOR[g])
                patch.set_edgecolor("none")
            ax.set_ylabel(label, fontsize=11)
        elif kind == "frac_bool":
            ys = []
            ns = []
            for g in GROUPS:
                sub = feats[feats["group"] == g][col]
                sub_clean = pd.to_numeric(sub, errors="coerce").dropna()
                n = len(sub_clean)
                positive = (sub_clean.astype(int) == 1).sum()
                ys.append(100 * positive / n if n else 0)
                ns.append(n)
            colors = [GROUP_COLOR[g] for g in GROUPS]
            ax.bar(range(len(GROUPS)), ys, color=colors, edgecolor="none")
            for i, (y, n_) in enumerate(zip(ys, ns)):
                ax.text(i, y + 1.5, f"{y:.0f}%\nn={n_}", ha="center", va="bottom",
                        fontsize=9, color=colors[i], weight="semibold")
            ax.set_ylim(0, 110)
            ax.set_xticks(range(len(GROUPS)))
            ax.set_xticklabels([GROUP_LABEL[g].replace(" — ", "\n") for g in GROUPS],
                               rotation=0, fontsize=9, ha="center")
            ax.set_ylabel(label, fontsize=10)

        sns.despine(ax=ax, top=True, right=True)
        if kind == "boxplot":
            ax.tick_params(axis="x", rotation=15)
            for tl in ax.get_xticklabels():
                tl.set_fontsize(9)
                tl.set_horizontalalignment("right")

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=GROUP_COLOR[g], label=GROUP_LABEL[g])
        for g in GROUPS
    ]
    fig.legend(
        handles=legend_handles, loc="upper center", ncol=3, frameon=False,
        bbox_to_anchor=(0.5, 1.02), fontsize=11,
        title="Surfaceome bucket (deep-dive hues MOCKED from Sonnet for now)",
        title_fontsize=11,
    )

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / "surfaceome_deterministic_features_placeholder.pdf"
    png = out_dir / "surfaceome_deterministic_features_placeholder.png"
    fig.savefig(pdf, metadata={"Subject": GIST_URL})
    fig.savefig(png, metadata={"Source": GIST_URL})
    _embed_source_in_metadata(png, GIST_URL)
    plt.close(fig)
    return pdf


def main() -> None:
    feats = _fetch_tsv(DATA_TSV)
    print(f"Sonnet-positive surfaceome: {len(feats)}")
    print(feats["group"].value_counts().to_string())
    out = render(feats, Path(__file__).parent)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
