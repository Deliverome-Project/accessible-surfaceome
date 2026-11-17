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
import { ReviewPanel, SiteCard } from "../components/L1Review/L1Review";
import {
  filterIndex,
  latestVerdicts,
  modelToMemberResidue,
  reviewScopeLabel,
  sortSites,
  standingReviewIds,
  visibleContacts,
  type L1Contact,
  type L1IndexMember,
  type L1Member,
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

// ------------------------------------------- what a verdict is a verdict on
//
// A verdict carries the tag site it is about, so "a2 sits in the pore, a1 and a3 are
// fine" has somewhere to go: the r2 agent round rejects arms, not members. A null
// site id is the member as a whole, which is what every row written before this was.
//
// Not covered here: the per-member draft retention. These tests render to static
// markup with no DOM, so typing in one member and clicking to another cannot be
// driven from them; that one is checked in the browser.

const member = (over: Partial<L1Member> = {}): L1Member => ({
  member_id: "l1-m0006", design_id: "l1-p0006", gene_symbol: "LHFPL6", species: "human",
  candidate_set: "library_reference", rung: "internal", ordered_length_aa: 400,
  sequence_sha256: null, sites: [], structures: [], ...over,
});
const twoArms = [
  site({ site_id: "l1-p0006-a1" }),
  site({ site_id: "l1-p0006-a2", is_primary: false, insert_after_residue: 151, residue_before: "H", residue_after: "D" }),
];

test("a verdict's scope reads as the arm it is about, or the member as a whole", () => {
  assert.equal(reviewScopeLabel(null, twoArms, 400), "the member as a whole");
  assert.equal(reviewScopeLabel("l1-p0006-a1", twoArms, 400), "a1 — between V94 and S95");
  assert.equal(reviewScopeLabel("l1-p0006-a2", twoArms, 400), "a2 — between H151 and D152 (alternative)");
  // A row from an earlier load, whose site this load no longer carries, still names its
  // arm rather than silently reading as a verdict on the whole member.
  assert.equal(reviewScopeLabel("l1-p0006-a7", twoArms, 400), "a7");
  assert.equal(reviewScopeLabel("l1-p2089-res1-igk_tag", twoArms, 400), "l1-p2089-res1-igk_tag");
});

test("a later verdict on the same arm supersedes it; another arm is a separate verdict", () => {
  const r = (id: string, siteId: string | null, at: string, v: "good" | "no"): L1ReviewRow => ({
    review_id: id, created_at: at, reviewer: "Becca", member_id: "l1-m0001", design_id: "l1-p0001",
    gene_symbol: "AXL", site_id: siteId, verdict: v, reason: null, load_version: "l1d-0",
  });
  const rows = [
    r("a", "l1-p0001-a1", "2026-11-16T09", "no"),
    r("b", "l1-p0001-a1", "2026-11-16T11", "good"), // changed her mind about a1
    r("c", "l1-p0001-a2", "2026-11-16T10", "no"),   // a different arm: still standing
    r("d", null, "2026-11-16T08", "good"),          // and the member as a whole
  ];
  assert.deepEqual([...standingReviewIds(rows)].sort(), ["b", "c", "d"]);
  // The member-list dots roll up by the same scope, so a1 and a2 both get one.
  assert.equal(latestVerdicts(rows).get("l1-p0001")!.length, 3);
});

const panel = (over: Partial<Parameters<typeof ReviewPanel>[0]> = {}) =>
  renderToStaticMarkup(
    React.createElement(ReviewPanel, {
      member: member({ sites: twoArms }), loadVersion: "l1d-3", reviews: null,
      token: "t", reviewer: "Becca", pickedResidue: null,
      drafts: {}, setDrafts: () => {}, onSaved: () => {}, ...over,
    }),
  );

test("the review panel asks which arm the verdict is about, before the buttons", () => {
  const html = panel();
  assert.match(html, /the member as a whole/);
  assert.match(html, /a1 — between V94 and S95/);
  assert.match(html, /a2 — between H151 and D152 \(alternative\)/);
  // The choice changes what the buttons mean, so it is read before them.
  assert.ok(html.indexOf("the member as a whole") < html.indexOf("Looks good"));
});

test("without a token the panel's text fields are closed, not only its buttons", () => {
  // A tokenless visitor could write 4,000 characters into a textarea whose save button
  // was greyed out above it, and lose every one of them.
  const locked = panel({ token: "" });
  assert.match(locked, /<textarea[^>]*disabled/);
  assert.match(locked, /Set your name and token above/);
  assert.doesNotMatch(panel(), /<textarea[^>]*disabled/);
});

test("an earlier verdict on the same arm shows as superseded, not as a second opinion", () => {
  const r = (id: string, at: string, v: "good" | "no", reason: string): L1ReviewRow => ({
    review_id: id, created_at: at, reviewer: "Becca", member_id: "l1-m0006", design_id: "l1-p0006",
    gene_symbol: "LHFPL6", site_id: "l1-p0006-a1", verdict: v, reason, load_version: "l1d-3",
  });
  const html = panel({
    reviews: {
      reviews: [r("a", "2026-11-16T09", "no", "pore helix"), r("b", "2026-11-16T11", "good", "mapped wrong; it is fine")],
      alt_tags: [],
    },
  });
  assert.match(html, /class="superseded"/);
  assert.equal(html.match(/superseded by a later row/g)!.length, 1);
  assert.match(html, /a1 — between V94 and S95/);
  // The list is every reviewer's rows, which is what makes answering someone possible;
  // it used to be headed "Your review".
  assert.match(html, /every reviewer/);
});

test("curated contacts are drawn only on a member whose protein is the reference sequence", async () => {
  const { curatedContactsAlign } = await import("../lib/l1-design");
  assert.equal(curatedContactsAlign("a".repeat(64), "a".repeat(64)), true);
  assert.equal(curatedContactsAlign("a".repeat(64), "b".repeat(64)), false);
  assert.equal(curatedContactsAlign(null, "a".repeat(64)), false);
  assert.equal(curatedContactsAlign("a".repeat(64), undefined), false);
});

// --------------------------------------------- browsing, gene grouping, topology strip

test("members of one gene group into one entry, in the browsing order they already have", async () => {
  const { groupByGene } = await import("../lib/l1-design");
  const got = groupByGene([
    { gene_symbol: "TFR2" }, { gene_symbol: "TFRC" }, { gene_symbol: "TFRC" }, { gene_symbol: "TG" },
  ]);
  assert.deepEqual(got.map((g) => [g.gene_symbol, g.members.length, g.firstIndex]), [
    ["TFR2", 1, 0], ["TFRC", 2, 1], ["TG", 1, 3],
  ]);
});

test("letter keys walk the genes starting with that letter and wrap", async () => {
  const { nextIndexByLetter } = await import("../lib/l1-design");
  const g = [{ gene_symbol: "ABCA8" }, { gene_symbol: "TFRC" }, { gene_symbol: "TFRC" }, { gene_symbol: "TG" }];
  assert.equal(nextIndexByLetter(g, "t", -1), 1);     // from nothing selected
  assert.equal(nextIndexByLetter(g, "T", 1), 2);      // same letter again walks on
  assert.equal(nextIndexByLetter(g, "T", 3), 1);      // and wraps past the end
  assert.equal(nextIndexByLetter(g, "a", 1), 0);
  assert.equal(nextIndexByLetter(g, "z", 0), -1);     // no such letter in this filter
  assert.equal(nextIndexByLetter(g, "ab", 0), -1);    // not a single letter
  assert.equal(nextIndexByLetter([], "a", 0), -1);
});

test("a topology is used only when it describes THIS member's ordered protein", async () => {
  const { l1MemberTopology } = await import("../lib/l1-design");
  const rows = [
    { candidate_id: "l1-p2131", per_residue_topology: "I".repeat(760), ordered_length_aa: "760" },
    { candidate_id: "l1-p2617", per_residue_topology: "I".repeat(732), ordered_length_aa: "732" },
    // Another tranche's member for the same gene: never this member's topology.
    { candidate_id: "l2-p4210", per_residue_topology: "I".repeat(763), ordered_length_aa: "763" },
  ];
  const human = { design_id: "l1-p2131", ordered_length_aa: 760 };
  const cyno = { design_id: "l1-p2617", ordered_length_aa: 732 };
  assert.equal(l1MemberTopology(rows, human)?.candidate_id, "l1-p2131");
  assert.equal(l1MemberTopology(rows, cyno)?.candidate_id, "l1-p2617");
  // A length disagreement means the two halves describe different proteins — refuse it
  // rather than draw the insert flag against the wrong bands.
  assert.equal(l1MemberTopology(rows, { design_id: "l1-p2131", ordered_length_aa: 999 }), null);
  assert.equal(l1MemberTopology(rows, { design_id: "l1-p9999", ordered_length_aa: 760 }), null);
  assert.equal(l1MemberTopology(rows, { design_id: null, ordered_length_aa: 760 }), null);
  assert.equal(l1MemberTopology([], human), null);
  assert.equal(
    l1MemberTopology([{ candidate_id: "l1-p2131", per_residue_topology: "" }], human),
    null,
  );
});

test("the legend names only the topology states the member actually has", async () => {
  const { topologyStatesPresent } = await import("../lib/l1-design");
  assert.deepEqual(topologyStatesPresent("SSSOOOMMMIII"), ["M", "O", "I", "S"]);
  assert.deepEqual(topologyStatesPresent("IIII"), ["I"]);
  assert.deepEqual(topologyStatesPresent(""), []);
});

test("a member's tab is named for the proteoform it encodes, falling back to candidate_set", async () => {
  const { l1MemberTabLabel } = await import("../lib/l1-design");
  const human = { candidate_set: "library_reference", species: "human" };
  const cyno = { candidate_set: "ortholog", species: "cyno" };
  // With a topology row the cohort decides, which is the only field that knows a
  // library_reference member is really a UniProt isoform.
  assert.equal(l1MemberTabLabel(human, { cohort: "human_canonical" }), "Canonical");
  assert.equal(l1MemberTabLabel(human, { cohort: "human_isoform", topology_acc: "P02786-2" }), "Isoform 2");
  assert.equal(l1MemberTabLabel(cyno, { cohort: "cyno_ortholog" }), "Cyno ortholog");
  // Without one, the index's own fields.
  assert.equal(l1MemberTabLabel(human), "Reference");
  assert.equal(l1MemberTabLabel(cyno), "Cyno ortholog");
  assert.equal(l1MemberTabLabel({ candidate_set: "isoform", species: "human" }), "Isoform");
});

test("every current pick gets a flag, ordered along the sequence and labelled by arm", async () => {
  const { insertFlags, armLabel } = await import("../components/L1Review/L1TopologyStrip");
  const arm = (id: string, r: number, primary = true): L1Site =>
    site({ site_id: id, insert_after_residue: r, is_primary: primary, residue_before: "H", residue_after: "D" });
  const flags = insertFlags([arm("l1-p1088-a2", 151), arm("l1-p1088-a1", 55), arm("l1-p1088-a3", 80)], 200);
  assert.deepEqual(flags.map((f) => f.label), ["a1", "a3", "a2"]);
  assert.deepEqual(flags.map((f) => f.insertAfterResidue), [55, 80, 151]);
  // Alternatives are not flagged: the strip's job is "where does THIS member's tag go".
  assert.equal(insertFlags([arm("l1-p1088-a1", 55), arm("alt", 70, false)], 200).length, 1);
  // A site id without an arm suffix is labelled by its residue, not by the raw id —
  // `l1-p2089-res1-igk_tag` would otherwise put 20 characters on a 6px mark.
  assert.equal(armLabel("l1-p2089-res1-igk_tag"), null);
  assert.equal(armLabel("l1-p1088-a2"), "a2");
  assert.equal(insertFlags([arm("l1-p2089-res1-igk_tag", 1)], 299)[0].label, "1");
  assert.equal(insertFlags([arm("l1-p0001-nterm", 0)], 299)[0].label, "N");
});

test("the strip reuses the gene pages' topology bands and flags the insert over them", async () => {
  const { L1TopologyStrip, insertFlags } = await import("../components/L1Review/L1TopologyStrip");
  const flags = insertFlags(
    [site({ site_id: "l1-p1088-a1", insert_after_residue: 55, residue_before: "H", residue_after: "D" })],
    200,
  );
  const html = renderToStaticMarkup(
    React.createElement(L1TopologyStrip, {
      topology: "I".repeat(50) + "M".repeat(20) + "O".repeat(130),
      flags, gene: "LHFPL6", variantLabel: "Canonical", nAlternatives: 2,
    }),
  );
  // The bands are TOPOLOGY_COLORS straight from lib/structure-viewer-types, the same
  // palette the gene pages' strip and 3D cartoon read — not a second scheme.
  assert.match(html, /#A9CFA8/); // intracellular
  assert.match(html, /#FFD579/); // TM helix
  assert.match(html, /#8878C8/); // extracellular
  assert.match(html, /Intracellular/);
  assert.match(html, /tag insert/);
  assert.match(html, /between H55 and D56/);
  assert.match(html, /2 alternatives not drawn here/);
  // Positioned on the boundary the cassette goes into, as a fraction of this member's
  // own length — 55 of 200.
  assert.match(html, /left:27\.5%/);
});

test("a member with no topology gets no strip rather than one drawn from something else", async () => {
  const { L1TopologyStrip } = await import("../components/L1Review/L1TopologyStrip");
  assert.equal(
    renderToStaticMarkup(
      React.createElement(L1TopologyStrip, {
        topology: "", flags: [], gene: "X", variantLabel: "Canonical", nAlternatives: 0,
      }),
    ),
    "",
  );
});
