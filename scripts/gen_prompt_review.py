#!/usr/bin/env python3
"""Review HTML: full prompt md shown always, with the diff vs main highlighted inline."""
from __future__ import annotations
import html
import re
import subprocess
import typing
from pathlib import Path

from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
    build_a1_kickoff, build_a2_kickoff,
)
from accessible_surfaceome.tools._shared import models as _models
from accessible_surfaceome.tools.gene_literature import _TOPIC_TERMS

NEW_ANCHORS = {"normal_tissue_expression", "surface_reachability",
               "partner_dependency", "membrane_subdomain", "epitope_masking"}
GATED = {"surface_reachability", "partner_dependency", "membrane_subdomain",
         "epitope_masking"}


def render_kickoff(label, sub, plan):
    cats = [s.category for s in plan.searches if s.tool == "evidence_retrieval"]
    modes = [s.mode for s in plan.searches
             if s.tool == "gene_literature" and s.mode in ("gene2pubmed", "recent_corpus")]
    topics = [s for s in plan.searches
              if s.tool == "gene_literature" and s.mode == "topic_search"]
    catrow = "".join(f'<span class="catchip">{html.escape(c)}</span>' for c in cats)
    moderow = "".join(f'<span class="catchip mode">{html.escape(m)}</span>' for m in modes)
    rows = []
    for s in topics:
        anc = s.anchors or []
        badge = ""
        for a in anc:
            if a in NEW_ANCHORS:
                badge += f'<span class="b new">new{"·gated" if a in GATED else ""}</span>'
        terms = sorted({t for a in anc for t in _TOPIC_TERMS.get(a, [])})
        rows.append(
            f'<div class="trow"><div class="tanc"><code>{" + ".join(anc)}</code>{badge}</div>'
            f'<div class="tterms">{", ".join(html.escape(t) for t in terms)}</div></div>'
        )
    return f"""<div class="kcol">
      <h3>{label} <span class="kn">{len(plan.searches)} searches · {sub}</span></h3>
      <div class="ksub">evidence_retrieval — methodology categories</div>
      <div class="catrow">{catrow}{moderow}</div>
      <div class="ksub">gene_literature — topic_search keyword groups</div>
      {''.join(rows)}
    </div>"""


def kickoff_section():
    a1 = render_kickoff("A1", "surface evidence", build_a1_kickoff(1, 600))
    a2 = render_kickoff("A2", "biological context", build_a2_kickoff(1, 600))
    return f"""<section class="kick">
      <h2>Retrieval — search terms feeding each agent</h2>
      <p class="sub2">Deterministic kickoff (no LLM planner). <span class="b new">new</span> = added in this PR;
      <code>·gated</code> = emitted only for membrane+ECD (or unknown) topology. The <code>flow_cytometry</code>
      category query also gained host-agnostic OE terms (<i>transfected / ectopic / heterologous / overexpressing /
      stably&nbsp;expressing</i>, no "wild-type"), and <code>shedding</code> gained serum/plasma/circulating terms.</p>
      <div class="kgrid">{a1}{a2}</div>
    </section>"""


# ---- Closed-enum reference -------------------------------------------------
# The structured-output options the model must choose from, introspected live
# from models.py so the review never drifts from the shipped schema. Each
# (EnumName, json-path) is rendered as a chip row; the masking mechanism gets
# the homo / hetero / other axis annotated.
ENUM_GROUPS = [
    ("Accessibility risks", [
        ("EpitopeMaskingMechanism", "epitope_masking.mechanism[]"),
        ("EpitopeMaskingSeverity", "epitope_masking.severity"),
        ("CoreceptorDependency", "co_receptor_requirements.surface_expression_dependency"),
        ("CoreceptorEvidenceBasis", "co_receptor_requirements.evidence_basis"),
        ("SecretedFormSource", "secreted_form.source"),
        ("ECDAccessibilityClass", "ecd_size_assessment.ecd_accessibility_class"),
        ("RestrictedSubdomainName", "restricted_subdomain.domain"),
        ("RiskSeverity", "shed/secreted/restricted severity"),
        ("EvidenceStrength", "every risk · evidence_strength"),
    ]),
    ("Executive summary", [
        ("HeadlineRisk", "executive_summary.headline_risks[]"),
    ]),
]

# homo / hetero / other axis for the masking mechanism options.
MASK_AXIS = {
    "oligomerization": ("homo", "the protein's OWN homodimer / homo-oligomer interface buries the epitope"),
    "partner": ("hetero", "a DIFFERENT protein in a complex covers the epitope"),
    "glycan": ("other", "glycocalyx / glycan shielding"),
    "conformational": ("other", "monomer closed/open occlusion"),
    "cleaved": ("other", "proteolytic removal of the epitope"),
    "none": ("", "no masking documented"),
}


def enum_chip(enum_name: str, val: str) -> str:
    if enum_name == "EpitopeMaskingMechanism":
        axis, desc = MASK_AXIS.get(val, ("", ""))
        if axis:
            return (f'<span class="evchip ev-{axis}" title="{html.escape(axis.upper())} — {html.escape(desc)}">'
                    f'{html.escape(val)}<span class="evaxis">{html.escape(axis)}</span></span>')
    return f'<span class="evchip">{html.escape(val)}</span>'


def enum_section() -> str:
    groups = []
    for title, entries in ENUM_GROUPS:
        rows = []
        for enum_name, field in entries:
            obj = getattr(_models, enum_name, None)
            if obj is None:
                continue
            chips = "".join(enum_chip(enum_name, v) for v in typing.get_args(obj))
            rows.append(
                f'<div class="evrow"><div class="evmeta"><code>{html.escape(field)}</code>'
                f'<span class="evname">{html.escape(enum_name)}</span></div>'
                f'<div class="evchips">{chips}</div></div>'
            )
        groups.append(f'<div class="evgroup"><h3>{html.escape(title)}</h3>{"".join(rows)}</div>')
    return f"""<section class="enums">
      <h2>Closed enums — the options the model must choose from</h2>
      <p class="sub2">Introspected live from <code>models.py</code> (the structured-output schema), so this
      never drifts from what ships. For <code>epitope_masking.mechanism</code> the
      <span class="evaxis ax-homo">homo</span> / <span class="evaxis ax-hetero">hetero</span> axis is annotated
      (everything else is monomer-level / other).</p>
      {''.join(groups)}
    </section>"""


# ---- Deterministic-data flow into each prompt -----------------------------
# Maps each agent group to the DeterministicFeatures fields its prompts
# receive at runtime. Hand-curated from the runtime wiring (NOT introspected,
# because the LLM prompts don't statically reference fields the same way the
# Python schema does — the relevant truth is what gets rendered into the
# system / user message, traced through the runners + kickoff templates).
#
# Source of truth references (paths relative to repo root):
#   * plan_trim_select  — agents/plan_trim_select/runner.py
#                         (_summarize_deterministic_for_planner @ ~L312;
#                          deterministic_summary_json on context @ L302; rendered
#                          into the user message @ L1083-1087).
#   * v2 builders       — agents/surfaceome_v2/orchestrator.py
#                         (a1_ctx / a2_ctx built @ L373-374: only {"gene": ...}).
#   * synthesizer       — surfaceome_synthesizer/prompts/task_template.md
#                         ({{deterministic_features}} placeholder); system.md
#                         references nested paths (e.g. L165-166).
#   * surface_triage    — agents/surface_triage/prompts/task_template.md
#                         (HGNC + NCBI identifier resolution; no topology).
DETERMINISTIC_GROUPS = [
    {
        "group": "plan_trim_select — A1 / A2 search planners",
        "shape": "summarized",
        "prompts": [
            "a1_select_system.md",
            "a1_trim_system.md",
            "a2_select_system.md",
            "a2_trim_system.md",
            "abstract_triage_system.md",
            "select_system.md",
            "trim_system.md",
        ],
        "note": (
            "Receives a JSON-stringified subset via "
            "<code>_summarize_deterministic_for_planner</code> "
            "(runner.py L312). The kickoff is gated on "
            "<code>tm_helix_count</code> + <code>ecd_length_residues</code> "
            "(membrane+ECD-only axes fire when both look real)."
        ),
        "fields": [
            "canonical_topology.tm_helix_count",
            "canonical_topology.n_terminal_orientation",
            "canonical_topology.c_terminal_orientation",
            "canonical_topology.ecd_length_residues",
            "canonical_topology.icd_length_residues",
            "canonical_topology.signal_peptide_length",
            "paralogs[].paralog_symbol  (top 5 by ECD identity)",
            "paralogs[].ecd_pct_identity  (top 5)",
            "paralog_count  (= len(paralogs))",
            "orthologs.mouse[].ortholog_symbol  (canonical)",
            "orthologs.mouse[].ecd_pct_identity_to_human_canonical",
            "orthologs.cynomolgus[].ortholog_symbol  (canonical)",
            "orthologs.cynomolgus[].ecd_pct_identity_to_human_canonical",
            "mouse_ortholog_count  (= len(orthologs.mouse))",
            "cyno_ortholog_count  (= len(orthologs.cynomolgus))",
        ],
    },
    {
        "group": "surfaceome_v2 — 7 of 8 builders (the narrow ones)",
        "shape": "none",
        "prompts": [
            "methods_builder_system.md",
            "contradiction_builder_system.md",
            "expression_builder_system.md",
            "cell_states_builder_system.md",
            "subcellular_localization_builder_system.md",
            "anatomical_accessibility_builder_system.md",
            "accessibility_modulation_builder_system.md",
        ],
        "note": (
            "Receive only <code>{gene: hgnc_symbol}</code> plus the A1 or A2 "
            "claim ledger (orchestrator.py <code>a1_ctx</code> / "
            "<code>a2_ctx</code>). Zero <code>DeterministicFeatures</code> "
            "fields land in these builder prompts &mdash; block extraction "
            "is an LLM operation over claims, not over topology / orthologs "
            "/ structure. <code>evidence_grade</code> is the exception "
            "(see next card)."
        ),
        "fields": [],
    },
    {
        "group": "surfaceome_v2 — evidence_grade builder",
        "shape": "calibration-only",
        "prompts": [
            "evidence_grade_builder_system.md",
        ],
        "note": (
            "Exception to &ldquo;builders see only the gene symbol&rdquo;. "
            "Receives an extended <code>evidence_grade_ctx</code> with the "
            "upstream <code>triage_summary_json</code> + "
            "<code>hgnc_gene_groups</code> + <code>uniprot_family</code>. "
            "The grade verdict is the deep-dive&rsquo;s load-bearing "
            "confidence anchor, so these calibration signals land here even "
            "though other builders stay narrow. Triage is used for "
            "calibration ONLY (don&rsquo;t cite); the family tags anchor "
            "the antibody-cross-reactivity-with-paralog discussion in "
            "<code>grade_rationale</code> + the <code>paralog_decoy</code> "
            "claim stance."
        ),
        "fields": [
            "(no DeterministicFeatures fields)",
            "triage_summary_json  (TriageRecord: verdict, reason, key_uncertainty, confidence)",
            "hgnc_gene_groups  (curator family tags from IdentifierBundle)",
            "uniprot_family  (curator family tag from IdentifierBundle)",
        ],
    },
    {
        "group": "surfaceome_synthesizer (B)",
        "shape": "full",
        "prompts": [
            "system.md",
        ],
        "note": (
            "The <strong>entire</strong> <code>DeterministicFeatures</code> "
            "block (canonical + isoform topology, paralogs, orthologs, "
            "structure, SURFACE-Bind) is summarized to compact JSON via "
            "<code>_summarize_deterministic_for_synthesizer</code> and "
            "rendered into the user message by "
            "<code>synthesizer/runner.py:_build_task()</code> as a "
            "&ldquo;Deterministic features (read-only)&rdquo; section. "
            "<code>task_template.md</code> is a stub left over from the "
            "v1.0.0-stub design &mdash; NOT read at runtime; the real wiring "
            "is procedural in <code>_build_task</code>. "
            "<code>system.md</code>&rsquo;s direct references "
            "(e.g. <code>deterministic_features.canonical_topology"
            ".ecd_length_residues</code> @ L165-166) are now grounded in "
            "something the model can actually read. The synthesizer also "
            "receives curator family tags (<code>hgnc_gene_groups</code> + "
            "<code>uniprot_family</code>) so it can cross-check its own "
            "<code>llm_family</code> call against ground truth at decision "
            "time, rather than discovering the mismatch only when "
            "<code>_attach_deterministic_families</code> overwrites them "
            "post-hoc."
        ),
        "fields": [
            "canonical_topology  (TM count, ECD/ICD len, N/C orientation, signal peptide)",
            "isoform_topologies  (count + checked sentinel)",
            "paralogs  (count + top-5 by ECD identity, each with TM + ECD len)",
            "paralogs_checked  (sentinel)",
            "orthologs.mouse  (count + canonical symbol + ECD identity)",
            "orthologs.cynomolgus  (count + canonical symbol + ECD identity)",
            "structure  (AFDB id, ecd_mean_plddt, ecd_disordered_fraction, model URL flag)",
            "surface_bind  (has_data, n_sites, n_seeds_total/alpha/beta, representative_pdb_id)",
            "homo_oligomerization  (is_homo_oligomer + stoichiometry &mdash; Schweke 2024 AF2 prior on epitope_masking.mechanism)",
            "curator_family_tags.hgnc_gene_groups  (from IdentifierBundle)",
            "curator_family_tags.uniprot_family  (from IdentifierBundle)",
        ],
    },
    {
        "group": "surface_triage",
        "shape": "identifiers-only",
        "prompts": [
            "system.md",
            "system_naive.md",
            "system_pubmed.md",
            "system_web.md",
            "system_web_naive.md",
            "task_template.md",
        ],
        "note": (
            "Triage runs <em>upstream</em> of the topology / paralog / ortholog "
            "fetch, so it sees zero fields from <code>DeterministicFeatures</code>. "
            "It receives identifier-resolution context only (HGNC + NCBI). "
            "Includes <code>hgnc_gene_groups</code> &mdash; deterministic and "
            "curator-assigned, but resolved separately via "
            "<code>resolve_by_hgnc_id</code>, not via the topology pipeline."
        ),
        "fields": [],
    },
]


def deterministic_section() -> str:
    SHAPE_LABEL = {
        "summarized": ("subset", "summarized"),
        "full":       ("full",   "full block"),
        "none":       ("none",   "claim-ledger only"),
        "identifiers-only": ("ids", "identifiers only"),
        "calibration-only": ("calibration-only", "triage + family tags only"),
    }
    cards = []
    for g in DETERMINISTIC_GROUPS:
        badge_class, badge_text = SHAPE_LABEL[g["shape"]]
        prompt_chips = "".join(
            f'<code class="dprompt">{html.escape(p)}</code>' for p in g["prompts"]
        )
        if g["fields"]:
            field_chips = "".join(
                f'<span class="dfield">{html.escape(f)}</span>' for f in g["fields"]
            )
            fields_block = f'<div class="dfields">{field_chips}</div>'
        else:
            fields_block = (
                '<div class="dnone">No <code>DeterministicFeatures</code> '
                'fields reach this prompt.</div>'
            )
        cards.append(f"""
          <div class="dcard">
            <div class="dhead">
              <h3>{html.escape(g["group"])}</h3>
              <span class="dbadge d-{badge_class}">{html.escape(badge_text)}</span>
            </div>
            <div class="dprompts">{prompt_chips}</div>
            <div class="dnote">{g["note"]}</div>
            {fields_block}
          </div>""")
    return f"""<section class="determ">
      <h2>Deterministic data flow &mdash; what each prompt actually receives</h2>
      <p class="sub2">From the runtime wiring: which fields of
      <code>DeterministicFeatures</code> (canonical / isoform topology, orthologs,
      paralogs, structure, SURFACE-Bind) the model can read in each agent's user
      message. The <em>shape</em> badge says how much of the block is exposed:
      <span class="dbadge d-full">full block</span> = the synthesizer gets
      everything; <span class="dbadge d-subset">summarized</span> = the
      plan-trim-select planners get a small JSON snapshot;
      <span class="dbadge d-none">claim-ledger only</span> = builders see only
      the gene symbol + extracted claims; <span class="dbadge d-ids">identifiers
      only</span> = triage runs before topology is even fetched.</p>
      <div class="dgrid">{''.join(cards)}</div>
    </section>"""


# ---- Example flow for a single gene (EGFR) --------------------------------
# Walks the deep-dive pipeline stage-by-stage with the EGFR-shaped data each
# agent sees + emits at that stage. Hand-curated reference, NOT introspected
# at runtime — the goal is "what a reader needs to trace a record from
# cohort row to SurfaceomeRecord", which is fundamentally documentation, not
# generated output. Update when the runtime wiring changes (the source-of-
# truth pointers in DETERMINISTIC_GROUPS double as the update checklist).
EXAMPLE_FLOW_STAGES = [
    {
        "stage": "0 — cohort entry",
        "actor": "build_universe_v2 / cohort row",
        "inputs": ["hgnc_id: HGNC:3236  (canonical stable key)"],
        "process": (
            "Cohort row is the canonical entry. The DB-vote table in "
            "<code>candidate_universe</code> says EGFR landed via 5 of the 5 "
            "surface-source DBs (UniProt-KW, GO-CC, HPA, CSPA, SURFY) &mdash; "
            "no LLM needed."
        ),
        "outputs": [
            "hgnc_symbol: EGFR",
            "uniprot_acc: P00533",
            "ncbi_gene_id: 1956",
            "aliases: ERBB, HER1, mENA",
            "previous_symbols: (none for EGFR)",
            "hgnc_gene_groups: [&ldquo;Erb-b2 receptor tyrosine kinases&rdquo;]",
            "uniprot_family: &ldquo;Protein kinase superfamily&rdquo;",
        ],
    },
    {
        "stage": "1 — surface_triage",
        "actor": "Haiku · system.md + task_template.md",
        "inputs": [
            "hgnc_symbol, uniprot_acc, ncbi_gene_id",
            "aliases, previous_symbols",
            "hgnc_gene_groups, cd_designation",
            "ncbi_summary  (NCBI&rsquo;s curated functional summary)",
        ],
        "process": (
            "First-pass alarm-clock judgment: is this a surface protein worth "
            "deep-diving? Pure identifier + summary input &mdash; runs upstream "
            "of any deterministic topology fetch."
        ),
        "outputs": [
            "verdict: &ldquo;likely&rdquo;",
            "reason: &ldquo;classical_surface_receptor&rdquo;",
            "verdict_reasoning: &ldquo;EGFR is the canonical single-pass type I "
            "receptor tyrosine kinase &hellip;&rdquo;",
            "key_uncertainty: (often empty for canonical receptors)",
            "confidence: &ldquo;high&rdquo;",
        ],
    },
    {
        "stage": "2 — plan_trim_select (A1 + A2)",
        "actor": "Sonnet · a1_select / a1_trim / a2_select / a2_trim / abstract_triage",
        "inputs": [
            "Triage prior  (the stage-1 record above, via _summarize_triage_for_planner)",
            "deterministic_summary_json  (canonical topology + paralogs + orthologs)",
            "Kickoff search terms  (deterministic; tox_panel + reachability + co_receptor + subdomain anchors)",
        ],
        "process": (
            "Runs the deterministic kickoff (tox-panel + membrane+ECD-gated "
            "axes), iterates the planner / trim / select loop over PubMed + "
            "Europe PMC + PubTator, and lands a deduplicated ledger of "
            "<code>EvidenceClaim</code>s plus the search-log audit trail. "
            "Topic searches now OR over <code>aliases</code> + "
            "<code>previous_symbols</code> so renamed genes don&rsquo;t drop "
            "pre-rename literature."
        ),
        "outputs": [
            "a1_claims  (~50&ndash;80 surface-evidence claims for EGFR)",
            "a2_claims  (~30&ndash;60 biological-context claims for EGFR)",
            "search_log  (every PubMed / EuropePMC / PubTator query + count)",
        ],
    },
    {
        "stage": "3 — fetch_deterministic_features  (was post-pass; now pre-synthesizer)",
        "actor": "D1 + AFDB + PDBe SIFTS + SURFACE-Bind (no LLM)",
        "inputs": [
            "uniprot_acc: P00533",
        ],
        "process": (
            "Tool pull (no LLM): DeepTMHMM topology from public D1, "
            "Compara paralog + cross-species ortholog rows from D1, AFDB "
            "structure metrics from the AlphaFold DB API, SURFACE-Bind "
            "sites from the checked-in JSON, representative experimental "
            "PDB from PDBe SIFTS <code>best_structures</code>. Falls back "
            "to a labeled stub if D1 is unreachable. <strong>Moved before "
            "step 4&rsquo;s synthesizer call so B can read the real topology "
            "thresholds the system prompt references.</strong>"
        ),
        "outputs": [
            "canonical_topology  (TM=1, ECD&asymp;620, ICD&asymp;542, sigP=24, N=extracellular)",
            "isoform_topologies  (4 isoforms; 3 with full topology rows)",
            "paralogs  (HER2 / HER3 / HER4 + 28 more, ECD identity 36&ndash;82%)",
            "orthologs  (mouse Egfr 88% ECD identity; cyno EGFR 99%)",
            "structure  (AFDB AF-P00533-F1 pLDDT 92.4; experimental PDB 5SX4)",
            "surface_bind  (n_sites=4, n_seeds_total=1287, alpha=812, beta=475)",
            "homo_oligomerization  (Schweke 2024 AF2 prior; is_homo_oligomer + cyclic stoichiometry N when present)",
        ],
    },
    {
        "stage": "4 — 8 block builders (parallel)",
        "actor": "Sonnet · methods_builder / contradictions_builder / etc.",
        "inputs": [
            "a1_claims OR a2_claims  (per-builder slice)",
            "a1_ctx = {gene: EGFR}  (or a2_ctx — narrow by design)",
            "<strong>evidence_grade only:</strong> evidence_grade_ctx adds triage_summary + hgnc_gene_groups + uniprot_family",
        ],
        "process": (
            "Eight independent block builders fan out in parallel: 4 on the "
            "A1 (surface-evidence) side &mdash; methods, contradictions, "
            "evidence_grade, evidence_grade also gets calibration context as "
            "of this PR &mdash; and 4 on the A2 (biological-context) side: "
            "expression, cell_states, subcellular_localization, "
            "anatomical_accessibility, accessibility_modulation. Each one "
            "extracts a structured block out of its claim slice; the "
            "extracted block embeds <code>(a1_evi_NN)</code> / "
            "<code>(a2_evi_NN)</code> cites back into the ledger."
        ),
        "outputs": [
            "SurfaceEvidence  (methods + non_surface_expression + evidence_grade + claim_stances + contradictions)",
            "BiologicalContext  (expression + cell_states + subcellular_localization + anatomical + modulation)",
        ],
    },
    {
        "stage": "5 — surfaceome_synthesizer (B)",
        "actor": "Sonnet · system.md  (tool-less Messages call)",
        "inputs": [
            "Triage prior  (_summarize_triage_for_planner)",
            "<strong>NEW — Deterministic features (read-only)</strong>  (_summarize_deterministic_for_synthesizer)",
            "<strong>NEW — curator_family_tags</strong>  (hgnc_gene_groups + uniprot_family from IdentifierBundle)",
            "SurfaceEvidenceDraft  (A1 block + ledger slice)",
            "BiologicalContextDraft  (A2 block + ledger slice, when present)",
            "SynthesizerDraft JSON schema",
        ],
        "process": (
            "Single-shot, tool-less Messages-API call (with a small repair "
            "loop). B integrates A1 + A2 into a <code>SynthesizerDraft</code> "
            "&mdash; emits the executive_summary, filters rollups, "
            "accessibility_risks, confidence + confidence_reasoning. With "
            "the new deterministic block in the user message, threshold "
            "calls against <code>ecd_length_residues</code> + the paralog "
            "cross-reactivity discussion are now grounded in real numeric "
            "input."
        ),
        "outputs": [
            "executive_summary  (surface_accessibility=&ldquo;high&rdquo;, llm_family=&ldquo;receptor&rdquo;, &hellip;)",
            "filters_llm  (4 LLM rollup chips: expression_level/breadth, surface_specificity, has_known_ligand)",
            "accessibility_risks  (per-risk present/severity/cited_evidence_ids)",
            "confidence + confidence_reasoning  (anchors on the triage prior + deterministic data)",
        ],
    },
    {
        "stage": "6 — post-passes  (deterministic)",
        "actor": "orchestrator post-pass helpers (no LLM)",
        "inputs": [
            "SynthesizerDraft  (B&rsquo;s output above)",
            "DeterministicFeatures  (from stage 3)",
            "IdentifierBundle  (curator family tags)",
        ],
        "process": (
            "Three post-passes: <code>scrub_headline_risks</code> deletes "
            "structurally-incoherent risks, "
            "<code>_attach_deterministic_families</code> overwrites "
            "<code>hgnc_gene_groups</code> + <code>uniprot_family</code> on "
            "the executive_summary, <code>secreted_form_post_pass</code> "
            "upgrades the secreted_form risk from isoform topology if the "
            "synthesizer hadn&rsquo;t (this is now defense-in-depth since B "
            "sees the topology at stage 5; was load-bearing before this PR). "
            "Then <code>_derive_filters</code> composes the full 17-field "
            "<code>Filters</code> block from the LLM rollups + the "
            "deterministic blocks."
        ),
        "outputs": [
            "SurfaceomeRecord  (gene, executive_summary, filters, surface_evidence, biological_context, accessibility_risks, deterministic_features, evidence, knowledge_gaps, &hellip;)",
        ],
    },
]


def flow_section() -> str:
    cards = []
    for i, s in enumerate(EXAMPLE_FLOW_STAGES):
        ins = "".join(f'<li>{x}</li>' for x in s["inputs"])
        outs = "".join(f'<li>{x}</li>' for x in s["outputs"])
        arrow = '<div class="farrow">&darr;</div>' if i < len(EXAMPLE_FLOW_STAGES) - 1 else ""
        cards.append(f"""
          <div class="fcard">
            <div class="fhead"><h3>{s["stage"]}</h3><span class="factor">{s["actor"]}</span></div>
            <div class="fbody">
              <div class="fcol"><h4>Input</h4><ul>{ins}</ul></div>
              <div class="fcol fproc"><h4>Process</h4><div class="fproctxt">{s["process"]}</div></div>
              <div class="fcol"><h4>Output</h4><ul>{outs}</ul></div>
            </div>
          </div>
          {arrow}""")
    return f"""<section class="flow">
      <h2>Example flow for one gene &mdash; EGFR end-to-end</h2>
      <p class="sub2">Walks the v2 deep-dive pipeline stage by stage with the
      EGFR-shaped data each agent reads + emits. The arrows mark the boundary
      between agents. Hand-curated reference &mdash; numbers are typical not
      exact (paralog count + AFDB pLDDT vary across resolver releases). To
      regenerate against fresh runtime data: run <code>uv run python
      scripts/surfaceome_v2_annotate.py EGFR --no-publish</code> and read the
      orchestrator log + the synthesizer&rsquo;s persisted task message.</p>
      <div class="fflow">{''.join(cards)}</div>
    </section>"""


REPO = Path(
    subprocess.run(["git", "rev-parse", "--show-toplevel"],
                   capture_output=True, text=True).stdout.strip() or "."
)
# Diff base = where this branch forked from main (PR base). Falls back to main.
BASE = (
    subprocess.run(["git", "merge-base", "origin/main", "HEAD"],
                   cwd=REPO, capture_output=True, text=True).stdout.strip()
    or "main"
)
HEAD = "HEAD"
GLOB = "src/accessible_surfaceome/agents/**/prompts/*.md"
HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)")
SKIP = ("diff --git", "index ", "--- ", "+++ ", "new file", "deleted file", "similarity", "rename ")


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout


# Wholesale-removed deprecated v1 Managed-Agent prompts — excluded so the
# review stays focused on the live v2 deep-dive prompts the colleague works on.
EXCLUDE = ("biology_compiler/", "surface_evidence_compiler/")


def changed():
    out = git("diff", "--name-status", f"{BASE}...{HEAD}", "--", GLOB).strip()
    rows = [(ln.split("\t")[0], ln.split("\t")[-1]) for ln in out.splitlines()]
    return [(st, p) for st, p in rows if not any(x in p for x in EXCLUDE)]


def full_diff(path: str) -> str:
    # -U100000 → whole file as one hunk: every line is context, changes inline.
    return git("diff", "--no-color", "-U100000", BASE, HEAD, "--", path)


def counts(diff: str):
    a = sum(1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    r = sum(1 for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    return a, r


def render(diff: str) -> str:
    rows, newno = [], 0
    for ln in diff.splitlines():
        if ln.startswith(SKIP):
            continue
        m = HUNK.match(ln)
        if m:
            newno = int(m.group(1))
            continue  # hide hunk header — full file is shown
        if ln.startswith("+"):
            cls, num, txt = "add", str(newno), ln[1:]
            newno += 1
        elif ln.startswith("-"):
            cls, num, txt = "del", "−", ln[1:]
        else:
            cls, num, txt = "ctx", str(newno), (ln[1:] if ln.startswith(" ") else ln)
            newno += 1
        rows.append(
            f'<div class="ln {cls}"><span class="num">{num}</span>'
            f'<span class="tx">{html.escape(txt) or "&nbsp;"}</span></div>'
        )
    return "".join(rows)


BADGE = {"M": ("modified", "mod"), "A": ("new", "new"), "D": ("deleted", "del")}


def main():
    files = changed()
    nm = sum(s == "M" for s, _ in files)
    nn = sum(s == "A" for s, _ in files)
    nd = sum(s == "D" for s, _ in files)
    nav, secs = [], []
    for i, (st, path) in enumerate(files):
        label, badge = BADGE[st]
        name = path.split("/prompts/")[-1]
        grp = ("synthesizer" if "surfaceome_synthesizer" in path
               else "plan_trim_select" if "plan_trim_select" in path else "v2 builders")
        d = full_diff(path)
        a, r = counts(d)
        nav.append(
            f'<a class="navitem" href="#f{i}"><span class="b {badge}">{label}</span>'
            f'<span class="nm">{html.escape(name)}</span><span class="grp">{grp}</span>'
            f'<span class="cnt"><span class="plus">+{a}</span> <span class="minus">−{r}</span></span></a>'
        )
        note = " · deleted prompt (shown struck-through)" if st == "D" else (
            " · new prompt (all lines added)" if st == "A" else "")
        secs.append(f"""
        <section class="card" id="f{i}">
          <div class="card-h"><span class="b {badge}">{label}</span>
            <code class="path">{html.escape(path)}</code>
            <span class="cnt"><span class="plus">+{a}</span> <span class="minus">−{r}</span></span></div>
          <div class="meta">Full prompt below; <span class="k add">added</span> /
            <span class="k del">removed</span> lines highlighted inline{note}.</div>
          <div class="doc">{render(d)}</div>
        </section>""")

    out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deep-dive prompt review — PR #54</title><style>
:root{{--bg:#0f1115;--panel:#171a21;--line:#262b36;--ink:#dfe4ee;--mut:#7e8696;
--add:#16361f;--addbar:#2ea043;--del:#3a1c20;--delbar:#f85149;--acc:#6aa3ff;--gut:#11141a;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);margin:0 0 18px}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 22px}}
.chip{{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:4px 12px;font-size:12px;color:var(--mut)}}
.chip b{{color:var(--ink)}}
.nav{{display:grid;gap:6px;margin:0 0 28px}}
.navitem{{display:grid;grid-template-columns:74px 1fr auto auto;gap:10px;align-items:center;text-decoration:none;
color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px}}
.navitem:hover{{border-color:var(--acc)}}.navitem .nm{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}}
.navitem .grp{{color:var(--mut);font-size:11px}}
.b{{font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;border-radius:5px;padding:2px 7px;font-weight:600;text-align:center}}
.b.mod{{background:#1f2a44;color:#8fb4ff}}.b.new{{background:#143226;color:#56d364}}.b.del{{background:#3a1d22;color:#ff9a9a}}
.cnt{{font-family:ui-monospace,monospace;font-size:12px;white-space:nowrap}}.plus{{color:var(--addbar)}}.minus{{color:var(--delbar)}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 20px;overflow:hidden;scroll-margin-top:14px}}
.card-h{{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}}
.path{{font-family:ui-monospace,monospace;font-size:12.5px;flex:1;word-break:break-all}}
.meta{{color:var(--mut);font-size:11.5px;padding:8px 14px;border-bottom:1px solid var(--line)}}
.meta .k{{padding:0 5px;border-radius:3px}}.meta .k.add{{background:var(--add);color:#7ee2a8}}.meta .k.del{{background:var(--del);color:#ff9a9a}}
.doc{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}
.ln{{display:grid;grid-template-columns:46px 1fr;border-left:3px solid transparent}}
.ln .num{{background:var(--gut);color:#4b5263;text-align:right;padding:1px 8px;user-select:none;font-size:11px}}
.ln .tx{{padding:1px 12px;white-space:pre-wrap;word-break:break-word}}
.ln.ctx .tx{{color:var(--ink)}}
.ln.add{{background:var(--add);border-left-color:var(--addbar)}}.ln.add .tx{{color:#c8f0d6}}
.ln.del{{background:var(--del);border-left-color:var(--delbar)}}.ln.del .tx{{color:#f0b3b6;text-decoration:line-through;text-decoration-color:#a04a4f}}
.ln.del .num{{color:var(--delbar)}}
.kick{{margin:0 0 30px}}.kick h2{{font-size:17px;margin:0 0 4px}}
.sub2{{color:var(--mut);font-size:12px;margin:0 0 14px;line-height:1.5}}
.kgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:760px){{.kgrid{{grid-template-columns:1fr}}}}
.kcol{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.kcol h3{{margin:0 0 6px;font-size:14px}}.kn{{color:var(--mut);font-weight:400;font-size:11.5px}}
.ksub{{color:var(--mut);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;margin:12px 0 6px}}
.catrow{{display:flex;flex-wrap:wrap;gap:5px}}
.catchip{{background:#1b2230;border:1px solid var(--line);border-radius:5px;padding:2px 8px;font-family:ui-monospace,monospace;font-size:11px;color:#bcd0f0}}
.catchip.mode{{color:#cdb6f0}}
.trow{{padding:6px 0;border-top:1px solid var(--line)}}
.tanc{{font-size:11.5px;margin-bottom:2px}}.tanc code{{color:#8fb4ff}}
.tterms{{color:var(--ink);font-size:11.5px;line-height:1.45}}
footer{{color:var(--mut);font-size:12px;margin:28px 0 0;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--acc)}}
.enums{{margin:0 0 30px}}.enums h2{{font-size:17px;margin:0 0 4px}}
.evgroup{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 12px}}
.evgroup h3{{margin:0 0 8px;font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}}
.evrow{{display:grid;grid-template-columns:280px 1fr;gap:12px;align-items:start;padding:7px 0;border-top:1px solid var(--line)}}
.evrow:first-of-type{{border-top:none}}
@media(max-width:680px){{.evrow{{grid-template-columns:1fr}}}}
.evmeta code{{font-family:ui-monospace,monospace;font-size:11.5px;color:#8fb4ff;display:block}}
.evmeta .evname{{color:var(--mut);font-size:10.5px}}
.evchips{{display:flex;flex-wrap:wrap;gap:5px}}
.evchip{{background:#1b2230;border:1px solid var(--line);border-radius:5px;padding:2px 8px;font-family:ui-monospace,monospace;font-size:11px;color:#cfd8ea;display:inline-flex;align-items:center;gap:6px}}
.evchip.ev-homo{{border-color:#2ea043;color:#7ee2a8}}.evchip.ev-hetero{{border-color:#6aa3ff;color:#a9c8ff}}
.evaxis{{font-size:9px;text-transform:uppercase;letter-spacing:.04em;border-radius:3px;padding:1px 4px;background:#0d1014;color:var(--mut)}}
.ev-homo .evaxis{{background:#143226;color:#56d364}}.ev-hetero .evaxis{{background:#142544;color:#8fb4ff}}
.evaxis.ax-homo{{background:#143226;color:#56d364}}.evaxis.ax-hetero{{background:#142544;color:#8fb4ff}}
.determ{{margin:0 0 30px}}.determ h2{{font-size:17px;margin:0 0 4px}}
.dgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:760px){{.dgrid{{grid-template-columns:1fr}}}}
.dcard{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.dhead{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 8px}}
.dhead h3{{margin:0;font-size:13px;color:var(--ink)}}
.dbadge{{font-size:10px;text-transform:uppercase;letter-spacing:.05em;border-radius:5px;padding:2px 7px;font-weight:600}}
.d-full{{background:#143226;color:#56d364;border:1px solid #2ea043}}
.d-subset{{background:#142544;color:#8fb4ff;border:1px solid #2a4a8a}}
.d-none{{background:#2a1d28;color:#cfd8ea;border:1px solid var(--line)}}
.d-ids{{background:#3a2e16;color:#f0c577;border:1px solid #6e5a2e}}
.d-calibration-only{{background:#2a1e44;color:#cdb6f0;border:1px solid #5a3e8a}}
.flow{{margin:0 0 30px}}.flow h2{{font-size:17px;margin:0 0 4px}}
.fflow{{display:flex;flex-direction:column;gap:8px}}
.fcard{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.fhead{{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin:0 0 12px;flex-wrap:wrap}}
.fhead h3{{margin:0;font-size:13px;color:var(--ink)}}
.factor{{font-family:ui-monospace,monospace;font-size:11px;color:var(--mut)}}
.fbody{{display:grid;grid-template-columns:1fr 1.2fr 1fr;gap:14px}}
@media(max-width:860px){{.fbody{{grid-template-columns:1fr}}}}
.fcol h4{{margin:0 0 6px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}}
.fcol ul{{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:3px}}
.fcol li{{font-family:ui-monospace,monospace;font-size:11px;color:#cfd8ea;background:#0f1014;border-left:2px solid var(--line);padding:3px 8px;border-radius:0 4px 4px 0;line-height:1.45}}
.fcol.fproc{{font-family:inherit}}
.fproctxt{{font-size:12px;color:var(--ink);line-height:1.5}}
.fproctxt code{{font-family:ui-monospace,monospace;font-size:11px;color:#8fb4ff;background:#1b2230;border-radius:3px;padding:1px 4px}}
.fproctxt strong{{color:#56d364}}
.farrow{{text-align:center;font-size:18px;color:#5a3e8a;line-height:1}}
.dprompts{{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 10px}}
.dprompt{{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;background:#1b2230;border:1px solid var(--line);border-radius:4px;padding:2px 6px;color:#bcd0f0}}
.dnote{{color:var(--mut);font-size:11.5px;line-height:1.5;margin:0 0 10px;border-top:1px solid var(--line);padding-top:8px}}
.dnote code{{font-family:ui-monospace,monospace;font-size:11px;color:#8fb4ff}}
.dnote strong{{color:var(--ink)}}.dnote em{{color:var(--ink)}}
.dfields{{display:flex;flex-direction:column;gap:3px;border-top:1px solid var(--line);padding-top:8px}}
.dfield{{font-family:ui-monospace,monospace;font-size:11px;color:#c8f0d6;background:#0f1a14;border-left:2px solid var(--addbar);padding:3px 8px;border-radius:0 4px 4px 0;line-height:1.4}}
.dnone{{font-size:11.5px;color:var(--mut);border-top:1px solid var(--line);padding-top:8px}}
.dnone code{{font-family:ui-monospace,monospace;font-size:11px;color:#8fb4ff}}
</style></head><body><div class="wrap">
<h1>Deep-dive prompt review</h1>
<p class="sub">PR&nbsp;#54 — full prompt text with the diff vs <b>main</b> (<code>{BASE[:7]}</code>) highlighted inline · {len(files)} files</p>
<div class="chips"><span class="chip"><b>{nm}</b> modified</span><span class="chip"><b>{nn}</b> new</span><span class="chip"><b>{nd}</b> deleted</span></div>
{kickoff_section()}
{deterministic_section()}
{flow_section()}
{enum_section()}
<h2 style="font-size:17px;margin:0 0 12px">Prompts</h2>
<nav class="nav">{''.join(nav)}</nav>
{''.join(secs)}
<footer>Each prompt shown in full (the verbatim system prompt the model receives), rendered from <code>git diff -U100000 {BASE[:7]}…HEAD</code>. Unchanged lines are plain; added=green, removed=struck red.</footer>
</div></body></html>"""
    dest = REPO / "docs" / "prompt_review.html"
    dest.write_text(out)
    print(f"wrote {dest}  ({len(files)} files, {len(out)//1024} KB)")


if __name__ == "__main__":
    main()
