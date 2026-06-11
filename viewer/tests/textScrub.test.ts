/**
 * Unit tests for the verbatim-quote scrubbers in lib/textScrub.ts.
 * Run with: npx --yes tsx --test tests/textScrub.test.ts
 *
 * Mirrors the JATS leaks the deep-dive agent has actually pulled out
 * of PMC sources — inline italics + structured-abstract headings.
 * Anchor cases are pinned to the EVI-drawer bug surfaced on CD63
 * (PMID 41818370 quote).
 */
import { strict as assert } from "node:assert";
import { test } from "node:test";

import { stripInlineHtml } from "../lib/textScrub";

test("stripInlineHtml: structured-abstract headings become inline labels", () => {
  const input =
    "<h4>Background</h4>Severe Omicron cases present profound lymphocytopenia, suggesting variant-specific immune injury.<h4>Results</h4>We identify CD63 as a conserved T-cell host factor supporting ACE2-independent SARS-CoV-2 entry.";
  const expected =
    "Background: Severe Omicron cases present profound lymphocytopenia, suggesting variant-specific immune injury. Results: We identify CD63 as a conserved T-cell host factor supporting ACE2-independent SARS-CoV-2 entry.";
  assert.equal(stripInlineHtml(input), expected);
});

test("stripInlineHtml: heading at start trims leading whitespace cleanly", () => {
  assert.equal(
    stripInlineHtml("<h4>Methods</h4>We retrospectively collected samples."),
    "Methods: We retrospectively collected samples.",
  );
});

test("stripInlineHtml: inline italics + sup tags still strip", () => {
  assert.equal(
    stripInlineHtml(
      "expression of <i>ABC</i> transporter genes using Wes<sup>TM</sup> analyses",
    ),
    "expression of ABC transporter genes using WesTM analyses",
  );
});

test("stripInlineHtml: heading + inline tags compose", () => {
  const input =
    "<h4>Results</h4>After alpha-gal stimulation, CD63<sup>+</sup> cells increased 3-fold.";
  const expected =
    "Results: After alpha-gal stimulation, CD63+ cells increased 3-fold.";
  assert.equal(stripInlineHtml(input), expected);
});

test("stripInlineHtml: `<5%` math-shaped text is NOT scrubbed", () => {
  // The conservative whitelist exists so non-tag angle brackets pass
  // through. Numeric / arithmetic comparisons in quotes must survive.
  assert.equal(
    stripInlineHtml("baseline rate <5% across cohorts"),
    "baseline rate <5% across cohorts",
  );
});

test("stripInlineHtml: empty / nullish input returns empty string", () => {
  assert.equal(stripInlineHtml(null), "");
  assert.equal(stripInlineHtml(undefined), "");
  assert.equal(stripInlineHtml(""), "");
});

test("stripInlineHtml: NBSP + soft hyphen normalize to ASCII", () => {
  // Real shape from FN1.json: "surface‐associated" + "11.7 ± 3.6%".
  assert.equal(
    stripInlineHtml("surface‐associated proteins"),
    "surface-associated proteins",
  );
  assert.equal(
    stripInlineHtml("mean 11.7 ± 3.6%"),
    "mean 11.7 ± 3.6%",
  );
  // Unicode minus → hyphen.
  assert.equal(
    stripInlineHtml("a − 5 fold decrease"),
    "a - 5 fold decrease",
  );
});

test("stripInlineHtml: en-dash / em-dash / Greek / ± / × all preserved", () => {
  // These convey distinct meaning; do NOT normalize away.
  assert.equal(
    stripInlineHtml("range 0.1–0.3 µg/mL — n=14, ±0.05, ×3"),
    "range 0.1–0.3 µg/mL — n=14, ±0.05, ×3",
  );
  assert.equal(
    stripInlineHtml("β-catenin / α2 subunit / κ-opioid"),
    "β-catenin / α2 subunit / κ-opioid",
  );
});

test("stripInlineHtml: trailing-space-in-paren citations get tidied", () => {
  // Real shape from FN1.json — "( Rogers et al., 2020 )" patterns.
  assert.equal(
    stripInlineHtml("FN1 ( Rogers et al., 2020 ) facilitates migration"),
    "FN1 (Rogers et al., 2020) facilitates migration",
  );
});
