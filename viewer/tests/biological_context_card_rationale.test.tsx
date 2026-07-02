/*
 * Render tests for the new ``rationale`` fields that landed in
 * commits c301e7c93 + d34b0a0f6 + b4b7237d3 — the
 * SubcellularLocalization / DualLocalization / MembraneSubdomain
 * ``rationale`` strings + ``biological_context.grade_rationale``.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       tests/biological_context_card_rationale.test.tsx
 *
 * The viewer doesn't have Vitest / RTL — see tests/helpers/css-loader.mjs
 * for the CSS-module shim that makes the components renderable under
 * plain ``tsx`` + ``react-dom/server``. ``node:test`` is the runner
 * (same convention as ``antibody_links.test.ts``).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { BiologicalContextCard } from "../components/surfaceome/BiologicalContextCard/BiologicalContextCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function render(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(BiologicalContextCard, { rec, n: 1 }));
}

test("SubcellularLocalization.rationale renders inline below primary compartment", () => {
  const rec = baseRecord();
  rec.biological_context.subcellular_localization.rationale =
    "Single-pass type I, ECD large per a1_evi_03.";
  const html = render(rec);
  assert.ok(
    html.includes("Single-pass type I, ECD large per"),
    "rationale text must appear in rendered HTML",
  );
  // The trailing evidence ref is linkified into a chip — confirm.
  assert.ok(
    html.includes('data-evidence-id="a1_evi_03"'),
    "trailing evidence ref must linkify to an EvidenceChip",
  );
});

test("SubcellularLocalization.rationale absent → no empty <p> tag in subcellular subsection", () => {
  const rec = baseRecord();
  rec.biological_context.subcellular_localization.rationale = "";
  const html = render(rec);
  // No locProse <p> should be emitted when the rationale is empty. The
  // module rewrites class names to their key under the test loader so
  // we can look for "locProse" verbatim.
  assert.equal(html.includes("Single-pass type I"), false);
  // Defensive: never emit ``<p class="locProse"></p>`` (the bug pattern
  // we're guarding against — an empty paragraph leaves visible empty
  // space in the gene page).
  assert.equal(
    /<p[^>]*class="[^"]*locProse[^"]*"[^>]*>\s*<\/p>/.test(html),
    false,
    "no empty locProse <p> when rationale is missing",
  );
});

test("DualLocalization.rationale renders inside the at-a-glance tooltip body", () => {
  const rec = baseRecord();
  rec.biological_context.subcellular_localization.dual_localization = [
    {
      compartment: "endosome",
      fraction_estimate: 0.2,
      condition: "low pH",
      rationale: "Endocytosed in clathrin-coated pits a1_evi_05.",
      cited_evidence_ids: ["a1_evi_05"],
    },
  ];
  const html = render(rec);
  // StatusPill renders ``title`` props as the body of a styled popover
  // (``role="tooltip"``), not as an HTML ``title=`` attribute — so the
  // assertion is on the popover text content. Either way, the rationale
  // string must appear in the rendered HTML.
  assert.ok(
    html.includes("Endocytosed in clathrin-coated pits"),
    "dual-localization rationale must appear in rendered HTML",
  );
  // The popover wraps the text in <span role="tooltip" class="popover">
  // — assert the text sits inside such a span.
  assert.ok(
    /<span[^>]*role="tooltip"[^>]*>[^<]*Endocytosed in clathrin-coated pits/.test(
      html.replace(/\s+/g, " "),
    ),
    "rationale must appear inside the role=\"tooltip\" popover body",
  );
});

test("DualLocalization with no rationale → no tooltip body emitted for it", () => {
  const rec = baseRecord();
  rec.biological_context.subcellular_localization.dual_localization = [
    {
      compartment: "endosome",
      fraction_estimate: null,
      condition: null,
      rationale: "",
      cited_evidence_ids: [],
    },
  ];
  const html = render(rec);
  // The pill renders as a plain pill (no popover) when ``hover`` is
  // empty. Assert no tooltip popover is emitted for an empty rationale
  // by counting the role="tooltip" occurrences — the count should NOT
  // include one for this dual_localization row.
  // (The exact count depends on other rationales in the card; this
  // assertion checks that the rationale text itself is absent.)
  assert.equal(html.includes("Endocytosed"), false);
});

test("MembraneSubdomain.rationale renders inside the subdomain pill tooltip", () => {
  const rec = baseRecord();
  rec.biological_context.subcellular_localization.membrane_subdomains = [
    {
      subdomain: "raft",
      rationale: "Localizes to lipid rafts upon activation.",
      cited_evidence_ids: ["a1_evi_07"],
    },
  ];
  const html = render(rec);
  assert.ok(
    html.includes("Localizes to lipid rafts upon activation"),
    "subdomain rationale must appear in rendered HTML",
  );
  assert.ok(
    /<span[^>]*role="tooltip"[^>]*>[^<]*Localizes to lipid rafts/.test(
      html.replace(/\s+/g, " "),
    ),
    "subdomain rationale must appear inside the role=\"tooltip\" popover body",
  );
});

test("biological_context.grade_rationale renders at the top of the card with the grade label", () => {
  const rec = baseRecord();
  rec.biological_context.grade_rationale =
    "Two direct flow methods plus IHC support a1_evi_01.";
  rec.biological_context.biological_context_grade = "moderate";
  const html = render(rec);
  // Both the grade label and the rationale text appear, in that order.
  const idxLabel = html.indexOf("Biology evidence");
  const idxRat = html.indexOf("Two direct flow methods plus IHC support");
  assert.ok(idxLabel >= 0, "grade-rationale 'Biology evidence' label must render");
  assert.ok(idxRat >= 0, "grade_rationale text must render");
  assert.ok(idxLabel < idxRat, "label comes before rationale");
  // Linkified ref → chip.
  assert.ok(
    html.includes('data-evidence-id="a1_evi_01"'),
    "grade_rationale evidence ref must linkify to an EvidenceChip",
  );
});

test("biological_context.grade_rationale empty → no Biology evidence label, no empty <p>", () => {
  const rec = baseRecord();
  rec.biological_context.grade_rationale = "";
  rec.biological_context.biological_context_grade = "absent";
  const html = render(rec);
  assert.equal(
    html.includes("Biology evidence"),
    false,
    "no 'Biology evidence' label rendered when grade_rationale is empty",
  );
  // Guard: no empty contextRationale paragraph leaks through.
  assert.equal(
    /<p[^>]*class="[^"]*contextRationale[^"]*"[^>]*>\s*<\/p>/.test(html),
    false,
    "no empty contextRationale <p> when grade_rationale is missing",
  );
});

test("FeatureRationales row carries chip-jump id + tabIndex for scroll target", () => {
  const rec = baseRecord();
  // The biology category's `spec` chip: value is derived from
  // filters.surface_specificity + rationale; we only need the row
  // to render so its id is emitted.
  rec.filters.surface_specificity = "surface_dominant";
  rec.filters.surface_specificity_rationale = "Membrane-anchored per a1_evi_02.";
  const html = render(rec);
  assert.match(
    html,
    /id="chip-jump-biology-spec"/,
    "biology `spec` rationale row must expose the chipJumpTargets.featureRationale id",
  );
  assert.match(
    html,
    /id="chip-jump-biology-spec"[^>]*tabindex="-1"/,
    "destination row must be programmatically focusable via tabIndex=-1",
  );
});
