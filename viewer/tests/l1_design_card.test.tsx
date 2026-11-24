/*
 * The L1 design card: payload parsing, site labels, model URLs, and the member block.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs tests/l1_design_card.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { L1MemberBlock, ObligatePartnerAbsence } from "../components/surfaceome/L1DesignCard/L1DesignCard";
import {
  fetchL1DesignResult,
  l1AbsenceReason,
  l1SiteLabel,
  l1StructureUrl,
  parseL1Design,
  type L1Site,
} from "../lib/l1-design";
import type { CoReceptorRequirements } from "../lib/surfaceome-types";
import { STRUCTURES_BASE } from "../lib/structure-viewer-types";

const site = (over: Partial<L1Site>): L1Site => ({
  site_id: "l1-m0001-cterm-760",
  rung: "C-terminal",
  insert_after_residue: 760,
  residue_before: null,
  residue_after: null,
  leader: null,
  cassette: "51-aa tandem",
  cassette_aa: 51,
  rank: null,
  status: "built",
  status_detail: "C-terminal",
  source: { pr: 1, pr_state: "open", commit: "a".repeat(40), path: "design/cterm.tsv" },
  decided_by: "Becca, test",
  implemented_by: "builder",
  reason: null,
  ...over,
});

const payload = {
  gene_symbol: "GENEA",
  load: { load_version: "l1d-0123456789abcdef", created_at: "2026-11-12T00:00:00Z" },
  members: [
    {
      member_id: "l1-m0001", design_id: "l1-p0001", gene_symbol: "GENEA", species: "cyno",
      candidate_set: "ortholog", rung: "C-terminal", ordered_length_aa: 760,
      sites: [site({}), { ...site({}), site_id: "bogus", status: "shipped" }],
      structures: [
        { structure_id: "n", kind: "native", site_id: null, source: "alphafold_db", release: "r",
          r2_key: null, model_url: "https://alphafold.example/AF-X.pdb", proteoform_match: "identical",
          residue_offset: 0, is_chosen: true, mean_plddt: 81.2, cassette_first_model_residue: null,
          cassette_last_model_residue: null, note: null },
        { structure_id: "t", kind: "tagged", site_id: "l1-m0001-cterm-760", source: "colabfold_tagged",
          release: "2026-11-12", r2_key: "library-colabfold-tagged/2026-11-12/l1-m0001.pdb", model_url: null,
          proteoform_match: "tagged_construct", residue_offset: 0, is_chosen: true, mean_plddt: 70.4,
          cassette_first_model_residue: 761, cassette_last_model_residue: 811, note: null },
      ],
    },
    { nonsense: true },
  ],
};

test("parse drops malformed members and sites with an unknown status", () => {
  const d = parseL1Design(payload);
  assert.ok(d);
  assert.equal(d.members.length, 1);
  assert.deepEqual(d.members[0].sites.map((s) => s.site_id), ["l1-m0001-cterm-760"]);
  assert.equal(parseL1Design({ members: [] }), null);
  assert.equal(parseL1Design("<html>"), null);
});

test("site labels name the junction in member numbering", () => {
  assert.equal(l1SiteLabel(site({}), 760), "after the last residue (760)");
  assert.equal(
    l1SiteLabel(site({ insert_after_residue: 34, residue_before: "E", residue_after: "S" }), 894),
    "between E34 and S35",
  );
  assert.equal(l1SiteLabel(site({ insert_after_residue: null }), 894), "no site");
  assert.equal(l1SiteLabel(site({ insert_after_residue: 0 }), 894), "before residue 1");
});

test("our models resolve under the structures bucket, AFDB models at their URL", () => {
  assert.equal(
    l1StructureUrl({ r2_key: "/library-colabfold-tagged/x.pdb", model_url: null }),
    `${STRUCTURES_BASE}/library-colabfold-tagged/x.pdb`,
  );
  assert.equal(l1StructureUrl({ r2_key: null, model_url: "https://a/b.pdb" }), "https://a/b.pdb");
  assert.equal(l1StructureUrl({ r2_key: null, model_url: null }), null);
});

test("member block shows rung, status, provenance and both models", () => {
  const d = parseL1Design(payload)!;
  const html = renderToStaticMarkup(React.createElement(L1MemberBlock, { m: d.members[0] }));
  assert.match(html, /l1-m0001/);
  assert.match(html, /cyno ortholog/);
  assert.match(html, />built</);
  assert.match(html, /decided by/);
  assert.match(html, /Becca, test/);
  assert.match(html, /Native model: AlphaFold DB, pLDDT 81/);
  assert.match(html, /Tagged refold \(l1-m0001-cterm-760\): ColabFold \(tagged\), pLDDT 70, cassette 761–811/);
  assert.match(html, /library-colabfold-tagged\/2026-11-12\/l1-m0001\.pdb/);
});

// --------------------------------------------------------------- no-design states

const coReceptor = (over: Partial<CoReceptorRequirements> = {}): CoReceptorRequirements => ({
  surface_expression_dependency: "required",
  partners: ["GENEB", "GENEC"],
  evidence_basis: "trafficking",
  rationale: "Gene X does not reach the surface as a monomer (a1_evi_04).",
  cited_evidence_ids: ["a1_evi_04"],
  ...over,
});

test("a non-member with an obligate partner is an explained exclusion", () => {
  assert.equal(
    l1AbsenceReason({ inFgLibrary: false, coReceptor: coReceptor() }),
    "obligate_partner",
  );
});

test("a library member is never an exclusion, whatever its dependency", () => {
  // A member with no published design is a gap in the load, so saying "excluded"
  // would be wrong in exactly the direction this card is meant to fix.
  assert.equal(l1AbsenceReason({ inFgLibrary: true, coReceptor: coReceptor() }), "unpublished");
});

test("a non-member without a required partner is an unexplained absence", () => {
  for (const dep of ["none", "modulatory", "unknown"] as const) {
    assert.equal(
      l1AbsenceReason({
        inFgLibrary: false,
        coReceptor: coReceptor({ surface_expression_dependency: dep }),
      }),
      "unpublished",
    );
  }
  assert.equal(l1AbsenceReason({ inFgLibrary: false, coReceptor: null }), "unpublished");
});

test("`required` with nothing to show is not dressed up as an exclusion", () => {
  assert.equal(
    l1AbsenceReason({
      inFgLibrary: false,
      coReceptor: coReceptor({ partners: [], rationale: "", cited_evidence_ids: [] }),
    }),
    "unpublished",
  );
  // Whitespace-only partners count as none.
  assert.equal(
    l1AbsenceReason({
      inFgLibrary: false,
      coReceptor: coReceptor({ partners: ["  "], rationale: "  ", cited_evidence_ids: [] }),
    }),
    "unpublished",
  );
});

test("the exclusion block names the partners, the basis and the rationale", () => {
  const html = renderToStaticMarkup(
    React.createElement(ObligatePartnerAbsence, { symbol: "GENEA", cr: coReceptor() }),
  );
  assert.match(html, /is not a v1 library member/);
  assert.match(html, /GENEB, GENEC/);
  assert.match(html, /Obligate partners/);
  assert.match(html, /does not reach the surface as a monomer/);
  // The host-line check is the actionable half: without it a reviewer cannot tell
  // what would have to change for the gene to be designable.
  assert.match(html, /host cell line does not\s+express/);
  // Never the old undifferentiated line.
  assert.doesNotMatch(html, /No L1 design is published/);
});

// ------------------------------------------------------ load-bearing fetch states

/** Stand in for one `/v1/l1-design/{sym}` response. */
function withFetch<T>(impl: typeof fetch, body: () => Promise<T>): Promise<T> {
  const real = globalThis.fetch;
  globalThis.fetch = impl;
  return body().finally(() => {
    globalThis.fetch = real;
  });
}
const ok = (payload: unknown): typeof fetch =>
  (async () => new Response(JSON.stringify(payload), { status: 200 })) as unknown as typeof fetch;

test("a load that covers the gene with no member is a real absence", async () => {
  const r = await withFetch(ok({ gene_symbol: "GENEA", load: payload.load, members: [] }), () =>
    fetchL1DesignResult("GENEA", "https://api.example"),
  );
  assert.equal(r.kind, "empty");
});

test("a 200 with no load is a FAILURE, not an absence", async () => {
  // The Worker's `l1Load` catches every D1 error and degrades to
  // `{ load: null, members: [] }` with a 200. Rendering that as "no design is
  // published" is the exact bug this card exists to stop, and it reached the
  // live site: a transient D1 hiccup blanked TFRC's two members.
  const r = await withFetch(ok({ gene_symbol: "TFRC", load: null, members: [] }), () =>
    fetchL1DesignResult("TFRC", "https://api.example"),
  );
  assert.equal(r.kind, "error");
});

test("a transport failure and a non-200 are failures, not absences", async () => {
  const thrown = await withFetch(
    (async () => {
      throw new TypeError("network");
    }) as unknown as typeof fetch,
    () => fetchL1DesignResult("GENEA", "https://api.example"),
  );
  assert.equal(thrown.kind, "error");
  const http500 = await withFetch(
    (async () => new Response("<html>", { status: 500 })) as unknown as typeof fetch,
    () => fetchL1DesignResult("GENEA", "https://api.example"),
  );
  assert.equal(http500.kind, "error");
});

test("a load with members is served as the design", async () => {
  const r = await withFetch(ok(payload), () => fetchL1DesignResult("GENEA", "https://api.example"));
  assert.equal(r.kind, "ok");
  assert.equal(r.kind === "ok" ? r.file.members.length : 0, 1);
});
