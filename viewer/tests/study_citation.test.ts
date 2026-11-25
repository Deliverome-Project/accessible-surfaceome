/*
 *   npx --yes tsx --test tests/study_citation.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { shortCitation, type StudyArm } from "../lib/surface-proteomics";

const arm = (o: Partial<StudyArm>) => ({ name: "Dataset", year: 2026, first_author: null, ...o }) as StudyArm;

test("studies are named by surname with et al., and/single per the author count", () => {
  assert.equal(shortCitation(arm({ citation: "George et al. 2026", first_author: "George BM" })), "George et al. 2026");
  assert.equal(shortCitation(arm({ citation: "Smith and Jones 2020" })), "Smith and Jones 2020");
});

test("without a built citation: drop the initials, default to et al.", () => {
  assert.equal(shortCitation(arm({ first_author: "George BM" })), "George et al. 2026");
  assert.equal(shortCitation(arm({ first_author: "Cohen Yaron K" })), "Cohen Yaron et al. 2026");
  assert.equal(shortCitation(arm({ first_author: null })), "Dataset");
});
