/*
 * Render test for the Contradicting-evidence chip-jump destination on
 * the Evidence tab.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/surface_evidence_card_chip_jump.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SurfaceEvidenceCard } from "../components/surfaceome/SurfaceEvidenceCard/SurfaceEvidenceCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function withSurfaceEvidence(rec: SurfaceomeRecord): SurfaceomeRecord {
  // baseRecord() omits `gene` + `surface_evidence` since most cards
  // don't read them. SurfaceEvidenceCard does (rec.gene.hgnc_symbol,
  // rec.surface_evidence.*) — patch them in so renderToStaticMarkup
  // doesn't throw on undefined property access.
  (rec as unknown as { gene: unknown }).gene = {
    hgnc_symbol: "TESTGENE",
    hgnc_id: "HGNC:1",
    uniprot_acc: "P00001",
    ncbi_gene_id: 1,
    ensembl_gene: "ENSG00000000001",
  };
  (rec as unknown as { surface_evidence: unknown }).surface_evidence = {
    evidence_grade: "absent",
    grade_rationale: "",
    claim_stances: [],
    methods: [],
    non_surface_expression: [],
    contradicting_evidence: [],
    excluded_as_ligand_engagement: [],
  };
  return rec;
}

function render(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(SurfaceEvidenceCard, { rec, n: 1 }));
}

test("Contradicting-evidence block carries chip-jump id + tabIndex when present", () => {
  const rec = withSurfaceEvidence(baseRecord());
  rec.surface_evidence.contradicting_evidence = [
    {
      claim: "Cytoplasmic staining reported in HeLa.",
      contradiction_type: "alternative_localization",
      severity_for_surface_accessibility: "moderate",
      likely_explanation: null,
      cited_evidence_ids: ["a1_evi_09"],
    },
  ];
  const html = render(rec);
  assert.match(
    html,
    /id="chip-jump-contradicting-evidence"/,
    "block must expose contradictingEvidence id when list is non-empty",
  );
  assert.match(
    html,
    /id="chip-jump-contradicting-evidence"[^>]*tabindex="-1"/,
    "destination block must be programmatically focusable",
  );
});

test("Contradicting-evidence block omitted (with its id) when list is empty", () => {
  const rec = withSurfaceEvidence(baseRecord());
  rec.surface_evidence.contradicting_evidence = [];
  const html = render(rec);
  assert.equal(
    /id="chip-jump-contradicting-evidence"/.test(html),
    false,
    "no id when the block itself isn't rendered",
  );
});
