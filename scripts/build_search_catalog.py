"""Emit the agent search catalog the /prompts page documents.

The deep-dive literature agents (A1 surface-evidence, A2 biology-context)
run two kinds of searches per gene:

  * **Deterministic sweeps** — fixed queries that run for EVERY gene,
    independent of what the LLM plans:
      - ``gene_literature`` baseline modes (gene2pubmed, recent_corpus)
      - one ``evidence_retrieval`` query per assay category
        (flow_cytometry, ihc, if, surface_biotinylation,
        mass_spec_surfaceome, western_blot_paired, structure_with_ecd,
        other).
  * **LLM-planned** — topic queries the planner chooses
    (topic_search, fetch_abstract, fetch_fulltext).

This script reads the CANONICAL definitions straight from the tool
modules (``evidence_retrieval._CATEGORY_SPECS`` and the
``gene_literature`` mode list) so the /prompts documentation can't drift
from what the agents actually run. It writes
``viewer/lib/search-catalog.json``, which the prompts page imports at
SSG time and renders as the "Searches the agents run" section under the
plan_trim_select group.

Run::

    uv run python scripts/build_search_catalog.py

Regenerate after changing the evidence_retrieval categories or the
gene_literature modes. CI / a reviewer can diff the committed JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

from accessible_surfaceome.tools.evidence_retrieval import _CATEGORY_SPECS

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "viewer" / "lib" / "search-catalog.json"

# Reader-facing names + one-line "what it finds" for each evidence_retrieval
# assay category. Keyed on the canonical category id (the _CATEGORY_SPECS
# keys); a KeyError here means a category was added to the tool without a
# description — fix it by adding the entry, so the docs stay complete.
CATEGORY_DOCS: dict[str, dict[str, str]] = {
    "flow_cytometry": {
        "label": "Flow cytometry / FACS",
        "finds": "Surface staining of intact, non-permeabilized cells — "
        "the strongest direct surface-accessibility signal.",
    },
    "ihc": {
        "label": "Immunohistochemistry",
        "finds": "Membranous IHC staining in primary tissue sections.",
    },
    "if": {
        "label": "Immunofluorescence",
        "finds": "Non-permeabilized surface IF, plus permeabilized confocal "
        "IF that colocalizes with a plasma-membrane marker.",
    },
    "surface_biotinylation": {
        "label": "Surface biotinylation",
        "finds": "Sulfo-NHS-biotin labeling of the cell surface + "
        "streptavidin pull-down — biochemical surface capture.",
    },
    "mass_spec_surfaceome": {
        "label": "Surfaceome mass spec",
        "finds": "Cell-surface-capture / surfaceome LC-MS/MS proteomics "
        "(the high-throughput membership datasets).",
    },
    "western_blot_paired": {
        "label": "Western blot (surface-paired)",
        "finds": "Immunoblot paired with a surface-biotinylation or "
        "membrane-fraction step (so the band is the surface pool).",
    },
    "structure_with_ecd": {
        "label": "Structure with ECD",
        "finds": "Crystal / cryo-EM structures resolving an extracellular "
        "domain — confirms an exposed, foldable ectodomain.",
    },
    "other": {
        "label": "Other surface assays",
        "finds": "Catch-all: radioligand / GPCR pharmacology, ectodomain "
        "shedding, proximity labeling (APEX2/TurboID/BioID), "
        "internalization kinetics.",
    },
}

# The gene_literature modes, split by determinism. Sourced from the
# gene_literature module docstring (kept in step manually — these 5 modes
# are stable; the assay categories are the part that grows).
LITERATURE_MODES = [
    {
        "id": "gene2pubmed",
        "label": "NCBI gene2pubmed",
        "deterministic": True,
        "finds": "NCBI's curated gene→PMID list — the high-precision "
        "baseline every gene starts from.",
    },
    {
        "id": "recent_corpus",
        "label": "Recent corpus (PubTator)",
        "deterministic": True,
        "finds": "Date-sorted PubTator entity sweep, pre-filtered on "
        "surface/membrane keywords — catches recent verdict-shifting "
        "papers the planner couldn't keyword-anchor.",
    },
    {
        "id": "topic_search",
        "label": "Topic search",
        "deterministic": False,
        "finds": "Europe PMC topic-anchored queries the planner composes "
        "to fill method-specific gaps.",
    },
    {
        "id": "fetch_abstract",
        "label": "Fetch abstract",
        "deterministic": False,
        "finds": "Pull a single PMID's abstract (planner-chosen follow-up).",
    },
    {
        "id": "fetch_fulltext",
        "label": "Fetch full text",
        "deterministic": False,
        "finds": "Pull a PMC open-access full text (planner-chosen "
        "deep read).",
    },
]


def _first_clause(spec: object) -> str:
    """The human-readable first query clause of a _CategorySpec — the
    primary phrase the assay query searches on."""
    clauses = getattr(spec, "query_clauses", None) or ()
    return clauses[0] if clauses else ""


def main() -> int:
    categories = []
    missing = [k for k in _CATEGORY_SPECS if k not in CATEGORY_DOCS]
    if missing:
        raise SystemExit(
            f"evidence_retrieval categories missing a doc entry: {missing}. "
            "Add them to CATEGORY_DOCS so the /prompts catalog stays complete."
        )
    for cat_id, spec in _CATEGORY_SPECS.items():
        doc = CATEGORY_DOCS[cat_id]
        categories.append(
            {
                "id": cat_id,
                "label": doc["label"],
                "finds": doc["finds"],
                "deterministic": True,  # every category runs per gene
                "query_preview": _first_clause(spec),
            }
        )

    catalog = {
        "_generated_by": "scripts/build_search_catalog.py",
        "_source": "evidence_retrieval._CATEGORY_SPECS + gene_literature modes",
        "evidence_retrieval_categories": categories,
        "literature_modes": LITERATURE_MODES,
    }
    OUT_PATH.write_text(json.dumps(catalog, indent=2) + "\n")
    n_det = len(categories) + sum(1 for m in LITERATURE_MODES if m["deterministic"])
    n_planned = sum(1 for m in LITERATURE_MODES if not m["deterministic"])
    print(
        f"wrote {OUT_PATH.relative_to(REPO_ROOT)} — "
        f"{len(categories)} assay categories, {len(LITERATURE_MODES)} lit modes "
        f"({n_det} deterministic, {n_planned} LLM-planned)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
