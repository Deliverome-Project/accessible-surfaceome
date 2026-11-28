/*
 * Server-render test for <InternalizationCardBody>:
 * Pins that Literature renders ABOVE the Sequence prior track, and that
 * schema 0.3.0 additive synthesis / kinetics / fate / binder fields render cleanly.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  InternalizationCardBody,
  type InternalizationRecord,
} from "../components/surfaceome/InternalizationCard/InternalizationCard";

const sampleRec: InternalizationRecord = {
  gene_symbol: "TFRC",
  uniprot_acc: "P02786",
  model_priors: [
    {
      model: "claude-opus-5",
      overall_grade: "high",
      overall_confidence: "high",
      model_reasoning: "Contains cytoplasmic YTRF motif.",
      per_isoform: [
        {
          isoform_id: "P02786-1",
          is_canonical: true,
          length_aa: 760,
          topology_summary: "Type II TM",
          endocytic_motifs_noted: "YTRF",
          grade: "high",
          confidence: "high",
          rationale: "Canonical sorting signal.",
        },
      ],
    },
  ],
  literature: {
    overall_grade: "high",
    overall_confidence: "high",
    rationale: "Rapid constitutive clathrin-mediated endocytosis (int_evi_01).",
    cross_condition_note: "",
    species_scope: "human",
    predominant_fate: "recycles",
    trafficking_summary: "Rapid recycling through early endosomes back to plasma membrane.",
    ligand_dependence_summary: "Constitutive recycling independent of transferrin binding.",
    epitope_or_valency_dependence_note: "Bivalent antibodies can reroute toward lysosomes.",
    has_primary_or_invivo_evidence: true,
    grades_by_mode: {
      basal: { grade: "high", confidence: "high", rationale: "Fast constitutive uptake.", cited_source_ids: ["int_evi_01"] },
      native_ligand: { grade: "high", confidence: "high", rationale: "Holo-Tf cycles rapidly.", cited_source_ids: ["int_evi_01"] },
      therapeutic: { grade: "high", confidence: "moderate", rationale: "Anti-TfR1 conjugates internalize rapidly.", cited_source_ids: ["int_evi_01"] },
    },
    observations: [
      {
        assay_type: "radioligand_uptake",
        cell_line: "HepG2",
        cell_context: "endogenous",
        expression_context: "endogenous",
        species: "human",
        internalization_mode: "basal",
        ligand_name: "transferrin",
        binder_type: "native_ligand",
        binder_valency: "monovalent",
        post_uptake_fate: "recycles",
        mechanism: "clathrin",
        magnitude: "high",
        quant: {
          rate_metric: "half_life",
          rate_value: 3.5,
          rate_unit: "min",
          quant_summary: "First-order internalization half-life",
          derived_t_half_min: 3.5,
          derived_ke_min_inv: 0.198,
          derived_kinetics_basis: "direct_half_life",
        },
        controls_note: null,
        cited_source_ids: ["int_evi_01"],
      },
    ],
    sources: [],
    n_papers_discovered: 120,
    n_papers_fetched: 12,
  },
};

test("renders Literature track ABOVE Sequence prior track with schema 0.3.0 richness", () => {
  const html = renderToStaticMarkup(
    React.createElement(InternalizationCardBody, {
      rec: sampleRec,
      obsSort: { key: "", dir: 1 },
      toggleObsSort: () => {},
      setObsModeFilter: () => {},
      setObsQuantOnly: () => {},
    }),
  );
  const litIdx = html.indexOf("Literature");
  const seqIdx = html.indexOf("Sequence prior");
  assert.ok(litIdx !== -1, "Literature heading must render");
  assert.ok(seqIdx !== -1, "Sequence prior heading must render");
  assert.ok(
    litIdx < seqIdx,
    `Expected Literature (${litIdx}) to appear before Sequence prior (${seqIdx})`,
  );
  assert.ok(html.includes("t½ 3.5 min"), "normalized derived_t_half_min should render");
  assert.ok(html.includes("kₑ 0.198 min"), "normalized derived_ke_min_inv should render");
  assert.ok(html.includes("recycling"), "human-readable predominant_fate should render");
  assert.ok(html.includes("Trafficking:"), "trafficking_summary should render");
  assert.ok(html.includes("Ligand dependence:"), "ligand_dependence_summary should render");
  assert.ok(html.includes("primary / in vivo"), "primary/in vivo badge should render");
  assert.ok(html.includes("native ligand · monovalent"), "binder type + valency should render");
});
