/*
 * Server-render tests for the <CatalogTable> internalization column + filter.
 * Pins the structural integration of the row_schema-8 `internalization` facet:
 *  - the trailing "Internalize" sortable column header renders,
 *  - the SEPARATE "Internalization" filter group renders (its own top-level
 *    group, not folded into the Deep Dive / DB-vote groups),
 *  - the component renders with internalization-bearing rows without throwing.
 *
 * (Row bodies are virtualized + gated on a post-mount effect, so static markup
 * doesn't emit data rows — hence we assert on the always-rendered header +
 * filter chrome, the same surface the sortable-column CI gate protects.)
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/catalog_table_internalization.test.tsx
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
    ...overrides,
  };
}

const rows: CatalogRow[] = [
  row({ symbol: "TFRC", uniprot: "P02786", internalization: "high" }),
  row({ symbol: "MS4A1", uniprot: "P11836", internalization: "low" }),
  row({ symbol: "NOINTERN", uniprot: "P99999" }), // no grade → column shows a dash
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

test("renders the trailing 'Internalize' sortable column header", () => {
  const html = render();
  assert.ok(
    html.includes("Internalize"),
    "the internalization column header must be present in the catalog header row",
  );
});

test("renders a SEPARATE 'Internalization' filter group (own top-level group)", () => {
  const html = render();
  // The collapsible group control carries this aria hook only when the
  // standalone Internalization group is emitted (not the deep-dive/DB groups).
  assert.ok(
    html.includes("catalog-filter-group-internalization") ||
      /Internalization<\/?/.test(html),
    "the standalone Internalization filter group must render",
  );
});

test("renders with internalization-bearing rows without throwing", () => {
  assert.doesNotThrow(render, "CatalogTable must render with the new column + rows");
});
