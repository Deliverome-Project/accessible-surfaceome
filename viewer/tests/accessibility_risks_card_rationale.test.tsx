/*
 * Render tests for the new rationale fields that landed in commits
 * c301e7c93 + d34b0a0f6 + b4b7237d3 — ShedForm.rationale,
 * SecretedForm.rationale + the linkified mechanism prose.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       tests/accessibility_risks_card_rationale.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AccessibilityRisksCard } from "../components/surfaceome/AccessibilityRisksCard/AccessibilityRisksCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function render(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(AccessibilityRisksCard, { rec, n: 1 }));
}

/** Slice the rendered HTML to the Shed-form subsection only — the
 *  per-section assertions don't want to collide with content the
 *  FeatureRationales summary block at the top of the card also renders.
 *  Returns the substring from the per-section subtitle to the next
 *  subsection. */
function shedSection(html: string): string {
  const start = html.indexOf("Shed form</p>");
  assert.ok(start >= 0, "Shed form section must exist");
  const end = html.indexOf("Secreted form</p>");
  return html.slice(start, end >= 0 ? end : undefined);
}

function secretedSection(html: string): string {
  const start = html.indexOf("Secreted form</p>");
  assert.ok(start >= 0, "Secreted form section must exist");
  const end = html.indexOf("ECD size assessment</p>");
  return html.slice(start, end >= 0 ? end : undefined);
}

test("shed_form.rationale renders inline above the Mechanism row", () => {
  const rec = baseRecord();
  rec.accessibility_risks.shed_form = {
    present: true,
    severity: "moderate",
    evidence_strength: "strong",
    mechanism: "ADAM10/17 cleavage releases the ECD a1_evi_12.",
    sheddase_if_known: "ADAM10",
    rationale: "Plasma sCD27 is elevated in inflammation a1_evi_10.",
    cited_evidence_ids: ["a1_evi_10", "a1_evi_12"],
  };
  const section = shedSection(render(rec));
  const idxRat = section.indexOf("Plasma sCD27 is elevated");
  const idxMech = section.indexOf("ADAM10/17 cleavage");
  assert.ok(idxRat >= 0, "rationale text must render");
  assert.ok(idxMech >= 0, "mechanism text must render");
  assert.ok(
    idxRat < idxMech,
    `rationale must come BEFORE mechanism in DOM order (got rationale@${idxRat}, mechanism@${idxMech}) — per b4b7237d3`,
  );
});

test("shed_form.rationale empty → no empty <p> in the shed section", () => {
  const rec = baseRecord();
  rec.accessibility_risks.shed_form = {
    present: true,
    severity: "moderate",
    evidence_strength: "strong",
    mechanism: "ADAM10/17 cleavage.",
    sheddase_if_known: "ADAM10",
    rationale: "",
    cited_evidence_ids: [],
  };
  const section = shedSection(render(rec));
  // No empty prose <p> renders. Mechanism still renders since it's non-empty.
  assert.ok(section.includes("ADAM10/17 cleavage"));
  assert.equal(
    /<p[^>]*class="[^"]*prose[^"]*"[^>]*>\s*<\/p>/.test(section),
    false,
    "no empty <p class=prose> for missing rationale",
  );
});

test("shed_form.mechanism is linkified — a1_evi_NN tokens become EvidenceChips", () => {
  const rec = baseRecord();
  rec.accessibility_risks.shed_form = {
    present: true,
    severity: "moderate",
    evidence_strength: "strong",
    mechanism: "ADAM10/17 cleavage releases the ECD a1_evi_12.",
    sheddase_if_known: null,
    rationale: "Plasma sCD27 elevated a1_evi_10.",
    cited_evidence_ids: ["a1_evi_10", "a1_evi_12"],
  };
  const section = shedSection(render(rec));
  // The a1_evi_12 ref inside the mechanism prose must render as an
  // EvidenceChip button — that's what linkifyEvidenceRefs does. The
  // chip carries data-evidence-id. (The same ref appears in the Cites
  // chiplist above, but the test asserts the substring is present
  // INSIDE the mechanism paragraph: we search after the "Mechanism"
  // label and before the section end.)
  const mechIdx = section.indexOf("Mechanism");
  assert.ok(mechIdx >= 0, "mechanism label must render");
  const afterMech = section.slice(mechIdx);
  assert.ok(
    afterMech.includes('data-evidence-id="a1_evi_12"'),
    "a1_evi_12 in mechanism prose must linkify to an EvidenceChip",
  );
});

test("secreted_form.rationale renders inline above the Source row", () => {
  const rec = baseRecord();
  rec.accessibility_risks.secreted_form = {
    present: true,
    severity: "moderate",
    evidence_strength: "moderate",
    ratio_to_membrane: 0.05,
    source: "alternative_splicing",
    rationale: "Soluble isoform detected by RNA-Seq a1_evi_15.",
    cited_evidence_ids: ["a1_evi_15"],
  };
  const section = secretedSection(render(rec));
  const idxRat = section.indexOf("Soluble isoform detected");
  const idxSrc = section.indexOf("Source</span>");
  assert.ok(idxRat >= 0, "rationale text must render");
  assert.ok(idxSrc >= 0, "Source label must render");
  assert.ok(
    idxRat < idxSrc,
    `rationale must come BEFORE Source label in DOM order (got rationale@${idxRat}, source@${idxSrc})`,
  );
});

test("secreted_form.rationale empty → no empty <p> in the secreted section", () => {
  const rec = baseRecord();
  rec.accessibility_risks.secreted_form = {
    present: false,
    severity: "low",
    evidence_strength: "moderate",
    ratio_to_membrane: null,
    source: "unknown",
    rationale: "",
    cited_evidence_ids: [],
  };
  const section = secretedSection(render(rec));
  assert.equal(
    /<p[^>]*class="[^"]*prose[^"]*"[^>]*>\s*<\/p>/.test(section),
    false,
    "no empty <p class=prose> for missing rationale",
  );
});
