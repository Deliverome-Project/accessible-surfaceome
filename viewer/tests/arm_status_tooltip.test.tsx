/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/arm_status_tooltip.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { tooltips } from "../lib/tooltips";
import { STATUS_DEFINITION, STATUS_LABEL, type ArmStatus } from "../lib/surface-proteomics";

const ALL: ArmStatus[] = ["core", "provisional", "held", "below_screen", "comparator"];

test("the Status explainer defines every status the data uses, one line each", () => {
  const html = renderToStaticMarkup(<>{tooltips.arm_status}</>);
  for (const s of ALL) {
    assert.ok(html.includes(STATUS_LABEL[s]), s);
    const def = STATUS_DEFINITION[s];
    assert.ok(def.length > 0 && !def.includes("\n"), s);
  }
  assert.equal((html.match(/<li>/g) ?? []).length, ALL.length);
  assert.match(html, /below screen/);
});

test("only core and provisional are defined as counted", () => {
  for (const s of ALL) {
    const counted = /^Counted/.test(STATUS_DEFINITION[s]);
    assert.equal(counted, s === "core" || s === "provisional", s);
  }
});
