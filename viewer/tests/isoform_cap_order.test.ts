/*
 * The 3D tab strip caps at 3 isoforms and must keep the MAJOR ones.
 *
 * The suffix has to be compared as a number. The API returns `isoform_topologies` ordered
 * by `uniprot_acc_full ASC` — a TEXT sort — so `P15941-10` precedes `P15941-2`, and a gene
 * with ten or more isoforms had the cap keep 10, 11 and 12. MUC1 is the case that surfaced
 * it: its tabs showed isoforms 10-12 and not Isoform 8, which is the proteoform the
 * library orders, so the one isoform that mattered was the one excluded.
 *
 * Failure mode is silent — three plausible isoform tabs appear either way, and nothing on
 * the card says the major ones are missing.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { isoformNumber } from "../components/surfaceome/GeneHeader/GeneHeader";

/** The cap as the component applies it, over isoform ids alone. */
function cappedIsoforms(ids: string[], canonical: string, cap = 3): string[] {
  return ids
    .filter((id) => id !== canonical)
    .slice()
    .sort((a, b) => isoformNumber(a) - isoformNumber(b))
    .slice(0, cap);
}

test("isoformNumber parses the suffix as a number", () => {
  assert.equal(isoformNumber("P15941-2"), 2);
  assert.equal(isoformNumber("P15941-10"), 10);
  // A bare accession has no suffix to parse and must sort LAST, not first.
  assert.equal(isoformNumber("P15941"), Number.POSITIVE_INFINITY);
});

test("isoformNumber orders 2 before 10, which a text sort does not", () => {
  assert.ok(isoformNumber("P15941-2") < isoformNumber("P15941-10"));
  // The bug, stated as the assertion that used to hold:
  assert.ok("P15941-10" < "P15941-2", "text sort really does invert these");
});

test("MUC1: the cap keeps the major isoforms, not 10-12", () => {
  const ids = [
    "P15941-10",
    "P15941-11",
    "P15941-12",
    "P15941-2",
    "P15941-3",
    "P15941-8",
  ];
  assert.deepEqual(cappedIsoforms(ids, "P15941"), [
    "P15941-2",
    "P15941-3",
    "P15941-8",
  ]);
});

test("the canonical is still excluded before the cap is applied", () => {
  // Some records (TACSTD2 and friends) carry the canonical inside isoform_topologies;
  // including it would surface a duplicate tab pointing at the same AFDB model.
  const ids = ["P15941", "P15941-2", "P15941-3", "P15941-8"];
  const out = cappedIsoforms(ids, "P15941");
  assert.ok(!out.includes("P15941"));
  assert.equal(out.length, 3);
});

test("an unparseable id does not displace a numbered one", () => {
  const ids = ["P15941-weird", "P15941-4", "P15941-2", "P15941-3"];
  assert.deepEqual(cappedIsoforms(ids, "P15941"), [
    "P15941-2",
    "P15941-3",
    "P15941-4",
  ]);
});

test("fewer isoforms than the cap returns all of them, still ordered", () => {
  assert.deepEqual(cappedIsoforms(["P15941-5", "P15941-2"], "P15941"), [
    "P15941-2",
    "P15941-5",
  ]);
});
