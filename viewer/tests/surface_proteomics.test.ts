import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import {
  baseAccession,
  countedRank,
  shareBelow,
  isCounted,
  letter,
  studyHref,
  TIER_HELP,
  TIER_LABEL,
  TIER_ORDER,
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

test("comparison letters and deep links", () => {
  assert.deepEqual([0, 1, 25, 26, 27].map(letter), ["A", "B", "Z", "AA", "AB"]);
  assert.equal(studyHref([]), "/surface-proteomics/");
  assert.equal(studyHref(["a-1", "b 2"]), "/surface-proteomics/?arm=a-1,b%202");
});

test("every tier has a label and a definition", () => {
  for (const t of TIER_ORDER) {
    assert.ok(TIER_LABEL[t], t);
    assert.ok(TIER_HELP[t], t);
  }
});

test("counted-detection rank", () => {
  // 4 proteins in 1 dataset, 3 in 2, 2 in 3, 1 in 4.
  const hist = [0, 4, 3, 2, 1];
  assert.equal(countedRank(hist, 0), null);
  assert.deepEqual(countedRank(hist, 1), { below: 0, total: 10, median: 2 });
  assert.deepEqual(countedRank(hist, 4), { below: 0.9, total: 10, median: 2 });
  const real = countedRank(index.counted_detection_hist, 1);
  assert.equal(real?.total, index.n_accessions_admitted);
});

test("cohort share below, zero detections included", () => {
  const hist = [5, 3, 2]; // 5 proteins in no counted dataset, 3 in one, 2 in two
  assert.deepEqual(shareBelow(hist, 0), { below: 0, total: 10 });
  assert.deepEqual(shareBelow(hist, 2), { below: 0.8, total: 10 });
  const all = index.cohort_detection_hist?.all;
  assert.ok(all && all.reduce((a, b) => a + b, 0) > 5000);
});
