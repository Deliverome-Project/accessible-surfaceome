/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/db_votes_tooltip.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { DatabasePresenceStrip } from "../components/surfaceome/DatabasePresenceCard/DatabasePresenceStrip";
import { tooltips } from "../lib/tooltips";
import type { CatalogRow } from "../lib/surfaceome";

test("the gene header's source-vote strip carries the DB votes explainer", () => {
  const row = { db: { uniprot: 1, go: 1, surfy: 0, cspa: 1, hpa: 0 } } as unknown as CatalogRow;
  const html = renderToStaticMarkup(<DatabasePresenceStrip row={row} />);
  assert.match(html, /Sources · 3\/5/);
  assert.match(html, /About the source database votes/);
});

test("the DB votes explainer names all five databases", () => {
  const text = renderToStaticMarkup(<>{tooltips.db_votes}</>);
  for (const db of ["UniProt", "Gene Ontology", "SURFY", "Cell Surface Protein Atlas", "Human Protein Atlas"]) {
    assert.ok(text.includes(db), db);
  }
  assert.match(text, /from 0 to 5/);
});
