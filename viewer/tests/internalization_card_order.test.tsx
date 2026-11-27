/*
 * Server-render test for <InternalizationCardBody>:
 * Pins that Literature renders ABOVE the Sequence prior track, and that
 * schema 0.3.0 additive synthesis / kinetics fields render cleanly.
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
    predominant_fate: "recycling",
    ligand_dependence_summary: "Constitutive recycling independent of transferrin binding.",
    epitope_or_valency_dependence_note: "Bivalent antibodies can reroute toward lysosomes.",
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
        species: "human",
        internalization_mode: "basal",
        ligand_name: "transferrin",
        mechanism: "clathrin",
        magnitude: "high",
        quant: {
          rate_metric: "k_int",
          rate_value: 0.14,
          rate_unit: "min-1",
          quant_summary: "First-order internalization rate constant",
          k_int_per_min: 0.14,
          t_half_min: 4.95,
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

test("renders Literature track ABOVE Sequence prior track", () => {
  const html = renderToStaticMarkup(
    React.createElement(InternalizationCardBody, {
      rec: sampleRec,
      obsSort: { key: "", dir: 1 },
      toggleObsSort: () => {},
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
  assert.ok(html.includes("k_int 0.14 min"), "normalized k_int should render");
  assert.ok(html.includes("Ligand dependence:"), "ligand dependence summary should render");
});
