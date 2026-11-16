/*
 *   npx --yes tsx --test tests/catalog_preset_param.test.ts
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { parsePresetParam, presetParamValue } from "../lib/catalog-presets";

test("?preset= reads known tier presets, ignoring case, blanks, unknowns and all", () => {
  assert.deepEqual([...parsePresetParam("canonical,likely")], ["canonical", "likely"]);
  assert.deepEqual([...parsePresetParam(" Likely ,CANONICAL,,bogus,all")], ["likely", "canonical"]);
  assert.equal(parsePresetParam(null).size, 0);
});

test("the URL value lists the selection in chip order, or nothing", () => {
  assert.equal(presetParamValue(new Set(["likely", "canonical"])), "canonical,likely");
  assert.equal(presetParamValue(new Set()), null);
  assert.equal(presetParamValue(parsePresetParam("likely,canonical")), "canonical,likely");
});
