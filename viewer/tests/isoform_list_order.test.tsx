/*
 * Render test: the §Isoforms variants table lists alt isoforms in NUMERIC order.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/isoform_list_order.test.tsx
 *
 * The API returns `isoform_topologies` ordered by `uniprot_acc_full ASC` — a
 * TEXT sort — so `P15941-10` precedes `P15941-2`. The card rendered that order
 * verbatim, so MUC1's table opened on "Isoform P15941-10 / -11 / -12" and the
 * low-numbered isoforms were 8 rows down. It was reported as the viewer showing
 * library isoforms or the wrong record; it was neither, which is the reason this
 * is worth a test rather than a one-line fix. Record history confirmed the 16
 * ids and their order were identical in every revision back to the first.
 *
 * `isoform_cap_order.test.ts` covers the 3D tab strip's 3-isoform cap over the
 * same helper. This covers the full, uncapped table — a different surface that
 * was still unsorted after the cap was fixed.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { IsoformsCard } from "../components/surfaceome/IsoformsCard/IsoformsCard";
import type { IsoformTopology, SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

/** A minimal IsoformTopology — only `isoform_id` matters to ordering. */
function iso(id: string): IsoformTopology {
  return {
    isoform_id: id,
    uniprot_acc: id,
    tm_helix_count: 1,
    n_terminal_orientation: "extracellular",
    c_terminal_orientation: "cytoplasmic",
    signal_peptide_length: 0,
    ecd_length_residues: 10,
    icd_length_residues: 10,
    per_residue_topology: "OOOOOMMMMMIIIII",
    tool_version: "deeptmhmm-1.0.24",
    retrieved_at: "2026-05-27T02:01:01Z",
  } as IsoformTopology;
}

/** MUC1's real ids, in the TEXT order the API serves them. */
const MUC1_SERVED_ORDER = [
  "P15941-10", "P15941-11", "P15941-12", "P15941-13", "P15941-14",
  "P15941-15", "P15941-16", "P15941-17", "P15941-2", "P15941-3",
  "P15941-4", "P15941-5", "P15941-6", "P15941-7", "P15941-8", "P15941-9",
];

/** `baseRecord()` is cast `as unknown as SurfaceomeRecord` and omits `gene`,
 *  which IsoformsCard reads — so set it here rather than in the shared fixture,
 *  where it would change every other render test's starting point. */
function muc1Record(ids: string[], canonical = "P15941"): SurfaceomeRecord {
  const rec: SurfaceomeRecord = baseRecord();
  rec.gene = {
    hgnc_symbol: "MUC1",
    hgnc_id: "HGNC:7508",
    uniprot_acc: canonical,
    ncbi_gene_id: 4582,
    ensembl_gene: "ENSG00000185499",
  };
  // The fixture's deterministic_features carries only canonical_topology, and
  // the card reads orthologs/paralogs unguarded. Empty, not absent — this test
  // is about isoform ordering, so every other row type stays off the table.
  rec.deterministic_features.orthologs = { mouse: [], cynomolgus: [] };
  rec.deterministic_features.paralogs = [];
  rec.deterministic_features.isoform_topologies = ids.map(iso);
  rec.deterministic_features.isoform_topologies_checked = true;
  return rec;
}

function renderWith(ids: string[], canonical = "P15941"): string {
  return renderToStaticMarkup(
    <IsoformsCard rec={muc1Record(ids, canonical)} n={6} fgLibrary={null} />,
  );
}

/** The isoform ids in the order they appear in the rendered markup. */
function renderedOrder(html: string, canonical = "P15941"): string[] {
  const re = new RegExp(`${canonical}-\\d+`, "g");
  const seen: string[] = [];
  for (const m of html.matchAll(re)) {
    if (!seen.includes(m[0])) seen.push(m[0]);
  }
  return seen;
}

test("MUC1: the table lists isoforms 2..17, not 10, 11, 12 first", () => {
  const order = renderedOrder(renderWith(MUC1_SERVED_ORDER));
  assert.equal(order.length, 16, "all 16 alt isoforms render");
  assert.deepEqual(
    order.slice(0, 3),
    ["P15941-2", "P15941-3", "P15941-4"],
    "the table must open on the low-numbered isoforms",
  );
  assert.equal(order.at(-1), "P15941-17");
  // The whole sequence, as a number, must be ascending.
  const nums = order.map((id) => Number(id.split("-")[1]));
  assert.deepEqual(nums, [...nums].sort((a, b) => a - b));
});

test("the served TEXT order really is the inverted one (the bug's premise)", () => {
  // Guards against the fixture silently being pre-sorted, which would make the
  // test above pass without the component doing anything.
  assert.deepEqual(MUC1_SERVED_ORDER, [...MUC1_SERVED_ORDER].sort());
  assert.ok("P15941-10" < "P15941-2");
});

test("the canonical accession is still excluded from the alt list", () => {
  // Some records (TACSTD2 and friends) carry the canonical inside
  // isoform_topologies; it must not appear as an "alt isoform" row.
  const html = renderWith(["P15941", "P15941-3", "P15941-2"]);
  assert.deepEqual(renderedOrder(html), ["P15941-2", "P15941-3"]);
});

test("sorting does not mutate the record's own array", () => {
  // `.filter()` copies, so the sort is on the copy — but if that filter is ever
  // removed, an in-place sort would reorder the array the topology bars and the
  // legend read from.
  const rec = muc1Record(MUC1_SERVED_ORDER);
  renderToStaticMarkup(<IsoformsCard rec={rec} n={6} fgLibrary={null} />);
  assert.deepEqual(
    rec.deterministic_features.isoform_topologies.map((i) => i.isoform_id),
    MUC1_SERVED_ORDER,
    "the record must come back in the order it arrived",
  );
});
