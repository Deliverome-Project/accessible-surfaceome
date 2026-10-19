/*
 * Server-render test for the <CatalogTable> "In FG library" facet chip.
 * Pins the structural integration of the top-level `in_fg_library` filter:
 *  - the "In FG library" facet chip renders in the presetBar,
 *  - its count reflects the number of in-library rows,
 *  - the component renders with library-bearing rows without throwing.
 *
 * (Row bodies are virtualized + gated on a post-mount effect, so static markup
 * doesn't emit data rows — hence we assert on the always-rendered presetBar
 * chip chrome, the same surface the other catalog render tests protect.)
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/catalog_table_fg_library.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CatalogTable } from "../components/CatalogTable/CatalogTable";
import type { CatalogRow } from "../lib/surfaceome";

function row(overrides: Partial<CatalogRow>): CatalogRow {
  return {
    symbol: "GENE",
    uniprot: "P00000",
    n_sources: 3,
    db: { uniprot: 1, go: 1, surfy: 1, cspa: 0, hpa: 0 },
    triage_by_model: [null, { verdict: "yes", reason: "cell surface" }, null],
    deep_dive: false,
    in_fg_library: false,
    ...overrides,
  };
}

const rows: CatalogRow[] = [
  row({ symbol: "ABCB1", uniprot: "P08183", in_fg_library: true }),
  row({ symbol: "ABCC1", uniprot: "P33527", in_fg_library: true }),
  row({ symbol: "NOTINLIB", uniprot: "P99999", in_fg_library: false }),
];

function render(): string {
  return renderToStaticMarkup(
    React.createElement(CatalogTable, {
      rows,
      n_rows: rows.length,
      n_with_triage: rows.length,
      n_with_deep_dive: 0,
      universe_version: "test",
    }),
  );
}

test("renders the 'In FG library' facet chip in the presetBar", () => {
  const html = render();
  assert.ok(
    html.includes("In FG library"),
    "the In FG library facet chip must render in the catalog presetBar",
  );
});

test("the facet chip count reflects the number of in-library rows", () => {
  const html = render();
  // Two of the three fixture rows are in the library.
  assert.match(
    html,
    /In FG library[\s\S]*?>2</,
    "the facet chip must show a count of 2 for the two in-library rows",
  );
});

test("renders with in_fg_library-bearing rows without throwing", () => {
  assert.doesNotThrow(render, "CatalogTable must render with the FG facet + rows");
});
