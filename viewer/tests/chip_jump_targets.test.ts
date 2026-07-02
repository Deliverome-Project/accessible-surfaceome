/*
 * Unit tests for viewer/lib/chipJumpTargets — the central destination-id
 * map wired between §01 summary chips (producers) and their destination
 * rows / blocks on the Biology / Expression / Risks / Evidence tabs.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/chip_jump_targets.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { chipJumpTargets } from "../lib/chipJumpTargets";

test("featureRationale composes category and key", () => {
  assert.equal(
    chipJumpTargets.featureRationale("biology", "ligand"),
    "chip-jump-biology-ligand",
  );
  assert.equal(
    chipJumpTargets.featureRationale("expression", "level"),
    "chip-jump-expression-level",
  );
});

test("primaryCompartment is a constant", () => {
  assert.equal(chipJumpTargets.primaryCompartment, "chip-jump-primary-compartment");
});

test("contradictingEvidence is a constant", () => {
  assert.equal(
    chipJumpTargets.contradictingEvidence,
    "chip-jump-contradicting-evidence",
  );
});

test("modulationCategory composes category value", () => {
  assert.equal(
    chipJumpTargets.modulationCategory("cell_state_induced"),
    "chip-jump-modulation-cell_state_induced",
  );
});

test("ids are valid HTML fragment identifiers (no spaces, no leading digit)", () => {
  const samples = [
    chipJumpTargets.featureRationale("risks", "epitope"),
    chipJumpTargets.primaryCompartment,
    chipJumpTargets.contradictingEvidence,
    chipJumpTargets.modulationCategory("hypoxia_induced"),
  ];
  for (const id of samples) {
    assert.match(id, /^[a-z][a-z0-9_-]*$/, `id "${id}" must be a safe fragment identifier`);
  }
});
