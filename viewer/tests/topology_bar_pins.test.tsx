// viewer/tests/topology_bar_pins.test.tsx
/*
 * Render test: TopologyBar draws one pin per provided pin, positioned by
 * leftPct and classed by provenance. Runs via run_render_tests.sh.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TopologyBar } from "../components/surfaceome/IsoformsCard/TopologyBar";

test("renders a pin per pin with provenance class + left%", () => {
  const html = renderToStaticMarkup(
    <TopologyBar
      topology={"O".repeat(100)}
      pins={[
        { siteId: "a", leftPct: 25, provenance: "literature_retrieved", tagType: "ALFA" },
        { siteId: "b", leftPct: 75, provenance: "deterministic_computed", tagType: "ALFA" },
      ]}
    />,
  );
  assert.equal((html.match(/data-provenance=/g) ?? []).length, 2);
  assert.match(html, /data-provenance="literature_retrieved"/);
  assert.match(html, /data-provenance="deterministic_computed"/);
  assert.match(html, /left:\s*25%/);
});

test("isoform pins color by shared/unique classification", () => {
  const html = renderToStaticMarkup(
    <TopologyBar
      topology={"O".repeat(100)}
      pins={[
        { siteId: "s", leftPct: 40, provenance: "deterministic_computed", tagType: "ALFA", classification: "shared" },
        { siteId: "u", leftPct: 60, provenance: "deterministic_computed", tagType: "ALFA", classification: "unique" },
      ]}
    />,
  );
  assert.match(html, /data-classification="shared"/);
  assert.match(html, /data-classification="unique"/);
  assert.match(html, /--tag-site-isoform-shared/);
  assert.match(html, /--tag-site-isoform-unique/);
});

test("no pins prop -> no pin markup (unchanged bar)", () => {
  const html = renderToStaticMarkup(<TopologyBar topology={"O".repeat(10)} />);
  assert.equal((html.match(/data-provenance=/g) ?? []).length, 0);
});
