/*
 * Regression test for the `TypeError: e.evidence is not iterable` crash
 * that hit the dev viewer once the production API (#171) split the
 * citation ledger off `GET /v1/genes/{sym}` onto its own
 * `GET /v1/genes/{sym}/evidence` endpoint. `app/gene/page.tsx` (#170,
 * cherry-picked here) now leaves `rec.evidence` as `undefined` — not
 * `[]` — while that lazy fetch is in flight, and `<EvidenceLedgerCard>`
 * must treat `undefined` as "still loading" rather than iterating over
 * it. Mirrors the setup in tests/tagged_sites_card_screen.test.tsx
 * (node:test + react-dom/server.renderToStaticMarkup — this repo has no
 * vitest / @testing-library/react installed).
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/gene_page_evidence_split.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { EvidenceLedgerCard } from "../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

test("EvidenceLedgerCard with evidence=undefined (lazy fetch in flight) does not throw", () => {
  const rec = baseRecord();
  // baseRecord() never sets `evidence`, so this already models the
  // post-split Worker's initial paint — but assert the precondition
  // explicitly so a future fixture change can't silently invalidate it.
  assert.equal(
    (rec as SurfaceomeRecord).evidence,
    undefined,
    "fixture must model the lazy-load-in-flight state (evidence undefined, not [])",
  );

  let html = "";
  assert.doesNotThrow(() => {
    html = renderToStaticMarkup(
      React.createElement(EvidenceLedgerCard, { rec, n: 1 }),
    );
  }, /e\.evidence is not iterable|is not iterable/);

  // Renders the loading skeleton, not the premature empty state — and
  // never falls through to trying to iterate `undefined` as an array.
  assert.match(html, /Loading evidence/);
  assert.doesNotMatch(html, /No evidence entries recorded/);
});

test("EvidenceLedgerCard with evidence=[] (settled, no entries) renders the empty state", () => {
  const rec = baseRecord();
  (rec as unknown as { evidence: unknown }).evidence = [];

  let html = "";
  assert.doesNotThrow(() => {
    html = renderToStaticMarkup(
      React.createElement(EvidenceLedgerCard, { rec, n: 1 }),
    );
  });
  assert.match(html, /No evidence entries recorded/);
});
