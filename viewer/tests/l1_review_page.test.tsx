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
import { ReviewPanel, SiteCard, structureTabLabel } from "../components/L1Review/L1Review";
import {
  currentMemberModels,
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
      auth: { take: () => "ts-token", status: "ready" }, reviewer: "Becca", onEditName: () => {}, pickedResidue: null,
      drafts: {}, setDrafts: () => {}, onSaved: () => {}, ...over,
    }),
  );

const withDraft = (draft: Record<string, unknown>) =>
  panel({ drafts: { "l1-p0006": { mode: "", reason: "", alt: { residue: "", placement: "internal", cassette: "" }, ...draft } as never } });

test("the verdict is three toggle buttons, and Submit waits for a choice", () => {
  const html = panel();
  // Buttons, not radios: a focused radio swallowed the page's arrow keys.
  assert.equal((html.match(/<input type="radio"/g) ?? []).length, 0);
  assert.equal((html.match(/aria-pressed="false"/g) ?? []).length, 3);
  for (const label of ["Site looks right", "Concern", "Suggest another site"]) assert.match(html, new RegExp(label));
  assert.match(html, /<button type="button"[^>]*disabled=""[^>]*>Submit<\/button>/);
  const chosen = withDraft({ mode: "good" });
  assert.doesNotMatch(chosen, /disabled=""[^>]*>Submit/);
  assert.match(chosen, /aria-pressed="true"[^>]*>Site looks right/);
  assert.doesNotMatch(html, /token/i);
  // The comment box is one line until it is used.
  assert.match(html, /<textarea[^>]*rows="1"/);
  assert.match(withDraft({ mode: "no", reason: "pore" }), /<textarea[^>]*rows="3"/);
});

test("a verdict asks which arm it is about, defaulting to the current pick", () => {
  const html = withDraft({ mode: "no" });
  assert.match(html, /a1 — between V94 and S95/);
  assert.match(html, /a2 — between H151 and D152 \(alternative\)/);
  assert.match(html, /the member as a whole/);
  assert.match(html, /<option value="l1-p0006-a1" selected="">/);
  assert.ok(html.indexOf("the member as a whole") < html.indexOf(">Submit<"));
  assert.match(html, /What should change, and why\?/);
});

test("'Suggest another site' alone shows the residue field without a placement dropdown", () => {
  assert.doesNotMatch(panel(), /after residue \(ordered-protein numbering\)/);
  const html = withDraft({ mode: "alt" });
  assert.match(html, /after residue \(ordered-protein numbering\)/);
  assert.match(html, /<input[^>]*type="number"/);
  assert.match(html, /or click a residue on the structure/);
  assert.doesNotMatch(html, /placement/);
  // No free-text cassette; a select appears only when the member's sites carry real options.
  assert.doesNotMatch(html, /cassette variant/);
  assert.doesNotMatch(html, /tag site<select/);
});

test("without a name the card says so, but nothing typed is locked away", () => {
  const html = panel({ reviewer: "   " });
  assert.match(html, /Add your name/);
  assert.doesNotMatch(html, /<textarea[^>]*disabled/);
  assert.match(panel(), /Reviewing as[\s\S]*Becca/);
});

test("a write sends the name and the Turnstile token in the body, and no token header", async () => {
  const { submitL1Review } = await import("../lib/l1-design");
  const seen: { headers: Record<string, string>; body: Record<string, unknown> }[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    seen.push({ headers: init.headers as Record<string, string>, body: JSON.parse(String(init.body)) });
    return new Response(JSON.stringify({ ok: true, review_id: "r1", created_at: "2026-11-22T10:00:00Z" }), { status: 201 });
  }) as typeof fetch;
  try {
    const r = await submitL1Review("https://api.test", "ts-token", { kind: "verdict", reviewer: "Ada" });
    assert.deepEqual(r, { ok: true, id: "r1", created_at: "2026-11-22T10:00:00Z" });
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.equal(seen[0].body.turnstile_token, "ts-token");
  assert.equal(seen[0].body.reviewer, "Ada");
  assert.ok(!Object.keys(seen[0].headers).some((h) => /review-token/i.test(h)));
});

test("Worker error codes read as instructions, not codes", async () => {
  const { reviewErrorMessage } = await import("../lib/l1-design");
  assert.match(reviewErrorMessage("invalid_reviewer"), /Add your name/);
  assert.match(reviewErrorMessage("turnstile_failed"), /submit again/);
  assert.match(reviewErrorMessage("rate_limited"), /Too many submissions/);
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
  // Fallback when library_designed_topology is absent (e.g. C5orf15): matches only on exact sequence_sha256.
  const canonicalFallback = [{ per_residue_topology: "S".repeat(45) + "O".repeat(153) + "M".repeat(17) + "I".repeat(50), ordered_length_aa: "265", sequence_sha256: "deadbeef" }];
  assert.equal(
    l1MemberTopology(canonicalFallback, { design_id: "l1-p0210", ordered_length_aa: 265, sequence_sha256: "deadbeef" })?.per_residue_topology?.length,
    265,
  );
  assert.equal(
    l1MemberTopology(canonicalFallback, { design_id: "l1-p0210", ordered_length_aa: 265, sequence_sha256: "other" }),
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

// ------------------------------------------------- filters, SP status, UniProt comparison

test("SP status comes from the export when present, else from the primary pick", async () => {
  const { indexSpStatus } = await import("../lib/l1-design");
  const row = (rung: string, over: Record<string, unknown> = {}) => ({ rung, ...over });
  assert.equal(indexSpStatus(row("N after SP")), null, "an index without pick_leader says nothing");
  assert.equal(indexSpStatus(row("N after SP", { pick_leader: "igk" })), "igk_swap");
  assert.equal(indexSpStatus(row("N at residue 1, multipass", { pick_leader: "igk" })), "igk_res1");
  assert.equal(indexSpStatus(row("N after SP", { pick_leader: null })), "native");
  assert.equal(indexSpStatus(row("internal", { pick_leader: null })), null);
  assert.equal(indexSpStatus(row("internal", { pick_leader: null, sp_status: "none" })), "none");
});

test("GLP2R reads as the Igκ swap, with the SP end once the export carries it", async () => {
  const { memberSp } = await import("../lib/l1-design");
  const glp2r = member({
    gene_symbol: "GLP2R", rung: "N after SP", ordered_length_aa: 553,
    sites: [site({ site_id: "l1-p0724-nsp-68", rung: "N after SP", insert_after_residue: 68, leader: "igk", decision: "igk_swap", status: "built" })],
  });
  const now = memberSp(glp2r);
  assert.equal(now.status, "igk_swap");
  assert.match(now.text, /Igκ leader replaces the native N-terminus \(native residues 1–68\)/);
  assert.deepEqual(now.band, { from: 1, to: 68, kind: "replaced" });
  const later = memberSp({ ...glp2r, sp_status: "igk_swap", native_sp_last_residue: 66, sp_evidence: "DeepTMHMM v2 + mouse ortholog" });
  assert.match(later.text, /Igκ leader replaces native SP 1–66; native 1–68 not in the construct/);
  assert.match(later.source, /mouse ortholog/);
  const kept = memberSp(member({ rung: "N after SP", sites: [site({ insert_after_residue: 24, leader: null, rung: "N after SP" })] }), "SSSSSSSSSSSSSSSSSSSSSSOOOO");
  assert.match(kept.text, /native signal peptide \(cleaved 1–22\), kept; tag after residue 24/);
});

test("filters: SP type, UniProt difference and reviewed-by-me; search matches class and rung words", () => {
  const rows = [
    { ...m("l1-m0001", "GLP2R", "N after SP", "multipass (other)", ["built"]), pick_leader: "igk", matches_uniprot_canonical: 0 },
    { ...m("l1-m0002", "AXL", "N after SP", "single-pass type I", ["built"]), pick_leader: null, matches_uniprot_canonical: 1 },
    { ...m("l1-m0003", "ADRB2", "C-terminal", "GPCR", ["built"]), pick_leader: null, matches_uniprot_canonical: 1 },
  ];
  const genes = (f: Parameters<typeof filterIndex>[1]) => filterIndex(rows, f).map((x) => x.gene_symbol);
  assert.deepEqual(genes({ sp: "igk_swap" }), ["GLP2R"]);
  assert.deepEqual(genes({ sp: "native" }), ["AXL"]);
  assert.deepEqual(genes({ diff: "yes" }), ["GLP2R"]);
  assert.deepEqual(genes({ diff: "no" }), ["ADRB2", "AXL"]);
  const mine = new Set(["l1-p0002"]);
  assert.deepEqual(genes({ reviewed: "mine", reviewedByMe: mine }), ["AXL"]);
  assert.deepEqual(genes({ reviewed: "notmine", reviewedByMe: mine }), ["ADRB2", "GLP2R"]);
  assert.deepEqual(genes({ query: "gpcr" }), ["ADRB2"]);
  assert.deepEqual(genes({ query: "c-term" }), ["ADRB2"]);
  assert.deepEqual(genes({ query: "igk" }), ["GLP2R"]);
  // Two letters still search gene symbols only, so "AX" does not drag in classes.
  assert.deepEqual(genes({ query: "ax" }), ["AXL"]);
});

test("UniProt differences read as sentences", async () => {
  const { uniprotDiffLines, uniprotDiffers } = await import("../lib/l1-design");
  assert.equal(uniprotDiffers({}), null);
  assert.equal(uniprotDiffers({ matches_uniprot_canonical: 0 }), true);
  assert.deepEqual(
    uniprotDiffLines([
      { kind: "substitution", member_start: 412, member_end: 412, uniprot_start: 412, uniprot_end: 412, member_aa: "V", uniprot_aa: "A" },
      { kind: "n_truncation", member_start: null, member_end: null, uniprot_start: 1, uniprot_end: 24 },
    ]),
    ["member 412 differs from UniProt 412 (A → V)", "member starts later: UniProt 1–24 not ordered"],
  );
});

// ------------------------------------------- arms and residues on either model
//
// Since the page opens on the fold, site marks and residue clicks have to work through
// the fold's own numbering, not only on the native model (regression, 2026-11-22: "i can
// no longer click a1 / 2 3 and see it on the protein"; "same with alt site suggestion").

test("residues map through the fold: around the cassette, and not where an Igκ leader replaced them", async () => {
  const { l1ResidueSegments, memberToModel, modelToMember } = await import("../lib/l1-design");
  // GLP2R-like: Igκ swap after 68, cassette 24–74 in a 559-residue model of a 553-aa member.
  const glp = member({ ordered_length_aa: 553, sites: [site({ site_id: "nsp", insert_after_residue: 68, leader: "igk" })] });
  const fold = { kind: "tagged" as const, site_id: "nsp", residue_offset: 0, cassette_first_model_residue: 24, cassette_last_model_residue: 74, model_length_aa: 559 };
  const segs = l1ResidueSegments(glp, fold);
  assert.deepEqual(segs, [{ unpLo: 69, unpHi: 553, offset: 6 }]);
  assert.equal(memberToModel(68, segs), null, "the swapped N-terminus is not in the fold");
  assert.equal(memberToModel(195, segs), 201);
  assert.equal(modelToMember(201, segs), 195);
  assert.equal(modelToMember(30, segs), null, "a cassette residue is not a member residue");
  // An internal arm with no leader: native 1..389, cassette, native 390.. shifted.
  const abca8 = member({ ordered_length_aa: 1621, sites: [site({ site_id: "a1", insert_after_residue: 389, leader: null })] });
  const fold1 = { kind: "tagged" as const, site_id: "a1", residue_offset: 0, cassette_first_model_residue: 390, cassette_last_model_residue: 440, model_length_aa: 1672 };
  const s1 = l1ResidueSegments(abca8, fold1);
  assert.equal(memberToModel(389, s1), 389);
  assert.equal(memberToModel(1012, s1), 1063);
  assert.equal(modelToMember(1063, s1), 1012);
  // Native: one shifted segment.
  assert.deepEqual(l1ResidueSegments(abca8, { kind: "native", site_id: null, residue_offset: 3, cassette_first_model_residue: null, cassette_last_model_residue: null, model_length_aa: 1624 }), [{ unpLo: 1, unpHi: 1621, offset: 3 }]);
});

test("strip flags and tag-site cards are buttons that focus an arm", async () => {
  const { L1TopologyStrip, insertFlags } = await import("../components/L1Review/L1TopologyStrip");
  const flags = insertFlags(twoArms, 400);
  const html = renderToStaticMarkup(
    React.createElement(L1TopologyStrip, {
      topology: "O".repeat(400), flags, gene: "G", variantLabel: "ref", nAlternatives: 0,
      focusSiteId: "l1-p0006-a1", onFlagClick: () => {}, suggestedResidue: 250,
    }),
  );
  assert.match(html, /<button[^>]*title="a1 — tag insert[^"]*"[^>]*aria-pressed="true"/);
  assert.match(html, /title="your suggested site: after residue 250"/);
  const card = renderToStaticMarkup(React.createElement(SiteCard, { site: twoArms[0], length: 400, focused: false, onShow: () => {} }));
  assert.match(card, /<button[^>]*aria-pressed="false"[^>]*>show on structure<\/button>/);
  const clickableStrip = renderToStaticMarkup(
    React.createElement(L1TopologyStrip, {
      topology: "O".repeat(400), flags, gene: "G", variantLabel: "ref", nAlternatives: 0,
      onPickResidue: () => {},
    }),
  );
  assert.match(clickableStrip, /click bar to suggest a site/);
});

test("multiple fold tabs name their arm and residue so identical pLDDT/verdict tabs stay distinct", () => {
  const foldA = { kind: "tagged" as const, site_id: "l1-p0006-a1", mean_plddt: 69.2, refold_verdict: "pass", note: null };
  const foldB = { kind: "tagged" as const, site_id: "l1-p0006-a2", mean_plddt: 69.1, refold_verdict: "pass", note: null };
  const foldNoArm = { kind: "tagged" as const, site_id: "l1-p0006-internal-94", mean_plddt: 72.0, refold_verdict: "fail", note: null };
  const foldFromNote = { kind: "tagged" as const, site_id: null, mean_plddt: 68.8, refold_verdict: "fail", note: "rung nterm; insert after 29; ALFA buried" };
  const native = { kind: "native" as const, site_id: null, mean_plddt: 84.4, refold_verdict: null, note: null };
  // Single fold stays concise.
  assert.equal(structureTabLabel(foldA, twoArms, false), "Fold · pLDDT 69 · pass");
  // Multi-fold disambiguates by arm and insertion residue.
  assert.equal(structureTabLabel(foldA, twoArms, true), "Fold (a1 · 94) · pLDDT 69 · pass");
  assert.equal(structureTabLabel(foldB, twoArms, true), "Fold (a2 · 151) · pLDDT 69 · pass");
  // A site without an -aK suffix falls back to its insertion residue; an unlisted fold reads `insert after N` from note.
  assert.equal(structureTabLabel(foldNoArm, [site({})], true), "Fold (after 94) · pLDDT 72 · fail");
  assert.equal(structureTabLabel(foldFromNote, [], true), "Fold (after 29) · pLDDT 69 · fail");
  assert.equal(structureTabLabel(native, twoArms, true), "Native · pLDDT 84");
});

test("currentMemberModels keeps only current-pick folds and native, excluding earlier sweep refolds (GLP1R / ADAM15)", () => {
  const mk = (id: string, kind: "tagged" | "native", site_id: string | null, refold_verdict: string | null) => ({
    structure_id: id, kind, site_id, source: "colabfold", release: null, r2_key: null, model_url: null,
    proteoform_match: null, residue_offset: 0, is_chosen: true, mean_plddt: 69,
    cassette_first_model_residue: 25, cassette_last_model_residue: 75, refold_verdict, note: null,
  });
  const glp1rSites = [site({ site_id: "l1-p0723-nsp-24", is_primary: true, insert_after_residue: 24 })];
  const got = currentMemberModels(
    [
      mk("native", "native", null, null),
      mk("fail-29", "tagged", null, "fail"),
      mk("fail-25", "tagged", null, "fail"),
      mk("pass-24", "tagged", "l1-p0723-nsp-24", "pass"),
    ],
    glp1rSites,
  );
  assert.deepEqual(got.map((x) => x.structure_id), ["pass-24", "native"]);
});

test("verdict buttons advertise = / - / . shortcuts and SiteCard chips semicolon-delimited detail", () => {
  const goodHtml = withDraft({ mode: "good" });
  assert.match(goodHtml, /Site looks right[^<]*<kbd[^>]*>=<\/kbd>/);
  assert.match(goodHtml, /Concern[^<]*<kbd[^>]*>-<\/kbd>/);
  assert.match(goodHtml, /Suggest another site[^<]*<kbd[^>]*>\.<\/kbd>/);
  assert.match(goodHtml, /class="segOn segGood"/);
  assert.match(withDraft({ mode: "no" }), /class="segOn segNo"/);
  const card = renderToStaticMarkup(React.createElement(SiteCard, { site: site({}), length: 152 }));
  assert.match(card, /<ul class="detailChips"><li>internal_loop<\/li><li>refold verdict pending<\/li><\/ul>/);
});

test("redacted public provenance is hidden cleanly on SiteCard and memberSp explains Igκ vs native SP", async () => {
  const { memberSp } = await import("../lib/l1-design");
  const redactedCard = renderToStaticMarkup(
    React.createElement(SiteCard, {
      site: site({
        decided_by: "withheld: internal design record",
        implemented_by: "withheld: internal design record",
        rationale: null,
        reason: null,
        source: { pr: null, pr_state: null, commit: "withheld", path: "withheld: internal design record" },
      }),
      length: 820,
    }),
  );
  assert.doesNotMatch(redactedCard, /withheld: internal design record/);
  assert.match(redactedCard, /construct &amp; site details/);
  assert.match(redactedCard, /Internal design scores and provenance are withheld/);

  const swap = memberSp(member({ rung: "N after SP", sites: [site({ leader: "igk", insert_after_residue: 68, reason: null })] }));
  assert.match(swap.why ?? "", /Igκ leader/);
  const native = memberSp(member({ rung: "N after SP", sites: [site({ leader: null, insert_after_residue: 24, reason: null })] }));
  assert.match(native.why ?? "", /Native SP retained/);
  const explicit = memberSp(member({ rung: "N after SP", sp_evidence: "native cleavage buried ALFA", sites: [site({ leader: "igk", reason: null })] }));
  assert.equal(explicit.why, "native cleavage buried ALFA");
});
