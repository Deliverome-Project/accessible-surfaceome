/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/revision_strip.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { parseRevisions } from "../lib/revisions";
import { RevisionStrip } from "../components/surfaceome/RevisionStrip/RevisionStrip";

const payload = {
  gene_symbol: "EGFR",
  hgnc_id: "HGNC:3236",
  current_revision: 2,
  revisions: [
    { revision: 2, published_at: "2026-09-27T10:00:00Z", source: "sweep",
      changed: ["markdown"],
      releases: [{ version: "1.3.0", zenodo_version_doi: "10.5281/zenodo.999" }],
      url: "https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions/2" },
    { revision: 1, published_at: "2026-08-15T00:00:00Z", source: "sweep",
      changed: ["first_served"],
      releases: [], url: "https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions/1" },
  ],
};

test("parseRevisions rejects junk", () => {
  assert.equal(parseRevisions(null), null);
  assert.equal(parseRevisions({ error: "gene_not_annotated" }), null);
  assert.equal(parseRevisions(payload)?.current.revision, 2);
});

test("strip shows revision, changed label, date, release, citation and history links", () => {
  const html = renderToStaticMarkup(
    React.createElement(RevisionStrip, { revisions: parseRevisions(payload)! }),
  );
  assert.match(html, /Revision 2/);
  assert.match(html, /Markdown refreshed/);
  assert.match(html, /2026-09-27/);
  assert.match(html, /release v1\.3\.0/);
  assert.match(html, /href="https:\/\/api\.deliverome\.org\/surfaceome\/v1\/genes\/EGFR\/revisions\/2"/);
  assert.match(html, /href="https:\/\/doi\.org\/10\.5281\/zenodo\.999"/);
  assert.match(html, /revisions"[^>]*>All revisions/);
});

test("strip omits the release when the revision is in none", () => {
  const p = { ...payload, current_revision: 1, revisions: [payload.revisions[1]] };
  const html = renderToStaticMarkup(React.createElement(RevisionStrip, { revisions: parseRevisions(p)! }));
  assert.doesNotMatch(html, /release v/);
  assert.doesNotMatch(html, /doi\.org/);
});

test("strip labels a first-served revision distinctly", () => {
  const p = { ...payload, current_revision: 1, revisions: [payload.revisions[1]] };
  const html = renderToStaticMarkup(React.createElement(RevisionStrip, { revisions: parseRevisions(p)! }));
  assert.match(html, /Revision 1/);
  assert.match(html, /first served version/);
});

test("strip combines multiple changed parts with ' + '", () => {
  const p = {
    ...payload,
    current_revision: 3,
    revisions: [
      { revision: 3, published_at: "2026-10-01T00:00:00Z", source: "sweep",
        changed: ["record", "evidence"],
        releases: [], url: "https://api.deliverome.org/surfaceome/v1/genes/EGFR/revisions/3" },
      ...payload.revisions,
    ],
  };
  const html = renderToStaticMarkup(React.createElement(RevisionStrip, { revisions: parseRevisions(p)! }));
  assert.match(html, /record updated \+ evidence updated/);
});

test("strip renders no changed segment when `changed` is absent", () => {
  const p = {
    ...payload,
    current_revision: 2,
    revisions: [
      { ...payload.revisions[0], changed: undefined },
      payload.revisions[1],
    ],
  };
  const html = renderToStaticMarkup(React.createElement(RevisionStrip, { revisions: parseRevisions(p)! }));
  assert.match(html, /Revision 2/);
  assert.doesNotMatch(html, /record updated|evidence updated|Markdown refreshed|first served version/);
});
