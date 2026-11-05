import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import {
  baseAccession,
  isCounted,
  shardOf,
  type PresenceShard,
  type StudyIndex,
} from "../lib/surface-proteomics";

const DIR = path.join(process.cwd(), "public", "data", "surface-proteomics");
const index = JSON.parse(readFileSync(path.join(DIR, "studies.json"), "utf8")) as StudyIndex;
const shard = (i: number) =>
  JSON.parse(
    readFileSync(path.join(DIR, "presence", `${String(i).padStart(2, "0")}.json`), "utf8"),
  ) as PresenceShard;

test("TS shardOf agrees with the Python builder for every committed accession", () => {
  for (let i = 0; i < index.n_shards; i++) {
    for (const acc of Object.keys(shard(i))) {
      assert.equal(shardOf(acc, index.n_shards), i, `${acc} is in shard ${i}`);
    }
  }
});

test("isoform suffixes are stripped before the join", () => {
  assert.equal(baseAccession("p16070-3"), "P16070");
  assert.equal(baseAccession(" P02786 "), "P02786");
});

test("only admitted intact-cell arms count as surface detections", () => {
  for (const arm of index.arms) {
    if (isCounted(arm)) {
      assert.equal(arm.admitted, true, arm.id);
      assert.equal(arm.method_class, "intact_cell", arm.id);
    }
    if (arm.method_class === "fractionation") assert.equal(isCounted(arm), false, arm.id);
    if (arm.status === "held") assert.equal(isCounted(arm), false, arm.id);
  }
  assert.equal(index.arms.filter(isCounted).length, index.n_admitted_arms);
});

test("presence entries point at real arms", () => {
  for (let i = 0; i < index.n_shards; i++) {
    for (const e of Object.values(shard(i))) {
      for (const a of e.a) assert.ok(a >= 0 && a < index.arms.length);
    }
  }
});
