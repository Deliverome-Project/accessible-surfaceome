/*
 * L1 review page: the browser's filtering, verdict roll-up, residue mapping and the
 * per-site rationale card.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs tests/l1_review_page.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SiteCard } from "../components/L1Review/L1Review";
import {
  filterIndex,
  latestVerdicts,
  modelToMemberResidue,
  sortSites,
  visibleContacts,
  type L1Contact,
  type L1IndexMember,
  type L1ReviewRow,
  type L1Site,
} from "../lib/l1-design";

const m = (id: string, gene: string, rung: string, cls: string, pick: L1IndexMember["pick_status"]): L1IndexMember => ({
  member_id: id, design_id: id.replace("m", "p"), gene_symbol: gene, species: "human",
  candidate_set: "library_reference", rung, membrane_class: cls, n_tm: 7, ordered_length_aa: 400,
  sequence_sha256: null, pick_status: pick,
});
const index = [
  m("l1-m0003", "ADRB2", "N at residue 1, multipass", "GPCR", ["built"]),
  m("l1-m0001", "AXL", "N after SP", "single-pass type I", ["pending"]),
  m("l1-m0002", "SLC2A1", "internal", "transporter", []),
];

test("filters by rung, class, pick status and query; sorted by gene", () => {
  assert.deepEqual(filterIndex(index, {}).map((x) => x.gene_symbol), ["ADRB2", "AXL", "SLC2A1"]);
  assert.deepEqual(filterIndex(index, { membraneClass: "GPCR" }).map((x) => x.gene_symbol), ["ADRB2"]);
  assert.deepEqual(filterIndex(index, { rung: "internal" }).map((x) => x.gene_symbol), ["SLC2A1"]);
  assert.deepEqual(filterIndex(index, { status: "none" }).map((x) => x.gene_symbol), ["SLC2A1"]);
  assert.deepEqual(filterIndex(index, { query: "l1-p0001" }).map((x) => x.gene_symbol), ["AXL"]);
  assert.deepEqual(filterIndex(index, { query: "slc" }).map((x) => x.gene_symbol), ["SLC2A1"]);
});

test("each reviewer's latest verdict per member wins", () => {
  const r = (id: string, who: string, at: string, v: "good" | "no"): L1ReviewRow => ({
    review_id: id, created_at: at, reviewer: who, member_id: "l1-m0001", design_id: "l1-p0001",
    gene_symbol: "AXL", site_id: null, verdict: v, reason: null, load_version: "l1d-0",
  });
  const got = latestVerdicts([r("a", "Becca", "2026-11-12T01", "no"), r("b", "Becca", "2026-11-12T02", "good"), r("c", "Kim", "2026-11-12T00", "no")]);
  assert.deepEqual(got.get("l1-p0001")!.map((x) => `${x.reviewer}:${x.verdict}`).sort(), ["Becca:good", "Kim:no"]);
});

test("a picked model residue maps to member numbering on native models only", () => {
  assert.equal(modelToMemberResidue(135, { kind: "native", residue_offset: 101 }), 34);
  assert.equal(modelToMemberResidue(135, { kind: "tagged", residue_offset: 0 }), null);
});

test("ion sites and additives are hidden unless asked for", () => {
  const c = (tier: L1Contact["confidence_tier"]): L1Contact => ({
    residue: 1, aa: "Y", canonical_residue: 1, source: "literature_agent", evidence_types: null,
    contact_classes: null, confidence_tier: tier, ion_site: tier === "hidden", additive_only: false,
    in_extracellular: true, topology_state: "O", ligands: null, pmids: null,
  });
  assert.equal(visibleContacts([c("high"), c("hidden")], false).length, 1);
  assert.equal(visibleContacts([c("high"), c("hidden")], true).length, 2);
});

const site = (over: Partial<L1Site>): L1Site => ({
  site_id: "l1-p0006-internal-94", rung: "internal", site_source: "ranker", is_primary: true,
  insert_after_residue: 94, residue_before: "V", residue_after: "S", leader: null, cassette: null,
  cassette_aa: null, rank: 1, status: "decided_not_built", decision: "internal_loop",
  status_detail: "internal_loop; refold verdict pending", confidence: "medium",
  rejected_alternative: "v5 rank-2 pick", rationale: { rank_score: 0.86, loop_evidence: { glycan_n: "100" } },
  source: { pr: 7, pr_state: "open", commit: "abcdef012345", path: "decisions.tsv" },
  decided_by: "ranker session (delegated by the reviewer 2026-11-12)", implemented_by: "ranker", reason: "v5 rank-1",
  ...over,
});

test("current picks sort before alternatives, ranker before agent", () => {
  const got = sortSites([
    site({ site_id: "agent", is_primary: false, site_source: "agent_proposer", rank: 1 }),
    site({ site_id: "alt", is_primary: false, rank: 2 }),
    site({ site_id: "pick" }),
  ]);
  assert.deepEqual(got.map((s) => s.site_id), ["pick", "alt", "agent"]);
});

test("the site card shows who decided, why, the rejected alternative and the scores", () => {
  const html = renderToStaticMarkup(React.createElement(SiteCard, { site: site({}), length: 152 }));
  assert.match(html, /Current pick/);
  assert.match(html, /between V94 and S95/);
  assert.match(html, /decided, not built/);
  assert.match(html, /delegated by the reviewer 2026-11-12/);
  assert.match(html, /rejected alternative/);
  assert.match(html, /v5 rank-2 pick/);
  assert.match(html, /rank score/);
  assert.match(html, /glycan n/);
  assert.match(html, /design PR 7 \(open\)/);
});
