/*
 * Render tests for the EvidenceDrawer's citation list.
 *
 * The drawer used to show only a bare accession ("PMC6199259") next to the
 * verbatim quote, because the stored record carries nothing else — the
 * agent writes `SourceRef.title` as a placeholder equal to the id. Real
 * citation metadata is joined in at serve time from `paper_metadata` and
 * arrives as the evidence endpoint's `papers` map. These tests pin both
 * halves of that contract: the enriched rendering, and the fallback for
 * every path where the metadata isn't there (paper missing from the table,
 * offline snapshot, pre-join Worker).
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/evidence_drawer_sources.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  SourceList,
  EvidenceCard,
  type SourceEntry,
} from "../components/surfaceome/EvidenceDrawer/EvidenceDrawer";
import type { Evidence, PaperMetadata } from "../lib/surfaceome-types";

test("DOI-only internalization citations show bibliography and never link to PMC/None", () => {
  const sid = "DOI:10.1101/2025.06.08.658482";
  const ev = {
    evidence_id: "int_evi_01", claim: "Measured uptake", spans: [{
      quote: "An uptake assay.", source: {
        source_id: sid, pmc_id: null,
        url: "https://www.ncbi.nlm.nih.gov/pmc/articles/None/",
      },
    }],
  } as unknown as Evidence;
  const html = renderToStaticMarkup(<EvidenceCard ev={ev} onClose={() => {}} papers={{
    [sid]: meta({ source_id: sid, pmc_id: null,
      title: "EndoNB: A general strategy to study the internalization of cell surface proteins",
      authors_short: "Lenaerts et al.", journal: "bioRxiv (preprint)", year: 2025,
    }),
  }} />);
  assert.match(html, /https:\/\/doi.org\/10.1101\/2025.06.08.658482/);
  assert.doesNotMatch(html, /articles\/None/);
  assert.match(html, /EndoNB/);
  assert.match(html, /Lenaerts et al./);
  assert.match(html, /bioRxiv \(preprint\) 2025/);
});

const PMC_HREF = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6199259/";

function meta(overrides: Partial<PaperMetadata> = {}): PaperMetadata {
  return {
    source_id: "PMC:PMC6199259",
    pmid: "30353140",
    pmc_id: "PMC6199259",
    doi: "10.1038/s41598-018-33841-w",
    title: "Structural and functional insights into the transporter TAPL",
    authors_short: "Bock et al.",
    authors: ["Bock C", "Löhr F", "Tumulka F"],
    n_authors: 11,
    journal: "Sci Rep",
    year: 2018,
    ...overrides,
  };
}

function render(sources: SourceEntry[]): string {
  return renderToStaticMarkup(React.createElement(SourceList, { sources }));
}

test("renders title, byline and accession when metadata is present", () => {
  const html = render([
    { href: PMC_HREF, label: "PMC6199259", meta: meta() },
  ]);
  assert.match(
    html,
    /Structural and functional insights into the transporter TAPL/,
    "paper title must be rendered",
  );
  assert.match(html, /Bock et al\./, "byline must carry the short author form");
  assert.match(html, /Sci Rep 2018/, "byline must carry journal + year");
  assert.match(html, /PMC6199259/, "accession must survive as a marker");
  assert.match(
    html,
    new RegExp(`href="${PMC_HREF.replace(/[/.]/g, "\\$&")}"`),
    "the title must link to the paper",
  );
});

test("the whole citation is one link, with no dead text beside the arrow", () => {
  // Regression: the title was the only anchor, so the byline and the
  // accession were dead text — while the accession carried the ↗, making
  // the least clickable part look the most clickable.
  const html = render([
    { href: PMC_HREF, label: "PMC6199259", meta: meta() },
  ]);
  const anchor = /<a[^>]*href="[^"]*PMC6199259[^"]*"[^>]*>([\s\S]*?)<\/a>/.exec(html);
  assert.ok(anchor, "citation must be wrapped in an anchor to the paper");
  const inner = anchor[1];
  assert.match(inner, /Structural and functional insights/, "title inside the link");
  assert.match(inner, /Bock et al\./, "byline inside the link");
  assert.match(inner, /PMC6199259/, "accession inside the link");
  assert.match(inner, /↗/, "the arrow belongs to the same link");
});

test("falls back to the bare accession link when metadata is absent", () => {
  const html = render([{ href: PMC_HREF, label: "PMC6199259" }]);
  assert.match(html, /PMC6199259 ↗/, "accession stays the link text");
  assert.doesNotMatch(html, /undefined/, "no undefined leaks into the markup");
});

test("falls back when the metadata row exists but has no title", () => {
  // A `paper_metadata` row can exist with a null title (NCBI returned a
  // docsum with no title field). Rendering the byline alone under a blank
  // heading would read as a broken citation, so the whole enriched branch
  // is gated on the title.
  const html = render([
    { href: PMC_HREF, label: "PMC6199259", meta: meta({ title: null }) },
  ]);
  assert.match(html, /PMC6199259 ↗/, "must fall back to the accession link");
  assert.doesNotMatch(html, /Bock et al\./, "byline must not render alone");
});

test("omits the byline when NCBI had no authors, journal or year", () => {
  const html = render([
    {
      href: PMC_HREF,
      label: "PMC6199259",
      meta: meta({ authors_short: null, journal: null, year: null }),
    },
  ]);
  assert.match(html, /transporter TAPL/, "title still renders");
  assert.match(html, /PMC6199259/, "accession still renders");
  assert.doesNotMatch(html, / · <span/, "no dangling separator before the id");
});

test("renders each of several sources once", () => {
  const html = render([
    { href: PMC_HREF, label: "PMC6199259", meta: meta() },
    {
      href: "https://pubmed.ncbi.nlm.nih.gov/40482031/",
      label: "PMID 40482031",
      meta: meta({
        source_id: "PMID:40482031",
        title: "Three cryo-EM structures of a protease inhibitor",
        authors_short: "Almeida & Jensen",
        journal: "Cell Rep",
        year: 2025,
      }),
    },
  ]);
  assert.match(html, /Sci Rep 2018/);
  assert.match(html, /Almeida &amp; Jensen · Cell Rep 2025/);
  assert.equal(
    html.match(/<li>/g)?.length,
    2,
    "one list item per deduped source",
  );
});
