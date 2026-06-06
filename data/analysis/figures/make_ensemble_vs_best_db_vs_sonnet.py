# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``ensemble_vs_best_db_vs_sonnet.{pdf,png}`` from the public repo.

Six-bar comparison on the 147-gene bench:

* Sonnet (+ IDs)        — the Claude triage agent on its canonical
                           NCBI-resolver prompt variant
* UniProt (TM+signal)    — best single classical DB, under its
                           bench-optimized cutoff (TM OR signal-peptide
                           positive)
* ≥2 / ≥3 / ≥4 / ≥5 DB   — ensemble callers: "yes" iff at least k of
                           the 5 surface DBs (UniProt, GO CC, HPA,
                           SURFY, CSPA, each under its own optimized
                           cutoff) vote yes

Accuracy uses the project's soft-credit rule: yes ≡ contextual on
the positive side; ``no`` matches ``no`` only.

Visual styling matches the in-repo ``_plotting_config`` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_ensemble_vs_best_db_vs_sonnet.py``.
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

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
BENCH_TSV = f"{BASE}/data/eval/triage_benchmark_v1.tsv"
CAND_TSV = f"{BASE}/data/processed/candidate_universe/candidate_universe.tsv"
PREDS_TSV = f"{BASE}/data/processed/triage_bench/mainbench_canonical_v2.tsv"
# Per-replicate predictions — used to overlay the Sonnet bar's individual
# replicate accuracies + SEM (the DB / ensemble bars are deterministic and
# stay plain — no run-to-run variance to show).
REPS_TSV = f"{BASE}/data/processed/triage_bench/mainbench_replicates_v2.tsv"
OPT_CUTOFFS_TSV = f"{BASE}/data/processed/triage_bench/db_optimized_cutoffs.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/0104308c239fe49d91d82a1007632b27"

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

# Sequential teal ramp for the ≥k ensembles: light → dark = permissive → strict.
ENSEMBLE_PALETTE = {
    2: "#7AAB9F",  # teal-light
    3: "#4D8A80",
    4: "#3D6B60",
    5: "#244840",  # teal-deep
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def _vote_correct(vote: str, truth: str) -> bool:
    if vote == truth:
        return True
    return vote in ("yes", "contextual") and truth in ("yes", "contextual")


def main() -> None:
    _apply_brand_style()

    bench = _fetch_tsv(BENCH_TSV)
    cand = _fetch_tsv(CAND_TSV).set_index("uniprot_accession")
    preds = _fetch_tsv(PREDS_TSV)
    opt = _fetch_tsv(OPT_CUTOFFS_TSV)
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt = set(opt.loc[opt["cspa_optimized"] == 1, "accession"].astype(str))

    truth_by_gene = dict(zip(bench["gene_symbol"], bench["ground_truth_verdict"], strict=True))
    acc_by_gene = dict(zip(bench["gene_symbol"], bench["uniprot_acc"], strict=True))

    def db_votes_for(acc: str) -> dict[str, bool]:
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

    sonnet_ncbi = preds[
        (preds["model"] == "claude-sonnet-4-6") & (preds["prompt_variant"] == "ncbi")
    ].set_index("gene_symbol")["predicted_verdict"].to_dict()

    callers: list[tuple[str, callable, str]] = [
        ("Sonnet (+ IDs)",      lambda g: sonnet_ncbi.get(g) or "no",                              BRAND_CLAUDE_ORANGE),
        ("UniProt\n(TM+signal)", lambda g: "yes" if db_votes_for(acc_by_gene.get(g, "")).get("UniProt") else "no",
                                                                                                    BRAND_PALETTE[0]),
    ]
    for k in (2, 3, 4, 5):
        callers.append((
            f"≥{k} DB",
            (lambda g, k=k: "yes" if sum(db_votes_for(acc_by_gene.get(g, "")).values()) >= k else "no"),
            ENSEMBLE_PALETTE[k],
        ))

    # Per-replicate Sonnet accuracies (for the bar height = mean-of-reps,
    # the points, and the SEM). The DB / ensemble callers are deterministic
    # — single value, no replicates.
    sonnet_rep_accs: list[float] = []
    try:
        _reps = _fetch_tsv(REPS_TSV)
        _s = _reps[(_reps["model"] == "claude-sonnet-4-6")
                   & (_reps["prompt_variant"] == "ncbi")].copy()
        _s["is_match"] = _s["is_match"].astype(int)
        sonnet_rep_accs = _s.groupby("replicate")["is_match"].mean().tolist()
    except Exception:  # noqa: BLE001
        sonnet_rep_accs = []

    genes = list(truth_by_gene)
    rows = []
    for label, vote_fn, color in callers:
        n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
        acc = n_correct / len(genes)
        # Sonnet bar = MEAN of per-replicate accuracies (so bar, points, and
        # SEM share one center). DB / ensemble bars keep their deterministic
        # majority count. The inner count label for Sonnet becomes the rounded
        # mean count (≈ avg correct per single run), the others stay exact.
        if label.startswith("Sonnet") and sonnet_rep_accs:
            acc = sum(sonnet_rep_accs) / len(sonnet_rep_accs)
            n_correct = round(acc * len(genes))
        rows.append({
            "caller": label, "accuracy": acc,
            "n_correct": n_correct, "n_total": len(genes), "color": color,
        })
    df = pd.DataFrame(rows)
    print("\nOverall accuracy on 147-gene bench:")
    for _, row in df.iterrows():
        print(f"  {row['caller'].replace(chr(10), ' '):20s}  "
              f"{row['accuracy']*100:5.1f}%  ({row['n_correct']}/{row['n_total']})")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(
        df["caller"], df["accuracy"] * 100,
        color=df["color"], edgecolor="none", width=0.6,
    )
    for bar, row in zip(bars, df.to_dict("records"), strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{row['accuracy']*100:.1f}%",
            ha="center", va="bottom",
            fontsize=17, fontweight="bold", color=BRAND_INK,
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{row['n_correct']}/{row['n_total']}",
            ha="center", va="center",
            fontsize=12, color="white", fontweight="bold",
        )

    # Overlay individual-replicate accuracies + SEM on the Sonnet bar only.
    # The Sonnet bar height is the MEAN of these per-rep accuracies (set
    # above), so the error bar (centered on that same mean) and the points
    # all line up with the bar top. DB / ensemble bars are deterministic and
    # stay plain.
    if len(sonnet_rep_accs) >= 2:
        rep_accs = [v * 100 for v in sonnet_rep_accs]
        sonnet_bar = bars[0]
        xc = sonnet_bar.get_x() + sonnet_bar.get_width() / 2
        m = sum(rep_accs) / len(rep_accs)
        sd = (sum((v - m) ** 2 for v in rep_accs) / (len(rep_accs) - 1)) ** 0.5
        sem = sd / (len(rep_accs) ** 0.5)
        ax.errorbar(xc, m, yerr=sem, fmt="none", ecolor=BRAND_INK,
                    elinewidth=1.2, capsize=4, capthick=1.2, zorder=4)
        for j, rv in enumerate(rep_accs):
            jitter = (j - (len(rep_accs) - 1) / 2) * (sonnet_bar.get_width() * 0.16)
            ax.scatter(xc + jitter, rv, s=24, color=BRAND_INK,
                       edgecolor="white", linewidth=0.5, zorder=5, alpha=0.9)

    ax.set_ylabel("Overall accuracy on 147-gene bench (%)", fontsize=14)
    ax.set_ylim(0, 105)
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", labelsize=13)
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    out_pdf = Path("ensemble_vs_best_db_vs_sonnet.pdf")
    out_png = Path("ensemble_vs_best_db_vs_sonnet.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
