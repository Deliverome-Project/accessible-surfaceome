"""Emit the agent search catalog the /prompts page documents.

The deep-dive runs **two** plan_trim_select literature agents over every
gene, each with its own mandated search floor:

  * **A1 — surface evidence** ("HOW the surface call was made"). Its
    planner prompt mandates all five method-centric ``evidence_retrieval``
    categories plus the literature baselines.
  * **A2 — biological context** ("WHERE / WHEN the protein reaches the
    surface"). Its planner prompt mandates a *different* always-run set —
    ``ihc`` flagship, ``if`` + ``flow_cytometry`` + ``mass_spec_surfaceome``
    for the localization output, a normal-tissue tox panel across six
    organs, and a subcellular-localization-depth sweep — and explicitly
    SKIPS the method-only categories A1 owns.

Both agents also run the same two literature baselines (``gene2pubmed``,
``recent_corpus``) and may emit planner-composed fill (extra
``topic_search`` / ``fetch_abstract`` / ``fetch_fulltext``).

Two sources of truth, deliberately:

  * The **category set + query previews** are imported from
    ``evidence_retrieval._CATEGORY_SPECS`` — so the docs can't drift from
    the actual assay queries, and a new category with no description here
    raises rather than silently dropping.
  * The **per-agent always / conditional / skip designations and the A2
    biology topic panels** are prose in the two planner prompts
    (``plan_trim_select/prompts/{a1,a2}_plan_system.md``). They're encoded
    below as an explicit mapping with the citing prompt section noted on
    each entry, the same kept-in-step convention used for the literature
    modes. Re-read those prompts after editing them and update here.

Writes ``viewer/lib/search-catalog.json``, which the prompts page imports
at SSG time and renders as the "Searches the agents run" section under the
plan_trim_select group.

Run::

    uv run python scripts/build_search_catalog.py

Regenerate after changing the evidence_retrieval categories, the
gene_literature modes, or the A1/A2 planner always-run mandates.
"""

from __future__ import annotations

import json
from pathlib import Path

from accessible_surfaceome.tools.evidence_retrieval import _CATEGORY_SPECS

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "viewer" / "lib" / "search-catalog.json"

# Reader-facing names + one-line "what it finds" for each evidence_retrieval
# assay category. Keyed on the canonical category id (the _CATEGORY_SPECS
# keys); a missing key here raises in main() — a category was added to the
# tool without a description; add the entry so the docs stay complete.
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

# Literature baselines BOTH agents are told to always include
# (a1_plan_system.md §"A1-specific planning bias" items 5-6;
#  a2_plan_system.md §"A2-specific planning bias" items 7-8).
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

# Planner-composed fill — emitted on top of the always-run floor when the
# gene context warrants it. NOT guaranteed per gene (the planner LLM
# chooses), so these are the genuinely non-deterministic searches.
PLANNED_FILL = [
    {
        "id": "topic_search_extra",
        "label": "Topic search (extra)",
        "finds": "Additional Europe PMC topic-anchored queries the planner "
        "composes beyond the mandated panels, to fill gene-specific gaps.",
    },
    {
        "id": "fetch_abstract",
        "label": "Fetch abstract",
        "finds": "Pull a single PMID's abstract (planner-chosen follow-up).",
    },
    {
        "id": "fetch_fulltext",
        "label": "Fetch full text",
        "finds": "Pull a PMC open-access full text — planner-chosen deep "
        "read of a known method (A1) or biology / atlas (A2) source.",
    },
]

# Per-agent always-run mandate. Sourced from the two planner prompts:
#   A1 → a1_plan_system.md §"A1-specific planning bias" (items 1-8)
#   A2 → a2_plan_system.md §"A2-specific planning bias" (items 1-9)
#        + §"Normal-tissue tox panel (ALWAYS)".
# `always_category_ids` = evidence_retrieval categories the prompt says to
# run for every gene. `skip_category_ids` = categories the prompt tells the
# agent to leave to the other pass (rendered as an explicit "skips" note so
# a reader sees the division of labor). `always_topic` = mandated
# topic_search panels unique to this agent.
AGENT_PLANS = [
    {
        "id": "a1",
        "label": "A1 · Surface evidence",
        "tagline": "How the surface call was made — the methodology ledger.",
        # a1_plan_system.md item 1: "Always run all 5 method-centric
        # evidence_retrieval categories".
        "always_category_ids": [
            "flow_cytometry",
            "surface_biotinylation",
            "mass_spec_surfaceome",
            "ihc",
            "if",
        ],
        "skip_category_ids": [],
        # a1 items 2-4: structure_with_ecd / western_blot_paired / other are
        # gene-class conditional, not unconditional.
        "conditional_note": "Adds western blot (surface-paired) when cheap, "
        "structure-with-ECD when UniProt lists experimental structures or "
        "signal peptides, and 'other' for the gene class it fits (e.g. "
        "radioligand pharmacology for 7-TM GPCRs).",
        # a1 item 8: method-anchored topic_search.
        "always_topic": [
            {
                "label": "Method-anchored topic search",
                "finds": "Europe PMC queries anchored on flow cytometry / "
                "surface biotinylation / mass-spec / IHC — the methods "
                "that produce a defensible surface call.",
            },
        ],
    },
    {
        "id": "a2",
        "label": "A2 · Biological context",
        "tagline": "Where & when the protein reaches the surface — tissue, "
        "cell type, localization, and what gates it.",
        # a2 items 1-4: ihc (flagship), if + flow_cytometry, mass_spec.
        "always_category_ids": [
            "ihc",
            "if",
            "flow_cytometry",
            "mass_spec_surfaceome",
        ],
        # a2 item 6: western_blot_paired + structure_with_ecd are "A1
        # territory. SKIP."
        "skip_category_ids": ["western_blot_paired", "structure_with_ecd"],
        # a2 item 5: surface_biotinylation is borderline / conditional.
        "conditional_note": "Adds surface biotinylation when UniProt lists "
        "multiple compartments (a dual-localization or stress-induced "
        "surface-fraction tell).",
        "always_topic": [
            # a2 §"Normal-tissue tox panel (ALWAYS — surface expression only)".
            {
                "label": "Normal-tissue tox panel",
                "finds": "Surface expression in the six high-consequence "
                "tox organs — liver, lung, kidney, GI tract, heart, brain "
                "(incl. BBB). Runs for every gene, even canonical "
                "receptors; negatives count.",
            },
            # a2 item 3: subcellular-localization depth.
            {
                "label": "Subcellular-localization depth",
                "finds": "Organelle colocalization (ER / Golgi / endosome / "
                "lysosome markers) + fractionation that quantifies the "
                "surface-vs-intracellular split — fills dual_localization "
                "and its fraction estimate.",
            },
            # a2 item 9: biology-leaning anchors.
            {
                "label": "Biology-leaning topic search",
                "finds": "Anchored on surface_expression / shedding / PTM / "
                "IHC — pulls the tissue-distribution and disease-state "
                "biology reviews A1 deliberately avoids.",
            },
        ],
    },
]


def _first_clause(spec: object) -> str:
    """The human-readable first query clause of a _CategorySpec — the
    primary phrase the assay query searches on."""
    clauses = getattr(spec, "query_clauses", None) or ()
    return clauses[0] if clauses else ""


def main() -> int:
    missing = [k for k in _CATEGORY_SPECS if k not in CATEGORY_DOCS]
    if missing:
        raise SystemExit(
            f"evidence_retrieval categories missing a doc entry: {missing}. "
            "Add them to CATEGORY_DOCS so the /prompts catalog stays complete."
        )

    # category id -> {label, finds, query_preview}; the per-agent plans
    # reference these by id so a category's copy lives in exactly one place.
    categories: dict[str, dict[str, str]] = {}
    for cat_id, spec in _CATEGORY_SPECS.items():
        doc = CATEGORY_DOCS[cat_id]
        categories[cat_id] = {
            "id": cat_id,
            "label": doc["label"],
            "finds": doc["finds"],
            "query_preview": _first_clause(spec),
        }

    # Validate the per-agent id references against the canonical category set
    # so a renamed/removed category can't leave a dangling reference.
    known = set(categories)
    for plan in AGENT_PLANS:
        bad = [
            c
            for c in (*plan["always_category_ids"], *plan["skip_category_ids"])
            if c not in known
        ]
        if bad:
            raise SystemExit(
                f"agent {plan['id']!r} references unknown categories {bad}; "
                "fix AGENT_PLANS to match _CATEGORY_SPECS."
            )

    catalog = {
        "_generated_by": "scripts/build_search_catalog.py",
        "_source": "evidence_retrieval._CATEGORY_SPECS + "
        "plan_trim_select/prompts/{a1,a2}_plan_system.md",
        "categories": categories,
        "shared_baselines": SHARED_BASELINES,
        "agents": AGENT_PLANS,
        "planned_fill": PLANNED_FILL,
    }
    OUT_PATH.write_text(json.dumps(catalog, indent=2) + "\n")

    print(
        f"wrote {OUT_PATH.relative_to(REPO_ROOT)} — "
        f"{len(categories)} assay categories, {len(SHARED_BASELINES)} shared "
        f"baselines, {len(AGENT_PLANS)} agents "
        f"(A1 {len(AGENT_PLANS[0]['always_category_ids'])} always-assays, "
        f"A2 {len(AGENT_PLANS[1]['always_category_ids'])} always-assays + "
        f"{len(AGENT_PLANS[1]['always_topic'])} biology topic panels), "
        f"{len(PLANNED_FILL)} planner-fill modes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
