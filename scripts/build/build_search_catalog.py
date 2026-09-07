"""Emit the agent search catalog the /prompts page documents.

The deep dive runs **two** plan_trim_select literature agents over every
gene, each with its own deterministic search floor (there is no LLM planner
anymore — a fixed kickoff template emits the searches):

  * **Surface-evidence agent (A1)** — "HOW the surface call was made". Runs
    the method-centric ``evidence_retrieval`` categories plus structure /
    topology.
  * **Biology agent (A2)** — "WHERE / WHEN the protein reaches the surface".
    Runs the biology-leaning subset and SKIPS A1's method-only extras.

Both share the literature baselines (``gene2pubmed`` + ``recent_corpus``) and
a set of shared topic_search axes; the selector may pull follow-up
``fetch_abstract`` / ``fetch_fulltext`` reads.

Single source of truth: this script reads the **live deterministic kickoff**
(``build_a1_kickoff`` / ``build_a2_kickoff``) for each agent's categories +
topic searches, and ``evidence_retrieval._CATEGORY_SPECS`` for the assay
query previews — so the catalog can't drift from what the agents actually
run. Only the human-readable per-category "what it finds" copy
(``CATEGORY_DOCS``) is hand-curated; a new category with no entry raises.

Writes ``viewer/lib/search-catalog.json``, imported by the /prompts page at
SSG time and rendered as the "Searches the agents run" section.

Run::

    uv run python scripts/build_search_catalog.py

Regenerate after changing the evidence_retrieval categories, the
gene_literature topic anchors, or the kickoff templates.
"""

from __future__ import annotations

import json
from pathlib import Path

from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
    build_a1_kickoff,
    build_a2_kickoff,
)
from accessible_surfaceome.tools.evidence_retrieval import _CATEGORY_SPECS
from accessible_surfaceome.tools.gene_literature import _TOPIC_TERMS

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "viewer" / "lib" / "search-catalog.json"

# Topology that fires the membrane+ECD-gated standing axes, so the catalog
# documents the full search set a surface-accessible target gets.
_KICKOFF_TMH, _KICKOFF_ECD = 1, 600

# Reader-facing names + one-line "what it finds" for each evidence_retrieval
# assay category. Keyed on the canonical category id (the _CATEGORY_SPECS
# keys); a missing key here raises in main() — a category was added to the
# tool without a description; add the entry so the docs stay complete.
CATEGORY_DOCS: dict[str, dict[str, str]] = {
    "flow_cytometry": {
        "label": "Flow cytometry / FACS",
        "finds": "Surface staining of intact, non-permeabilized cells — "
        "the strongest direct surface-accessibility signal. Includes "
        "overexpression / transfected-cell readouts.",
    },
    "ihc": {
        "label": "Immunohistochemistry",
        "finds": "Membranous IHC staining in primary tissue sections.",
    },
    "if": {
        "label": "Immunofluorescence",
        "finds": "Non-permeabilized surface IF, plus permeabilized confocal "
        "IF that colocalizes with a plasma-membrane marker. Includes "
        "overexpression / transfected-cell readouts.",
    },
    "surface_biotinylation": {
        "label": "Surface biotinylation",
        "finds": "Sulfo-NHS-biotin labeling of the cell surface + "
        "streptavidin pull-down — biochemical surface capture. Includes "
        "overexpression / transfected-cell readouts.",
    },
    "mass_spec_surfaceome": {
        "label": "Surfaceome mass spec",
        "finds": "Cell-surface-capture / surfaceome LC-MS/MS proteomics "
        "(the high-throughput membership datasets).",
    },
    "shedding": {
        "label": "Ectodomain shedding / soluble form",
        "finds": "Sheddase-mediated ectodomain release (ADAM/BACE/MMP) and "
        "soluble/shed form measured in serum, plasma, or supernatant — the "
        "shed_form + secreted_form (decoy) signal.",
    },
    "surface_expression": {
        "label": "Surface expression (context-tagged)",
        "finds": "Assay-less, location-tagged surface-expression mentions "
        "the method categories miss — e.g. \"expressed on the surface of "
        "activated T cells\" or \"surface levels elevated in hepatocytes\". "
        "Surface/membrane token paired with a tissue, cell-type, or "
        "expression-level cue (never bare \"surface\").",
    },
    "overexpression": {
        "label": "Overexpression surface-trafficking",
        "finds": "Papers showing the protein reaches the cell surface when "
        "over-expressed / ectopically / heterologously expressed — a "
        "surface-capability signal, host-agnostic and detection-method-"
        "independent.",
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
        "finds": "Catch-all: radioligand / GPCR pharmacology, proximity "
        "labeling (APEX2/TurboID/BioID), internalization kinetics.",
    },
}

# Literature baselines BOTH agents always run (kickoff gene_literature modes).
SHARED_BASELINES = [
    {
        "id": "gene2pubmed",
        "label": "NCBI gene2pubmed",
        "finds": "NCBI's curated gene→PMID list — the high-precision "
        "baseline every gene starts from.",
    },
    {
        "id": "recent_corpus",
        "label": "Recent corpus (PubTator)",
        "finds": "Date-sorted PubTator entity sweep, pre-filtered on "
        "surface/membrane keywords — catches recent verdict-shifting "
        "papers no keyword-anchored query would surface.",
    },
]

# Selector-requested follow-ups — not part of the deterministic floor; the
# selector pulls these when the trimmed menu has an obvious gap.
SELECTOR_FOLLOWUPS = [
    {
        "id": "fetch_abstract",
        "label": "Fetch abstract",
        "finds": "The selector pulls a specific PMID's abstract as a "
        "follow-up when the candidate menu has a gap.",
    },
    {
        "id": "fetch_fulltext",
        "label": "Fetch full text",
        "finds": "The selector pulls a PMC open-access full text for a deep "
        "read of a known method (A1) or biology / atlas (A2) source.",
    },
]

# Human-readable tagline per focus; the search lists themselves are derived
# live from the kickoff below.
_AGENT_META = {
    "a1": {
        "label": "Surface-evidence agent (A1)",
        "tagline": "How the surface call was made — the methodology ledger.",
    },
    "a2": {
        "label": "Biology agent (A2)",
        "tagline": "Where & when the protein reaches the surface — tissue, "
        "cell type, localization, and what gates it.",
    },
}


def _first_clause(spec: object) -> str:
    """The human-readable first query clause of a _CategorySpec — the
    primary phrase the assay query searches on."""
    clauses = getattr(spec, "query_clauses", None) or ()
    return clauses[0] if clauses else ""


def _categories_in(plan) -> list[str]:
    return [s.category for s in plan.searches if s.tool == "evidence_retrieval"]


def _topic_panels(plan) -> list[dict[str, str]]:
    """Each topic_search the kickoff emits → {label, finds} where finds is the
    OR-set of Europe PMC terms the anchors expand to."""
    panels: list[dict[str, str]] = []
    for s in plan.searches:
        if s.tool != "gene_literature" or s.mode != "topic_search" or not s.anchors:
            continue
        terms = sorted({t for a in s.anchors for t in _TOPIC_TERMS.get(a, [])})
        panels.append(
            {
                "label": " + ".join(s.anchors),
                "finds": ", ".join(terms),
            }
        )
    return panels


def build_catalog() -> dict:
    """Assemble the search-catalog dict (pure — no file write). The drift-guard
    test (tests/test_search_catalog_current.py) imports this and asserts the
    committed JSON matches, so a kickoff/category change can't leave it stale."""
    missing = [k for k in _CATEGORY_SPECS if k not in CATEGORY_DOCS]
    if missing:
        raise SystemExit(
            f"evidence_retrieval categories missing a doc entry: {missing}. "
            "Add them to CATEGORY_DOCS so the /prompts catalog stays complete."
        )

    categories: dict[str, dict[str, str]] = {
        cat_id: {
            "id": cat_id,
            "label": CATEGORY_DOCS[cat_id]["label"],
            "finds": CATEGORY_DOCS[cat_id]["finds"],
            "query_preview": _first_clause(spec),
        }
        for cat_id, spec in _CATEGORY_SPECS.items()
    }

    a1 = build_a1_kickoff(_KICKOFF_TMH, _KICKOFF_ECD)
    a2 = build_a2_kickoff(_KICKOFF_TMH, _KICKOFF_ECD)
    a1_cats, a2_cats = _categories_in(a1), _categories_in(a2)

    agents = [
        {
            "id": "a1",
            **_AGENT_META["a1"],
            "always_category_ids": a1_cats,
            # A1 runs everything A2 does plus the method-only extras.
            "skip_category_ids": [c for c in a2_cats if c not in a1_cats],
            "conditional_note": "Deterministic kickoff — every search above "
            "runs for every gene (no LLM planner).",
            "always_topic": _topic_panels(a1),
        },
        {
            "id": "a2",
            **_AGENT_META["a2"],
            "always_category_ids": a2_cats,
            # Categories A1 runs that A2 leaves to the surface-evidence pass.
            "skip_category_ids": [c for c in a1_cats if c not in a2_cats],
            "conditional_note": "Deterministic kickoff — every search above "
            "runs for every gene (no LLM planner).",
            "always_topic": _topic_panels(a2),
        },
    ]

    return {
        "_generated_by": "scripts/build_search_catalog.py",
        "_source": "evidence_retrieval._CATEGORY_SPECS + the live deterministic "
        "kickoff (plan_trim_select/kickoff_templates.build_a1/a2_kickoff)",
        "categories": categories,
        "shared_baselines": SHARED_BASELINES,
        "agents": agents,
        "planned_fill": SELECTOR_FOLLOWUPS,
    }


def main() -> int:
    catalog = build_catalog()
    OUT_PATH.write_text(json.dumps(catalog, indent=2) + "\n")
    agents = catalog["agents"]
    print(
        f"wrote {OUT_PATH.relative_to(REPO_ROOT)} — "
        f"{len(catalog['categories'])} assay categories, "
        f"{len(catalog['shared_baselines'])} shared baselines, "
        f"{len(agents)} agents "
        f"(A1 {len(agents[0]['always_category_ids'])} assays + "
        f"{len(agents[0]['always_topic'])} topic searches, "
        f"A2 {len(agents[1]['always_category_ids'])} assays + "
        f"{len(agents[1]['always_topic'])} topic searches), "
        f"{len(catalog['planned_fill'])} selector follow-ups"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
