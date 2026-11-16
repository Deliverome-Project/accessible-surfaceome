/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/arm_status_tooltip.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { tooltips } from "../lib/tooltips";
import {
  ANNOTATION_SELECTED_METHODS,
  STATUS_DEFINITION,
  STATUS_HELP,
  STATUS_LABEL,
  STATUS_ORDER,
} from "../lib/surface-proteomics";

const ALL = STATUS_ORDER;

test("the Status explainer defines every status the data uses, one line each", () => {
  const html = renderToStaticMarkup(<>{tooltips.arm_status}</>);
  for (const s of ALL) {
    const label = s === "annotation_selected" ? "Pre-filtered by surface annotation" : STATUS_LABEL[s];
    assert.ok(html.includes(label), s);
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

test("the pre-filtered status uses the review's wording verbatim", () => {
  assert.equal(STATUS_LABEL.annotation_selected, "Pre-filtered by surface annotation (shown, not counted)");
  assert.equal(STATUS_HELP.annotation_selected, ANNOTATION_SELECTED_METHODS);
  assert.match(ANNOTATION_SELECTED_METHODS, /^Pre-filtered by surface annotation \(shown, not counted\): the published table/);
  assert.ok(ALL.includes("annotation_selected"));
});
