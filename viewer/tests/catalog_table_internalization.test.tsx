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
    in_fg_library: false,
    ...overrides,
  };
}

const rows: CatalogRow[] = [
  // seq + lit grades can diverge — the reason there are two columns.
  row({
    symbol: "TFRC",
    uniprot: "P02786",
    internalization: "high",
    internalization_lit: "high",
  }),
  row({
    symbol: "MS4A1",
    uniprot: "P11836",
    internalization: "moderate",
    internalization_lit: "no", // observed non-internalizing despite a modest prior
  }),
  row({ symbol: "NOINTERN", uniprot: "P99999" }), // no grades → columns show dashes
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

test("renders ONLY the literature internalization column (not sequence prior)", () => {
  const html = render();
  assert.ok(
    html.includes("Intern · lit"),
    "the internalization LITERATURE column header must render",
  );
  assert.ok(
    !html.includes("Intern · seq"),
    "the internalization SEQUENCE-prior column header must NOT render in the catalog",
  );
});

test("renders internalization literature tooltip & column metadata", () => {
  const html = render();
  assert.ok(
    html.includes("catalog-filter-group-internalization") ||
      /Internalization \(literature\)/.test(html),
    "the Internalization (literature) column/filter metadata must render",
  );
});

test("renders with internalization-bearing rows without throwing", () => {
  assert.doesNotThrow(render, "CatalogTable must render with the new column + rows");
});
