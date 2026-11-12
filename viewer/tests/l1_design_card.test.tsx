/*
 * The L1 design card: payload parsing, site labels, model URLs, and the member block.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs tests/l1_design_card.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { L1MemberBlock } from "../components/surfaceome/L1DesignCard/L1DesignCard";
import { l1SiteLabel, l1StructureUrl, parseL1Design, type L1Site } from "../lib/l1-design";
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
