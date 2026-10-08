/*
 * Visual harness for the citation rendering — NOT a test.
 *
 * Renders the real EvidenceDrawer SourceList and the real
 * EvidenceLedgerCard row against the real stylesheets, so the typography
 * can be eyeballed without standing up the gene page (which needs the
 * Cloudflare Pages rewrite that maps /{SYMBOL}/ onto the /gene shell, and
 * so 404s under `next dev`).
 *
 * The CSS-module stub loader returns each key verbatim (styles.sourceCite
 * -> "sourceCite"), so pairing the rendered markup with the raw .module.css
 * text makes every selector match exactly what ships.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       tests/helpers/citation-preview.tsx > /tmp/preview.html
 */
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { SourceList } from "../../components/surfaceome/EvidenceDrawer/EvidenceDrawer";
import { EvidenceLedgerCard } from "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard";
import type { PaperMetadata, SurfaceomeRecord } from "../../lib/surfaceome-types";
import { baseRecord } from "./fixtures";

const SOURCE_ID = "PMC:PMC6199259";
const HREF = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/";

const META: PaperMetadata = {
  source_id: SOURCE_ID,
  pmid: "30353140",
  pmc_id: "PMC6199259",
  doi: "10.1038/s41598-018-33841-w",
  title:
    "Structural and functional insights into the interaction and targeting hub TMD0 of the polypeptide transporter TAPL",
  authors_short: "Bock et al.",
  authors: ["Bock C", "Löhr F"],
  n_authors: 11,
  journal: "Sci Rep",
  year: 2018,
};

const META2: PaperMetadata = {
  ...META,
  source_id: "PMID:40482031",
  pmc_id: null,
  pmid: "40482031",
  title: "Three cryo-EM structures of CD109 reveal its mechanism of protease inhibition",
  authors_short: "Almeida & Jensen",
  journal: "Cell Rep",
  year: 2025,
};

function ledgerRecord(): SurfaceomeRecord {
  const rec = baseRecord();
  (rec as unknown as { evidence: unknown }).evidence = [
    {
      evidence_id: "evi_1",
      claim: "Detected at the cell surface of non-permeabilized cells by flow cytometry.",
      claim_type: "surface_localization",
      evidence_tier: "primary",
      confidence: 0.9,
      entailment_verified: true,
      spans: [
        {
          quote:
            "surface staining was readily detected in non-permeabilized cells, indicating a plasma-membrane pool",
          source: { source_id: SOURCE_ID, pmc_id: "PMC6199259", url: HREF },
        },
      ],
    },
  ];
  return rec;
}

const drawerCss = readFileSync(
  new URL(
    "../../components/surfaceome/EvidenceDrawer/EvidenceDrawer.module.css",
    import.meta.url,
  ),
  "utf8",
);
const ledgerCss = readFileSync(
  new URL(
    "../../components/surfaceome/EvidenceLedgerCard/EvidenceLedgerCard.module.css",
    import.meta.url,
  ),
  "utf8",
);
const tokens = readFileSync(
  new URL("../../app/design-tokens.css", import.meta.url),
  "utf8",
);

const drawerHtml = renderToStaticMarkup(
  React.createElement(SourceList, {
    sources: [
      { href: HREF, label: "PMC6199259", meta: META },
      { href: "https://pubmed.ncbi.nlm.nih.gov/40482031/", label: "PMID 40482031", meta: META2 },
    ],
  }),
);

const ledgerHtml = renderToStaticMarkup(
  React.createElement(EvidenceLedgerCard, {
    rec: ledgerRecord(),
    n: 1,
    papers: { [SOURCE_ID]: META },
  }),
);

process.stdout.write(`<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,400..700;1,400..700&display=swap" rel="stylesheet">
<style>
${tokens}
:root { --font-sans: "Manrope", system-ui, sans-serif; --font-display: "Playfair Display", Georgia, serif; }
body { font-family: var(--font-sans); background: var(--bg, #fff); color: var(--ink, #1a1a1a);
       margin: 0; padding: 32px; max-width: 760px; }
h2.hdr { font-family: var(--font-sans); font-size: 0.72rem; letter-spacing: 0.22em;
         text-transform: uppercase; color: var(--muted); margin: 32px 0 8px; font-weight: 400; }
.panel { border: 1px solid var(--line, #e5e0dd); border-radius: 8px; padding: 20px; }
.subhead { margin: 0 0 6px; font-size: 0.78rem; letter-spacing: 0.08em;
           text-transform: uppercase; color: var(--muted); }
${drawerCss}
${ledgerCss}
</style></head><body>
<h2 class="hdr">Evidence drawer — Source list</h2>
<div class="panel"><h3 class="subhead">Sources</h3>${drawerHtml}</div>
<h2 class="hdr">Evidence ledger — row</h2>
<div class="panel">${ledgerHtml}</div>
</body></html>
`);
