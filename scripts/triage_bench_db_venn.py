"""5-way Venn diagram of the M1 surface databases — two views.

For each of the 5 retained surface DBs (UniProt subcellular query,
GO cellular component, HPA, SURFY, CSPA), build the set of UniProt
accessions in the M1 candidate universe that the DB votes ``true``.

Two visualizations of the same data:

* ``db_overlap_venn`` — elliptical 5-way Venn. Topologically correct
  (every one of the 31 non-empty regions is represented) but **NOT
  area-proportional** — that's a known unsolved problem in geometry
  for 5 sets, no library produces a true area-proportional 5-ellipse
  Venn. Reads as "structure of agreement at a glance".
* ``db_overlap_upset`` — UpSetPlot rendering of the same data. **IS
  area-proportional** (each intersection is a bar whose height is
  its set size). Standard for ≥4 sets in genomics. Reads as "exactly
  how many proteins agree across which combination of DBs".

Outputs (PDF + PNG):
  data/analysis/triage_bench/{db_overlap_venn,db_overlap_upset}.{pdf,png}

# Reproduction: https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa
#   db_overlap_venn — minimal PyPA inline-script-metadata standalone fetching the universe
#   TSV via raw.githubusercontent.com. Mirror lives at
#   data/analysis/figures/make_db_overlap_venn.py (canonical
#   source-of-truth; the gist is the readers' minimal-dep mirror).
#   See the Final-Figure Gist Convention in CLAUDE.md / AGENTS.md.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import pandas as pd
import upsetplot
from venn import venn

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    save_figure,
    setup_plotting_style,
)


DB_FLAGS_5 = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag", "GO CC"),
    ("hpa_surface_flag", "HPA"),
    ("surfy_surface_flag", "SURFY"),
    ("cspa_surface_flag", "CSPA"),
]

# Per-DB fixed colour assignment. Every label always renders with the
# same colour across figures (UniProt = palette[0], GO CC = palette[1],
# …). Match the standalone gist's PALETTE_BY_LABEL so the canonical
# figure and the gist's live re-run produce identical colour-to-DB
# mappings regardless of which DB happens to be the largest set.
PALETTE_BY_LABEL = {
    label: CATEGORICAL_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS_5)
}

# Pin to an immutable commit SHA so the reproduction is traceable and
# tamper-evident. Bump together with ``_EXPECTED_TSV_SHA256`` whenever
# the upstream universe TSV is intentionally refreshed (and update the
# matching ``data[0]`` entry in scripts/embed_figure_gist_metadata.py).
_PINNED_COMMIT_SHA = "898c743d9df4ec7497e7424b80d3408e5ad07c41"
_CAND_URL = (
    "https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/"
    f"{_PINNED_COMMIT_SHA}/data/processed/candidate_universe/candidate_universe.tsv"
)
_EXPECTED_TSV_SHA256 = (
    "2406464f3f86680e76844fe07e9aa32e5550960bc9fa5573137bb31c15ea3ef2"
)


def _load_universe_bytes(path: Path) -> bytes:
    """Return the universe TSV bytes from ``path`` if present, else fetch
    them from the pinned commit URL. Verifies sha256 against the
    pinned digest in either case and raises ``SystemExit`` on mismatch.
    """

    if path.is_file():
        tsv_bytes = path.read_bytes()
    else:
        r = httpx.get(_CAND_URL, timeout=30)
        r.raise_for_status()
        tsv_bytes = r.content
    got = hashlib.sha256(tsv_bytes).hexdigest()
    if got != _EXPECTED_TSV_SHA256:
        raise SystemExit(
            f"candidate_universe.tsv sha256 mismatch: expected "
            f"{_EXPECTED_TSV_SHA256}, got {got}. The pinned URL "
            f"({_CAND_URL}) may be wrong, or upstream content changed."
        )
    return tsv_bytes


def build_sets(path: Path) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {label: set() for _, label in DB_FLAGS_5}
    tsv_bytes = _load_universe_bytes(path)
    reader = csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t")
    for row in reader:
        acc = row["uniprot_accession"]
        for flag, label in DB_FLAGS_5:
            if row.get(flag, "0") == "1":
                sets[label].add(acc)
    return sets


def make_plot(out_dir: Path) -> None:
    setup_plotting_style(style="white", context="notebook", font_scale=1.0)
    sets = build_sets(Path("data/processed/candidate_universe/candidate_universe.tsv"))

    # Sort by set size descending so the largest set ends up under the
    # most-readable ellipse slot in the `venn` package layout.
    sorted_keys = sorted(sets, key=lambda k: -len(sets[k]))
    sorted_sets = {k: sets[k] for k in sorted_keys}

    fig, ax = plt.subplots(figsize=(11, 10))
    cmap = [PALETTE_BY_LABEL[k] for k in sorted_keys]
    venn(
        sorted_sets,
        ax=ax,
        cmap=cmap,
        fontsize=15,
        legend_loc=None,  # custom legend below so it doesn't overlap the ellipses
    )

    # ax.set_title is a no-op under the project's no-titles policy
    # (see _plotting_config.setup_plotting_style); the summary stats
    # below can move into the figure caption in any document that
    # embeds this plot.
    ax.set_xticks([])
    ax.set_yticks([])

    # Legend with per-DB set size, anchored below the diagram. Fontsize
    # bumped to match the rest of the post-2026-05 plotting config.
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE_BY_LABEL[k], alpha=0.6)
        for k in sorted_keys
    ]
    labels = [f"{k}  (n = {len(sets[k]):,})" for k in sorted_keys]
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncols=len(sorted_keys),
        frameon=False,
        fontsize=14,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="db_overlap_venn",
        output_dir=str(out_dir),
        formats=("pdf", "png"),
    )
    plt.close(fig)


def make_upset_plot(out_dir: Path) -> None:
    """Render the same 5-set data as an UpSetPlot.

    UpSetPlot solves the area-proportionality problem that a 5-ellipse
    Venn can't: each intersection is shown as a bar whose height is
    the number of proteins in exactly that combination of DBs.
    Standard alternative for ≥4 sets in genomics.
    """

    setup_plotting_style(style="white", context="notebook", font_scale=1.0)
    sets = build_sets(Path("data/processed/candidate_universe/candidate_universe.tsv"))

    # upsetplot expects a pandas series indexed by a categorical
    # boolean MultiIndex (one boolean column per set, one row per
    # protein). Construct that from the universe TSV.
    all_accs = sorted(set().union(*sets.values()))
    rows = []
    for acc in all_accs:
        rows.append({label: acc in sets[label] for label in sets})
    df = pd.DataFrame(rows, index=all_accs).astype(bool)
    # from_indicators turns a wide boolean DataFrame into the multi-index
    # categorical series upsetplot wants.
    data = upsetplot.from_indicators(list(sets.keys()), data=df)

    fig = plt.figure(figsize=(14, 7))
    upset = upsetplot.UpSet(
        data,
        subset_size="count",
        sort_by="cardinality",
        sort_categories_by="cardinality",
        facecolor=CATEGORICAL_PALETTE[0],
    )
    upset.plot(fig=fig)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig,
        filename="db_overlap_upset",
        output_dir=str(out_dir),
        formats=("pdf", "png"),
    )
    plt.close(fig)


def main() -> None:
    # Default output dir tracks the "final" rendering folder so a venn
    # regenerate doesn't drift back into the staging dir. Override via
    # the VENN_OUT_DIR env var.
    out_dir = Path(os.environ.get(
        "VENN_OUT_DIR", "data/analysis/triage_bench_final"
    ))
    make_plot(out_dir)
    make_upset_plot(out_dir)


if __name__ == "__main__":
    main()
