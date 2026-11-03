"""Deep-dive run-to-run concordance, and how much of it is evidence retrieval.

New Supp figure. Genes drawn at random from the deep-dive cohort (two disjoint
batches of 25, seeds 20260927 and 20260928) were re-annotated and compared
field by field against their published records (run_id ``cu_v3_sonnet_2026_06``).

Two re-analyses per gene, each compared against the published record:

* **Full re-run** (run_id ``deep_dive_concordance_v1``; solid lines, filled
  markers) — literature discovery, paper selection, builders and synthesis all
  re-executed.
* **Fixed-evidence replay** (dotted lines, open markers) — reuses the published
  run's own evidence ledger and re-executes only the builders and synthesizer.
  The gap between the two isolates how much disagreement comes from which
  papers are retrieved and kept.

Each is scored two ways (maroon = hard, lavender = soft):

* **hard** — the value equals the published value.
* **soft** — within one step on an ordinal scale (e.g. moderate vs high
  accessibility); for the tier, the same surface call (canonical/likely vs
  low/uncertain/no); for the surface-call reason, the same side of the
  surface / non-surface divide; for the induction trigger, agreement on whether
  any trigger exists; for the subcategory, the same topology group. Protein
  family is nominal and has no soft grade.

Points are the fraction of genes matching; bars are exact (Clopper-Pearson) 95%
binomial confidence intervals.

Run::

    uv run python scripts/figures/deep_dive_replicate_concordance.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import beta

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "deep_dive_replicate_concordance"
DATA_TSV = ROOT / "data/processed/figures/deep_dive_replicate_kappa.tsv"

# (TSV column stem, axis label). The tier row leads and is separated by a rule.
_METRICS = [
    ("tier", "Confidence tier"),
    ("surface_call_reason", "Surface call reason"),
    ("surface_accessibility", "Surface accessibility"),
    ("surface_specificity", "Surface specificity"),
    ("evidence_grade", "Evidence grade"),
    ("confidence", "Confidence"),
    ("state_dependence", "State dependence"),
    ("induction_trigger", "Induction trigger"),
    ("expression_level", "Expression level"),
    ("expression_breadth", "Expression breadth"),
    ("subcategory", "Subcategory"),
    ("llm_family", "Protein family"),
]
_NO_SOFT = {"llm_family"}
_HARD_COLOR = COLORS["primary"]   # maroon
_SOFT_COLOR = COLORS["info"]      # lavender-mid: separable from maroon under red-green CVD
# (series, color, offset, solid?) — full re-run solid/filled, replay dotted/open.
_SERIES = [
    ("full_hard", _HARD_COLOR, -0.27, True),
    ("replay_hard", _HARD_COLOR, -0.09, False),
    ("full_soft", _SOFT_COLOR, 0.09, True),
    ("replay_soft", _SOFT_COLOR, 0.27, False),
]


def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = beta.ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    hi = beta.ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return float(lo), float(hi)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _series(rows: list[dict[str, str]], suffix: str, name: str) -> pd.DataFrame:
    n = len(rows)
    out = []
    for i, (stem, _) in enumerate(_METRICS):
        if suffix == "_soft_match" and stem in _NO_SOFT:
            continue
        k = sum(r[f"{stem}{suffix}"] == "True" for r in rows)
        lo, hi = _clopper_pearson(k, n)
        out.append({"row": i, "series": name, "k": k, "n": n, "agreement": 100 * k / n,
                    "ci_lo": 100 * lo, "ci_hi": 100 * hi})
    return pd.DataFrame(out)


def main() -> None:
    setup_plotting_style()
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 0,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 14,
    })
    rows = _read(DATA_TSV)
    full = [r for r in rows if r["comparison"] == "full_rerun"]
    replay = [r for r in rows if r["comparison"] == "fixed_evidence_replay"]
    df = pd.concat([
        _series(full, "_match", "full_hard"),
        _series(full, "_soft_match", "full_soft"),
        _series(replay, "_match", "replay_hard"),
        _series(replay, "_soft_match", "replay_soft"),
    ])
    style = {name: (color, off, solid) for name, color, off, solid in _SERIES}

    fig, ax = plt.subplots(figsize=(12, 13))
    sns.despine(ax=ax, top=True, right=True)
    for r in df.itertuples():
        color, off, solid = style[r.series]
        y = r.row + off
        _, _, bars = ax.errorbar(
            r.agreement, y,
            xerr=[[r.agreement - r.ci_lo], [r.ci_hi - r.agreement]],
            fmt="o", color=color, ecolor=color, elinewidth=2, capsize=3,
            markersize=7, markerfacecolor=color if solid else "white",
            markeredgewidth=1.8, clip_on=False,
        )
        if not solid:
            bars[0].set_linestyle(":")
        ax.text(102.5, y, f"{r.k}/{r.n}", va="center", ha="left", fontsize=10,
                color=color)

    ax.axhline(0.5, color=COLORS["line"], linewidth=1.5)
    ax.set_yticks(range(len(_METRICS)))
    ax.set_yticklabels([label for _, label in _METRICS])
    ax.set_ylim(len(_METRICS) - 0.5, -0.5)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Agrees with\npublished record (%)")
    ax.set_ylabel("")
    ax.grid(axis="y", visible=False)

    def _h(color, solid, label):
        return mlines.Line2D([], [], color=color, marker="o", markersize=8,
                             markerfacecolor=color if solid else "white",
                             markeredgewidth=1.8, linestyle="-" if solid else ":",
                             linewidth=2, label=label)
    ax.legend(handles=[
        _h(_HARD_COLOR, True, "Hard, full re-run"),
        _h(_HARD_COLOR, False, "Hard, fixed-evidence replay"),
        _h(_SOFT_COLOR, True, "Soft, full re-run"),
        _h(_SOFT_COLOR, False, "Soft, fixed-evidence replay"),
    ], loc="lower left", frameon=False)
    fig.tight_layout()
    save_figure(fig, SLUG, OUT_DIR)


if __name__ == "__main__":
    main()
