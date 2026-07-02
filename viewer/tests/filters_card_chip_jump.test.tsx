/*
 * Render tests for the §01 Summary metrics clickable-chip wiring.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/filters_card_chip_jump.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FeatureChips } from "../components/surfaceome/FeatureChips/FeatureChips";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

function renderFeatureChips(category: "biology" | "expression" | "risks", rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(FeatureChips, { category, rec }));
}

test("chip with rationale renders inside a ChipJumpButton", () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "IGF-1 binding characterized (a1_evi_04).";
  const html = renderFeatureChips("biology", rec);
  assert.match(
    html,
    /<button[^>]*data-chip-jump-target="chip-jump-biology-ligand"/,
    "ligand chip must be wrapped in a ChipJumpButton",
  );
  assert.match(
    html,
    /aria-label="Jump to rationale: Known ligand"/,
    "aria-label must describe the destination",
  );
});

test("chip without rationale renders as static pill (no button)", () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = false;
  rec.filters.has_known_ligand_rationale = null;
  const html = renderFeatureChips("biology", rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    "no chip-jump-target wrapper when rationale is null",
  );
});

test('rationale === "None" is treated as null (static pill)', () => {
  const rec = baseRecord();
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "None";
  const html = renderFeatureChips("biology", rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    'nz("None") is null → chip stays static',
  );
});
