"""GO surface-rule variants: cohort inclusion cost vs SurfaceBench accuracy.

Context
-------
The GO column the paper reports (42.2 % on SurfaceBench) was not computed
with the rule the Methods describe. ``GO:0005887`` (integral component of
plasma membrane) is an ``alt_id`` of ``GO:0005886`` (plasma membrane) in
the ontology we pulled, and goatools resolves alt_ids silently, so the
third root expanded to every *sub-compartment* of the plasma membrane
(cytoplasmic side, apical, basolateral, caveola, ...) while never matching
plain plasma membrane itself. See
``docs/reports/2026-10-21-go-surface-rule-tradeoff.md``.

This script scores nine candidate GO rules the same way Supplementary
Figure 1 scores the per-source cutoff variants: x = how many
protein-coding proteins the rule admits (cost of inclusion), y = binary
SurfaceBench accuracy (yes + contextual vs no, n = 147). It reads only the
pinned GO artifacts already in ``data/external/go_human_surface_annotations``
(go-basic.obo release 2026-03-25; goa_human.gaf generated 2026-03-28), so
it is reproducible offline after ``scripts/bootstrap-worktree.sh all``.

Outputs (``data/analysis/go_rule_tradeoff/``):
  go_rule_tradeoff_points.tsv   one row per rule variant
  go_rule_tradeoff.{pdf,png}    the trade-off panel

Run: ``uv run python scripts/audit/audit_go_surface_rule_tradeoff.py``
"""

from __future__ import annotations

import collections
import csv
import gzip
from collections.abc import Callable

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from goatools.obo_parser import GODag

from accessible_surfaceome.audit._plotting_config import (
    save_figure,
    setup_plotting_style,
)
from accessible_surfaceome.paths import REPO_ROOT

GO_DIR = REPO_ROOT / "data/external/go_human_surface_annotations"
COHORT_TSV = (
    REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
)
UNIVERSE_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
BENCH_TSV = REPO_ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
OUT_DIR = REPO_ROOT / "data/analysis/go_rule_tradeoff"

N_YES, N_CTX, N_NO = 68, 31, 48

# ──── Term sets ──────────────────────────────────────────────────────────────
# Every root is expanded with is_a + part_of descendants (same closure the
# production pull uses). ``pmsub`` reproduces the released column: the
# plasma-membrane subtree minus plasma membrane itself.
ROOTS: dict[str, tuple[str, ...]] = {
    "out": ("GO:0009986", "GO:0009897"),  # cell surface, external side of PM
    "pm": ("GO:0005886",),  # plasma membrane (incl. itself)
    "tm": (
        "GO:0004888",
        "GO:0022857",
        "GO:0015267",
    ),  # TM signaling receptor / transporter / channel
    "adh": ("GO:0098631",),  # cell adhesion mediator activity
    "junc": (
        "GO:0030057",
        "GO:0005923",
        "GO:0005921",
        "GO:0070160",
    ),  # desmosome, tight, gap, tight
    "apbl": ("GO:0016324", "GO:0016323"),  # apical / basolateral plasma membrane
    "sigrec": ("GO:0038023",),  # signaling receptor activity
}

Hits = dict[str, bool]
Rule = Callable[[Hits], bool]

# (label, short label, evidence policy, family, predicate)
RULES: list[tuple[str, str, str, str, Rule]] = [
    (
        "Released column (alias leak: PM sub-compartments, no plain PM)",
        "released (alias leak)",
        "nie",
        "leak",
        lambda h: h["out"] or h["pmsub"],
    ),
    (
        "Alias fix: outward terms only (rule as written in Methods)",
        "alias fix (as written)",
        "nie",
        "fix",
        lambda h: h["out"],
    ),
    ("Alias fix + IEA", "alias fix + IEA", "all", "fix", lambda h: h["out"]),
    (
        "Plain plasma membrane (incl. PM itself)",
        "plain plasma membrane",
        "nie",
        "broad",
        lambda h: h["pm"],
    ),
    (
        "GO proposal: outward or (PM and TM function)",
        "GO proposal:\nPM ∧ TM function",
        "nie",
        "go",
        lambda h: h["out"] or (h["pm"] and h["tm"]),
    ),
    (
        "GO proposal + IEA",
        "GO proposal + IEA",
        "all",
        "go",
        lambda h: h["out"] or (h["pm"] and h["tm"]),
    ),
    (
        "GO proposal + adhesion fn + junction terms",
        "+ adhesion + junction",
        "nie",
        "ext",
        lambda h: h["out"] or (h["pm"] and (h["tm"] or h["adh"])) or h["junc"],
    ),
    (
        "+ apical/basolateral membrane",
        "+ apical/basolateral",
        "nie",
        "rec",
        lambda h: (
            h["out"] or (h["pm"] and (h["tm"] or h["adh"])) or h["junc"] or h["apbl"]
        ),
    ),
    (
        "+ apical/basolateral + (PM and signaling receptor)",
        "+ signaling receptor",
        "nie",
        "ext",
        lambda h: (
            h["out"]
            or (h["pm"] and (h["tm"] or h["adh"] or h["sigrec"]))
            or h["junc"]
            or h["apbl"]
        ),
    ),
]


def _descendants(dag: GODag, roots: tuple[str, ...]) -> set[str]:
    seen = set(roots)
    stack = list(roots)
    while stack:
        term = dag[stack.pop()]
        rev = (term.relationship_rev or {}).get("part_of", set())
        for child in list(term.children) + list(rev):
            if child.id not in seen:
                seen.add(child.id)
                stack.append(child.id)
    return seen


def _term_sets() -> dict[str, set[str]]:
    dag = GODag(str(GO_DIR / "go-basic.obo"), optional_attrs={"relationship"}, prt=None)
    sets = {k: _descendants(dag, v) for k, v in ROOTS.items()}
    sets["pmsub"] = sets["pm"] - {"GO:0005886"}
    return sets


def _scan_gaf(
    sets: dict[str, set[str]],
) -> tuple[dict[str, dict[str, Hits]], dict[str, str]]:
    """Per UniProt accession: {evidence policy: {set name: hit?}} plus symbol."""
    hits: dict[str, dict[str, Hits]] = collections.defaultdict(
        lambda: {
            "nie": collections.defaultdict(bool),
            "all": collections.defaultdict(bool),
        }
    )
    symbol_of: dict[str, str] = {}
    with gzip.open(GO_DIR / "goa_human.gaf.gz", "rt") as fh:
        for line in fh:
            if line.startswith("!"):
                continue
            f = line.rstrip("\n").split("\t")
            if (
                f[0] != "UniProtKB"
                or f[3].startswith("NOT")
                or "taxon:9606" not in f[12]
            ):
                continue
            acc, go_id, non_iea = f[1], f[4], f[6] != "IEA"
            symbol_of[acc] = f[2]
            for name, members in sets.items():
                if go_id in members:
                    hits[acc]["all"][name] = True
                    if non_iea:
                        hits[acc]["nie"][name] = True
    return hits, symbol_of


def compute_points() -> pd.DataFrame:
    sets = _term_sets()
    hits, symbol_of = _scan_gaf(sets)
    with COHORT_TSV.open() as fh:
        cohort = {r["gene_symbol"] for r in csv.DictReader(fh, delimiter="\t")}
    with UNIVERSE_TSV.open() as fh:
        universe = {r["uniprot_accession"] for r in csv.DictReader(fh, delimiter="\t")}
    bench: dict[str, tuple[str, str]] = {}
    with BENCH_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            bench.setdefault(
                r["gene_symbol"], (r["uniprot_acc"], r["ground_truth_verdict"])
            )
    assert len(bench) == N_YES + N_CTX + N_NO, len(bench)

    rows = []
    for label, short, ev, family, fn in RULES:
        admitted = {acc for acc, h in hits.items() if fn(h[ev])}
        genome = {acc for acc in admitted if symbol_of[acc] in cohort}
        verdict = collections.Counter(
            (v, acc in admitted) for _, (acc, v) in bench.items()
        )
        y, ctx, n_wrong = (
            verdict[("yes", True)],
            verdict[("contextual", True)],
            verdict[("no", True)],
        )
        rows.append(
            {
                "label": label,
                "short": short,
                "evidence": "non-IEA" if ev == "nie" else "all incl. IEA",
                "family": family,
                "size_genome": len(genome),
                "size_in_universe": len(admitted & universe),
                "new_to_universe": len(genome - universe),
                "acc": (y + ctx + N_NO - n_wrong) / (N_YES + N_CTX + N_NO),
                "yes_vs_no": (y + N_NO - n_wrong) / (N_YES + N_NO),
                "pos": (y + ctx) / (N_YES + N_CTX),
                "neg": (N_NO - n_wrong) / N_NO,
                "yes": y,
                "ctx": ctx,
                "no_wrong": n_wrong,
            }
        )
    return pd.DataFrame(rows)


# ──── Figure ─────────────────────────────────────────────────────────────────
FAM_COLOR = {
    "leak": "#BC3C4C",
    "fix": "#6F5D5A",
    "broad": "#F4AA28",
    "go": "#244840",
    "ext": "#4D8A80",
    "rec": "#4D8A80",
}
FAM_LABEL = {
    "leak": "released (bug)",
    "fix": "alias fix only",
    "broad": "plain PM",
    "go": "GO's proposal",
    "ext": "GO's proposal, extended",
    "rec": "recommended",
}
FAM_MARKER = {"leak": "D", "fix": "o", "broad": "o", "go": "o", "ext": "o", "rec": "*"}
FAM_SIZE = {"leak": 140, "fix": 120, "broad": 120, "go": 120, "ext": 120, "rec": 460}
# label offsets in points: (dx, dy, ha)
LABEL_OFFSET = {
    "released (alias leak)": (0, -18, "center"),
    "alias fix (as written)": (0, -18, "center"),
    "alias fix + IEA": (0, 14, "center"),
    "plain plasma membrane": (0, 16, "center"),
    "GO proposal:\nPM ∧ TM function": (-12, -20, "right"),
    "GO proposal + IEA": (10, -18, "left"),
    "+ adhesion + junction": (-12, 6, "right"),
    "+ apical/basolateral": (-10, 24, "center"),
    "+ signaling receptor": (16, -4, "left"),
}


def plot(df: pd.DataFrame) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    fig, ax = plt.subplots(figsize=(9, 6.5))
    for fam_key, g in df.groupby("family", sort=False):
        fam = str(fam_key)
        ax.scatter(
            g["size_genome"],
            g["acc"] * 100,
            s=FAM_SIZE[fam],
            marker=FAM_MARKER[fam],
            color=FAM_COLOR[fam],
            edgecolor="#1F1718",
            linewidth=1.6 if fam == "rec" else 0.8,
            label=FAM_LABEL[fam],
            zorder=3,
        )
    for _, r in df.iterrows():
        dx, dy, ha = LABEL_OFFSET[r["short"]]
        ax.annotate(
            r["short"],
            (r["size_genome"], r["acc"] * 100),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=11,
            color="#1F1718",
        )
    ax.set_xscale("log")
    ax.set_xticks([1000, 2000, 5000])
    ax.set_xticklabels(["1,000", "2,000", "5,000"])
    ax.set_xlim(550, 11000)
    ax.set_ylim(35, 92)
    ax.set_xlabel("Proteins the GO rule admits\n(protein-coding genome, log scale)")
    ax.set_ylabel("SurfaceBench accuracy (%)\n(yes + contextual vs no, n = 147)")
    ax.legend(loc="lower right", frameon=False, fontsize=11)
    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    save_figure(fig, "go_rule_tradeoff", OUT_DIR, formats=("pdf", "png"))


def main() -> None:
    df = compute_points()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "go_rule_tradeoff_points.tsv", sep="\t", index=False)
    cols = [
        "short",
        "evidence",
        "size_genome",
        "new_to_universe",
        "acc",
        "yes_vs_no",
        "pos",
        "neg",
    ]
    print(df[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    plot(df)


if __name__ == "__main__":
    main()
