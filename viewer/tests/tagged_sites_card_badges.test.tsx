/*
 * Server-render tests for the two things the Tag-sites card could not say.
 *
 * 1. The agent metadata used to be concatenated onto the rationale string as
 *    "[validation: function_only; position: inferred; entailment_verified: True]"
 *    — raw field names and a Python True, rendered as prose in the middle of a
 *    scientific argument, with nothing the UI could sort or filter on. They are
 *    fields now and render as badges.
 * 2. A gene the agent SEARCHED and found nothing in rendered as nothing at all,
 *    identical to a gene nobody had looked at. 1,107 of 1,835 searched genes are
 *    that case. The card now says zero, and when it looked.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/tagged_sites_card_badges.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TaggedSitesCard } from "../components/surfaceome/TaggedSitesCard/TaggedSitesCard";
import type { TaggedSite, TaggedSitesFile } from "../lib/tag-sites-types";

const litSite: TaggedSite = {
  site_id: "X-internal-594-lit",
  gene_symbol: "X",
  uniprot_acc: "Q0",
  provenance: "literature_retrieved",
  det_path: null,
  site_kind: "internal",
  insert_after_residue: 594,
  residue_before: "G",
  residue_after: "S",
  residue_label: "G594",
  topology_state: "O",
  extracellular: true,
  compartment: "extracellular",
  tag_type: "ALFA",
  tag_length_aa: null,
  linker: null,
  evidence_type: "epitope insertion",
  functional_impact_measured: "transport retained",
  confidence: "high",
  rationale: "The paper places the tag in the second extracellular loop.",
  validation_level: "function_only",
  position_evidence: "inferred",
  source_tier: "paper",
  cited_tag_residue: 594,
  entailment_verified: true,
  sources: [{ pmid: 123, citation: "PMID 123", claim: "a verbatim sentence" }],
  plddt: null,
  conservation_rank: null,
  median_conservation: null,
};

function render(file: TaggedSitesFile): string {
  return renderToStaticMarkup(<TaggedSitesCard taggedSites={file} n={1} />);
}

test("validation + position render as badges, not as a bracket in the prose", () => {
  const html = render({
    has_data: true,
    gene_symbol: "X",
    uniprot_acc: "Q0",
    prompt_sha: "abc",
    sites: [litSite],
  });
  assert.ok(html.includes("Validation"), "Validation column header missing");
  assert.ok(html.includes("Position"), "Position column header missing");
  assert.ok(html.includes("Function"), "validation_level badge not rendered");
  assert.ok(html.includes("Inferred"), "position_evidence badge not rendered");
  // The exact shapes that were leaking.
  assert.ok(!html.includes("[validation:"), "raw metadata bracket still rendered");
  assert.ok(!html.includes("entailment_verified"), "internal gate name is user-facing");
  assert.ok(!html.includes("cited_tag_residue:"), "raw field name is user-facing");
});

test("an inferred position says which real tag it was reasoned from", () => {
  const html = render({
    has_data: true, gene_symbol: "X", uniprot_acc: "Q0",
    prompt_sha: "abc", sites: [litSite],
  });
  assert.ok(
    html.includes("residue 594"),
    "an inferred junction must name the cited tag that grounds it",
  );
});

test("a searched gene with no literature site reports zero, not silence", () => {
  const html = render({
    has_data: false,
    gene_symbol: "SIGLEC9",
    uniprot_acc: "Q9Y336",
    prompt_sha: "abc123",
    generated_at: "2026-10-11T14:22:21Z",
    sites: [],
  });
  assert.ok(html.includes("Literature-validated (0)"), "zero count not shown");
  assert.ok(
    html.includes("No published tag-insertion site found"),
    "zero state text missing",
  );
});

test("a gene the agent never searched still renders the plain empty state", () => {
  const html = render({
    has_data: false, gene_symbol: "X", uniprot_acc: "Q0", sites: [],
  });
  assert.ok(
    html.includes("No tag-site suggestions"),
    "unsearched gene must not claim a zero result",
  );
  assert.ok(
    !html.includes("Literature-validated (0)"),
    "unsearched gene must not be reported as a searched zero",
  );
});

test("literature sits above screen-validated", () => {
  const screenSite: TaggedSite = {
    ...litSite,
    site_id: "X-nterm-screen",
    provenance: "screen_validated",
    site_kind: "terminal_n",
    residue_label: null,
    insert_after_residue: null,
  };
  const html = render({
    has_data: true, gene_symbol: "X", uniprot_acc: "Q0",
    prompt_sha: "abc", sites: [screenSite, litSite],
  });
  const lit = html.indexOf("Literature-validated");
  const screen = html.indexOf("Screen-validated");
  assert.ok(lit >= 0 && screen >= 0, "both sections should render");
  assert.ok(lit < screen, "Literature-validated must come before Screen-validated");
});
