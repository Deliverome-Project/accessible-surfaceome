"""Supplementary Figure 15 — deep-dive run-to-run reliability as Cohen's kappa.

Fifty genes drawn at random from the deep-dive cohort were re-analysed two ways
— a full re-run (solid) and a fixed-evidence replay (dotted) — and each of the
24 LLM-derived filter fields, plus the derived surface call and confidence tier,
is scored as chance-corrected agreement with the published record. Inputs are
the TSV built by ``scripts/build/build_deep_dive_concordance_tsvs.py``
from the frozen bundle in ``data/processed/deep_dive_concordance_v1/``.
(``deep_dive_replicate_concordance.py`` is the exploratory percent-agreement
view of the same data.)

Ordered fields — including the five-tier confidence spectrum — use linearly
weighted kappa (a one-step disagreement earns partial credit); nominal fields
and the binary surface call use unweighted kappa. State dependence and
co-receptor dependency are scored on their ordered levels only, excluding
``unclear`` / ``unknown`` records (the row prints the n kept). Bars are 95% percentile intervals from 5,000
paired bootstrap resamples of genes. Shaded bands mark the McHugh (2012)
"moderate" (0.60-0.79), "strong" (0.80-0.90) and "almost perfect" (>0.90)
ranges.

Run::

    uv run python scripts/figures/deep_dive_replicate_kappa.py

# Reproduction: https://gist.github.com/beccajcarlson/14eec28d77e0d529213815c6af4283e0
"""
from __future__ import annotations

import csv
import math
import random
from collections import Counter
from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "deep_dive_replicate_kappa"
DATA_TSV = ROOT / "data/processed/figures/deep_dive_replicate_kappa.tsv"

_ORDINAL = {
    "surface_accessibility": ["no", "low", "moderate", "high"],
    "confidence": ["low", "moderate", "high"],
    "evidence_grade": ["weak", "supportive_but_indirect", "direct_single_method",
                       "direct_multi_method"],
    "surface_specificity": ["mostly_intracellular", "mixed", "surface_dominant"],
    "expression_breadth": ["rare", "restricted", "broad", "pan_tissue"],
    "expression_level": ["absent", "low", "moderate", "high"],
    # Figure 5's five-tier spectrum, weakest to strongest surface call.
    "tier": ["no", "uncertain", "low", "likely", "canonical"],
    # Ordered once the non-ordinal level is set aside ("unclear" / "unknown"
    # records are excluded from these two rows, and the row states its n).
    "state_dependence": ["low", "moderate", "high"],
    "co_receptor_dependency": ["none", "modulatory", "required"],
}
_EXCLUDED = {"state_dependence": "unclear", "co_receptor_dependency": "unknown"}
_POSITIVE = {"canonical", "likely"}
# Rows, grouped into sections. (stem, label, option text shown under the label).
# "<" separates ordered levels (weighted kappa); "·" separates unordered ones.
_SECTIONS = [
    ("Surface call", [
        ("surface_call", "Surface call", "canonical / likely  vs  low / uncertain / no"),
        ("tier", "Confidence tier", "no < uncertain < low < likely < canonical"),
    ]),
    ("Protein classification", [
        ("llm_family", "Protein family",
         "receptor · enzyme · transporter · miscellaneous"),
        ("subcategory", "Subcategory",
         "single-pass T1/T2 · multi-pass · GPCR · tetraspanin · GPI · other"),
        ("primary_compartment", "Primary compartment",
         "plasma membrane · endolysosome · ER · Golgi · cytosol · secreted …"),
    ]),
    ("Surface evidence", [
        ("surface_call_reason", "Surface call reason",
         "e.g. multipass · GPI · tissue-restricted · induced · secreted"),
        ("surface_accessibility", "Surface accessibility", "no < low < moderate < high"),
        ("surface_specificity", "Surface specificity",
         "mostly intracellular < mixed < surface-dominant"),
        ("evidence_grade", "Evidence grade",
         "weak < indirect < direct (1 method) < direct (multi)"),
        ("confidence", "Confidence", "low < moderate < high"),
        ("has_live_cell_surface_evidence", "Live-cell surface evidence", "yes · no"),
        ("overexpression_surface_localization_observed",
         "Surface localization on overexpression", "yes · no"),
    ]),
    ("Biological context", [
        ("state_dependence", "State dependence", "low < moderate < high"),
        ("induction_trigger", "Induction trigger",
         "none · oncogenic · immune · stress · infection · other …"),
        ("expression_level", "Expression level", "absent < low < moderate < high"),
        ("expression_breadth", "Expression breadth", "rare < restricted < broad < pan-tissue"),
        ("low_endogenous_expression", "Low endogenous expression", "yes · no"),
        ("tumor_associated", "Tumor-associated", "yes · no"),
    ]),
    ("Accessibility risks", [
        ("has_shed_form", "Shed form", "yes · no"),
        ("has_secreted_form", "Secreted form", "yes · no"),
        ("secreted_form_source", "Secreted form source",
         "proteolytic · splicing · both · unknown · n/a"),
        ("has_epitope_masking", "Epitope masking", "yes · no"),
        ("co_receptor_dependency", "Co-receptor dependency",
         "none < modulatory < required"),
        ("has_restricted_subdomain", "Restricted membrane subdomain", "yes · no"),
        ("restricted_subdomain_kind", "Restricted subdomain type",
         "apical · basolateral · junctional · ciliary · synaptic …"),
        ("has_known_ligand", "Known ligand", "yes · no"),
    ]),
]
_METRICS = [(stem, label, opts) for _, rows in _SECTIONS for stem, label, opts in rows]
_FULL_COLOR = COLORS["primary"]   # maroon
_REPLAY_COLOR = COLORS["info"]    # lavender-mid: separable from maroon under red-green CVD
_RARE = 0.2  # binary rows whose minority class is below this share get a prevalence note
_N_BOOT = 5000


# McHugh (2012) band shades: the brand green (#2E7A55) mixed 8% / 16% / 26% over
# white, as opaque colours — an alpha fill over the transparent figure background
# renders near-black in viewers that drop the alpha channel.
_BAND_MODERATE, _BAND_STRONG, _BAND_ALMOST_PERFECT = "#EEF4F1", "#DEEAE4", "#C9DCD3"


GIST_URL = "https://gist.github.com/beccajcarlson/14eec28d77e0d529213815c6af4283e0"


def _kappa(a: list, b: list, order: list | None = None) -> float:
    """Cohen's kappa; linearly weighted when ``order`` is given."""
    n = len(a)
    cats = order or sorted(set(a) | set(b), key=str)
    idx = {c: i for i, c in enumerate(cats)}
    m = len(cats)

    def w(i: int, j: int) -> float:
        if order and m > 1:
            return abs(i - j) / (m - 1)
        return 0.0 if i == j else 1.0

    ca, cb = Counter(a), Counter(b)
    d_obs = sum(w(idx[x], idx[y]) for x, y in zip(a, b)) / n
    d_exp = sum(ca[p] * cb[q] * w(idx[p], idx[q]) for p in cats for q in cats) / (n * n)
    return 1 - d_obs / d_exp if d_exp else math.nan


def _pairs(rows: list[dict[str, str]], stem: str, rep: str) -> tuple[list, list, list | None]:
    if stem == "surface_call":
        return ([r["tier_published"] in _POSITIVE for r in rows],
                [r[f"tier_{rep}"] in _POSITIVE for r in rows], None)
    a = [r[f"{stem}_published"] for r in rows]
    b = [r[f"{stem}_{rep}"] for r in rows]
    order = _ORDINAL.get(stem)
    if order:
        keep = [(x, y) for x, y in zip(a, b) if x in order and y in order]
        a, b = [x for x, _ in keep], [y for _, y in keep]
    return a, b, order


def _series(rows: list[dict[str, str]], rep: str, name: str, rng: random.Random) -> pd.DataFrame:
    out = []
    for i, (stem, _, _) in enumerate(_METRICS):
        a, b, order = _pairs(rows, stem, rep)
        point = _kappa(a, b, order)
        boots = []
        for _ in range(_N_BOOT):
            ix = [rng.randrange(len(a)) for _ in a]
            kb = _kappa([a[j] for j in ix], [b[j] for j in ix], order)
            if not math.isnan(kb):
                boots.append(kb)
        boots.sort()
        lo = boots[int(0.025 * len(boots))] if boots else point
        hi = boots[int(0.975 * len(boots)) - 1] if boots else point
        out.append({"row": i, "series": name, "kappa": point, "lo": lo, "hi": hi})
    return pd.DataFrame(out)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> None:
    setup_plotting_style()
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
    })
    rows = _read(DATA_TSV)
    full_rows = [r for r in rows if r["comparison"] == "full_rerun"]
    replay_rows = [r for r in rows if r["comparison"] == "fixed_evidence_replay"]
    rng = random.Random(20260927)
    df = pd.concat([
        _series(full_rows, "reanalysis", "full", rng),
        _series(replay_rows, "reanalysis", "replay", rng),
    ])

    # Row positions, leaving a gap before each section for its header.
    ypos, headers, y = [], [], 0.0
    for title, rows in _SECTIONS:
        headers.append((y, title))
        y += 0.9
        for _ in rows:
            ypos.append(y)
            y += 1.25
        y += 0.3
    df["y"] = df["row"].map(dict(enumerate(ypos)))

    fig, ax = plt.subplots(figsize=(15, 20))
    sns.despine(ax=ax, top=True, right=True)
    # McHugh (2012) bands, drawn contiguous so no gap shows between them.
    ax.axvspan(0.60, 0.80, color=_BAND_MODERATE, zorder=0)
    ax.axvspan(0.80, 0.90, color=_BAND_STRONG, zorder=0)
    ax.axvspan(0.90, 1.00, color=_BAND_ALMOST_PERFECT, zorder=0)

    for r in df.itertuples():
        solid = r.series == "full"
        color = _FULL_COLOR if solid else _REPLAY_COLOR
        yy = r.y + (-0.19 if solid else 0.19)
        _, _, bars = ax.errorbar(
            r.kappa, yy, xerr=[[r.kappa - r.lo], [r.hi - r.kappa]],
            fmt="o", color=color, ecolor=color, elinewidth=2, capsize=3,
            markersize=7, markerfacecolor=color if solid else "white",
            markeredgewidth=1.8, clip_on=True, zorder=3,
        )
        if not solid:
            bars[0].set_linestyle(":")
        ax.text(1.04, yy, f"{r.kappa:.2f}", va="center", ha="left", fontsize=13,
                color=color)

    # Row labels drawn by hand so each can carry a lighter option line beneath it.
    trans = ax.get_yaxis_transform()
    for yy, (stem, label, opts) in zip(ypos, _METRICS):
        kind = "weighted κ" if stem in _ORDINAL else "unweighted κ"
        if stem in _EXCLUDED:
            scale = _ORDINAL[stem]
            n_kept = sum(r[f"{stem}_published"] in scale and r[f"{stem}_reanalysis"] in scale
                         for r in full_rows)
            opts = f"{opts}  ({_EXCLUDED[stem]} excluded, n={n_kept})"
        if opts == "yes · no":
            n_yes = sum(r[f"{stem}_published"] == "True" for r in full_rows)
            if min(n_yes, len(full_rows) - n_yes) < _RARE * len(full_rows):
                opts = f"yes · no  (rare: {n_yes}/{len(full_rows)} yes)"
        ax.text(-0.02, yy - 0.2, label, transform=trans, ha="right", va="center",
                fontsize=15, color=COLORS["dark"])
        ax.text(-0.02, yy + 0.3, f"{opts}  [{kind}]", transform=trans, ha="right",
                va="center", fontsize=13, color=COLORS["neutral"])
    for yy, title in headers:
        ax.text(-0.02, yy + 0.25, title.upper(), transform=trans, ha="right",
                va="center", fontsize=13, fontweight=800, color=COLORS["primary"])
        if yy > 0:
            ax.axhline(yy - 0.15, color=COLORS["neutral"], linewidth=0.8, alpha=0.5,
                       zorder=1)

    ax.set_yticks([])
    ax.set_ylim(y - 0.2, -0.7)
    ax.set_xlim(0, 1.005)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("Cohen's κ vs\npublished record")
    ax.set_ylabel("")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[
        mlines.Line2D([], [], color=_FULL_COLOR, marker="o", markersize=8, linewidth=2,
                      label="Full re-run"),
        mlines.Line2D([], [], color=_REPLAY_COLOR, marker="o", markersize=8, linewidth=2,
                      markerfacecolor="white", markeredgewidth=1.8, linestyle=":",
                      label="Fixed-evidence replay"),
        mpatches.Patch(color="none", label=""),  # spacer: bands fill column two
        mpatches.Patch(color=_BAND_MODERATE, label="Moderate (0.60–0.79)"),
        mpatches.Patch(color=_BAND_STRONG, label="Strong (0.80–0.90)"),
        mpatches.Patch(color=_BAND_ALMOST_PERFECT, label="Almost perfect (>0.90)"),
    ], loc="upper center", bbox_to_anchor=(0.45, -0.075), ncol=2, frameon=False,
        columnspacing=1.5, handlelength=2.2)
    fig.tight_layout()
    save_figure(fig, SLUG, OUT_DIR, gist_url=GIST_URL)


if __name__ == "__main__":
    main()
