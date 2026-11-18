import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import {
  baseAccession,
  countedRank,
  surfacePreference,
  formatQuant,
  ordinalPct,
  shareBelow,
  ABUNDANCE_SCREEN,
  countableOtherConditions,
  countingRule,
  isCounted,
  letter,
  studyHref,
  TIER_HELP,
  TIER_LABEL,
  TIER_ORDER,
  loadShard,
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

test("every dataset has a cell-type group; per-line atlases list their lines", () => {
  for (const arm of index.arms) assert.ok(arm.cell_group, arm.id);
  for (let i = 0; i < index.n_shards; i++) {
    for (const e of Object.values(shard(i))) {
      for (const [armIdx, lines] of Object.entries(e.l ?? {})) {
        const arm = index.arms[Number(armIdx)];
        assert.ok(arm.lines && lines.every((j) => j >= 0 && j < arm.lines!.length), arm.id);
      }
    }
  }
});

test("quantity formatting", () => {
  assert.equal(ordinalPct(1), "1st percentile");
  assert.equal(ordinalPct(12), "12th percentile");
  assert.equal(ordinalPct(92), "92nd percentile");
  assert.equal(ordinalPct(100), "100th percentile");
  assert.equal(formatQuant(11864.4), "11,864");
  assert.equal(formatQuant(23.44), "23.4");
  assert.equal(formatQuant(2.5e9), "2.50e9");
});

test("surface preference: differences, mean and verdict", () => {
  assert.deepEqual(surfacePreference(undefined), { vsProcan: null, vsMembrane: null, mean: null, verdict: null });
  const npc1 = surfacePreference([57, 74, 65]);
  assert.equal(npc1.vsProcan, -8);
  assert.equal(npc1.vsMembrane, -17);
  assert.equal(npc1.verdict, "carryover");
  assert.equal(surfacePreference([97, 78, 85]).verdict, "enriched");
  assert.equal(surfacePreference([99, 97, 98]).verdict, "unclear");
  assert.equal(surfacePreference([80, null, 60]).mean, 20);
});

test("other conditions are not counted unless the reader opts in, and then only under a counted baseline", () => {
  const arms = index.arms;
  const other = arms.filter((a) => a.status === "perturbed");
  assert.ok(other.length > 0, "the committed snapshot carries other-condition arms");
  const byId = new Map(arms.map((a) => [a.id, a]));

  // Default rule: identical to isCounted, so no other condition counts.
  const base = countingRule(arms, false);
  for (const a of arms) assert.equal(base(a), isCounted(a), a.id);
  assert.ok(other.every((a) => !base(a)));

  // Opt-in: every baseline arm still counts the same way, and an other
  // condition counts exactly when its parent baseline arm is counted.
  const opted = countingRule(arms, true);
  for (const a of arms) {
    if (a.status !== "perturbed") {
      assert.equal(opted(a), isCounted(a), a.id);
      continue;
    }
    const parent = a.parent ? byId.get(a.parent) : undefined;
    assert.ok(parent, `${a.id} names a parent that exists`);
    assert.equal(opted(a), isCounted(parent), a.id);
  }
  const countable = countableOtherConditions(arms);
  assert.ok(countable.length > 0 && countable.length < other.length);
});

test("datasets with published amounts are screened on their amount, at the viewer's bar", () => {
  const byAmount = index.arms.filter((a) => a.screen_basis === "abundance");
  assert.ok(byAmount.length > 0, "the snapshot carries abundance-screened arms");
  for (const a of byAmount) {
    assert.equal(a.abundance_cutoff, ABUNDANCE_SCREEN, `${a.id}: cutoff matches ABUNDANCE_SCREEN`);
    assert.ok(a.abundance_share != null, `${a.id}: has a share`);
    const passes = a.abundance_share! + 1e-9 >= ABUNDANCE_SCREEN;
    assert.equal(isCounted(a), passes, `${a.id}: counted exactly when its amount share passes`);
  }
});

test("a presence shard survives a transient failure but not a real 404", async () => {
  const realFetch = globalThis.fetch;
  const calls: string[] = [];
  const reply = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  try {
    // Two hiccups then success: the shard still loads, so one dropped request out of the
    // 32 the explorer asks for cannot strand the whole view.
    let n = 0;
    globalThis.fetch = (async (url: string) => {
      calls.push(String(url));
      n += 1;
      if (n === 1) throw new TypeError("network error");
      if (n === 2) return reply({}, 503);
      return reply({ P12345: { s: "SHARD_OK", a: [] } });
    }) as typeof fetch;
    const ok = (await loadShard(900)) as PresenceShard;
    assert.equal(ok.P12345?.s, "SHARD_OK");
    assert.equal(n, 3, "retried twice before succeeding");

    // A 404 is the server's answer, not a hiccup: it fails on the first try rather than
    // spending two more round trips and the backoff on a file that is not there.
    calls.length = 0;
    globalThis.fetch = (async (url: string) => {
      calls.push(String(url));
      return reply({}, 404);
    }) as typeof fetch;
    await assert.rejects(() => loadShard(901), /HTTP 404/);
    assert.equal(calls.length, 1, "a 404 is not retried");
  } finally {
    globalThis.fetch = realFetch;
  }
});
