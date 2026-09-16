/*
 * Render tests for the citation line on EvidenceLedgerCard rows.
 *
 * The ledger's at-a-glance rows used to end in a bare accession
 * ("PMC6199259"), so a reader scanning the list couldn't tell one paper
 * from another without opening each drawer. When `paper_metadata`
 * resolves the row's source, the title becomes the link text and the
 * byline + accession trail underneath. Every path where the metadata
 * isn't there — paper missing from the table, ledger still loading, the
 * offline-snapshot path — must keep the previous accession-only row.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/evidence_ledger_citation.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { EvidenceLedgerCard } from "../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import type {
  PaperMetadataMap,
  SurfaceomeRecord,
} from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

const SOURCE_ID = "PMC:PMC6199259";

const PAPERS: PaperMetadataMap = {
  [SOURCE_ID]: {
    source_id: SOURCE_ID,
    pmid: "30353140",
    pmc_id: "PMC6199259",
    doi: "10.1038/s41598-018-33841-w",
    title: "Structural insights into the transporter TAPL",
    authors_short: "Bock et al.",
    authors: ["Bock C", "Löhr F"],
    n_authors: 11,
    journal: "Sci Rep",
    year: 2018,
  },
};

function recordWithEvidence(): SurfaceomeRecord {
  const rec = baseRecord();
  (rec as unknown as { evidence: unknown }).evidence = [
    {
      evidence_id: "evi_1",
      claim: "Detected at the cell surface by flow cytometry.",
      claim_type: "surface_localization",
      evidence_tier: "primary",
      confidence: 0.9,
      entailment_verified: true,
      spans: [
        {
          quote: "surface staining was observed in non-permeabilized cells",
          source: {
            source_id: SOURCE_ID,
            pmc_id: "PMC6199259",
            url: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/",
          },
        },
      ],
    },
  ];
  return rec;
}

function render(papers?: PaperMetadataMap): string {
  return renderToStaticMarkup(
    React.createElement(EvidenceLedgerCard, {
      rec: recordWithEvidence(),
      n: 1,
      papers,
    }),
  );
}

test("row leads with the paper title when metadata resolves", () => {
  const html = render(PAPERS);
  assert.match(
    html,
    /Structural insights into the transporter TAPL/,
    "title must render on the row itself, not only in the drawer",
  );
  assert.match(html, /Bock et al\. · Sci Rep 2018 · PMC6199259/, "byline + accession trail");
});

test("row keeps the bare accession when no metadata is passed", () => {
  // The offline-snapshot path and the pre-fetch window both land here.
  const html = render(undefined);
  assert.match(html, /PMC6199259/, "accession link survives");
  assert.doesNotMatch(html, /Bock et al\./, "no byline without metadata");
});

test("row keeps the bare accession when the paper isn't in the table", () => {
  const html = render({});
  assert.match(html, /PMC6199259/);
  assert.doesNotMatch(html, /undefined/, "no undefined leaks into the markup");
});

test("the evidence chip still opens the drawer alongside the citation", () => {
  // The citation line is additive — the row's chip is the click target
  // for the full claim + quote, and must not be displaced by it.
  const html = render(PAPERS);
  assert.match(html, /data-evidence-id="evi_1"/, "chip keeps its drawer hook");
});
