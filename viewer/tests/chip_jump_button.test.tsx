/*
 * Server-render tests for <ChipJumpButton>. Interaction (scroll, focus,
 * hashchange) requires jsdom and is verified by manual QA per the plan;
 * these tests pin the rendered markup — <span role="button" tabindex="0">,
 * aria attrs, and the wrapped chip content — because those are the pieces
 * a screen reader and keyboard user rely on. We use a span (not a real
 * <button>) so the wrapped StatusPill can host an InfoTip-style popover
 * with rich content (<p>, <ul>) without invalid button-content-model or
 * nested-button DOM recovery.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/chip_jump_button.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChipJumpButton } from "../components/surfaceome/_shared/ChipJumpButton/ChipJumpButton";

test('renders as <span role="button" tabindex="0"> wrapping its children', () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-biology-ligand", tabId: "biology", ariaLabel: "Jump to rationale: Known ligand" },
      React.createElement("span", null, "chip-content"),
    ),
  );
  assert.match(html, /<span[^>]*role="button"/);
  assert.match(html, /<span[^>]*tabIndex="0"|tabindex="0"/);
  assert.ok(html.includes("chip-content"), "children must render inside the trigger span");
});

test("carries aria-label", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-primary-compartment", tabId: "biology", ariaLabel: "Jump to Primary compartment" },
      "x",
    ),
  );
  assert.ok(
    html.includes('aria-label="Jump to Primary compartment"'),
    "aria-label must be surfaced in markup",
  );
});

test("target and tab metadata are surfaced as data-* attrs (for e2e)", () => {
  const html = renderToStaticMarkup(
    React.createElement(
      ChipJumpButton,
      { targetId: "chip-jump-contradicting-evidence", tabId: "evidence", ariaLabel: "Jump to Contradicting evidence" },
      "x",
    ),
  );
  assert.ok(html.includes('data-chip-jump-target="chip-jump-contradicting-evidence"'));
  assert.ok(html.includes('data-chip-jump-tab="evidence"'));
});
