/*
 * Server-render test for the <TaggedSitesCard> "Screen-validated" section —
 * the third provenance lane (Tedman-style parallel surface-display screen
 * controls), distinct from Literature-validated / Computed candidates. Mirrors
 * the setup in tests/tagged_sites_card.test.tsx (node:test +
 * react-dom/server.renderToStaticMarkup — this repo has no vitest /
 * @testing-library/react installed, so this matches the working harness
 * rather than the vitest+RTL sketch).
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/tagged_sites_card_screen.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TaggedSitesCard } from "../components/surfaceome/TaggedSitesCard/TaggedSitesCard";
import type { TaggedSitesFile } from "../lib/tag-sites-types";

const file: TaggedSitesFile = {
  has_data: true,
  gene_symbol: "ADRB2",
  uniprot_acc: "P07550",
  sites: [
    {
      site_id: "ADRB2-nterm-tedman",
      gene_symbol: "ADRB2",
      uniprot_acc: "P07550",
      provenance: "screen_validated",
      det_path: null,
      site_kind: "terminal_n",
      insert_after_residue: null,
      residue_before: null,
      residue_after: "M",
      topology_state: "S",
      extracellular: true,
      compartment: "extracellular",
      tag_type: "HA",
      tag_length_aa: 9,
      linker: null,
      evidence_type: "N-terminal HA epitope; parallel surface-display screen",
      functional_impact_measured:
        "Surface immunostaining PME 1234 ± 67 (HA immunostaining, Tedman deep receptor scanning)",
      confidence: "high",
      rationale: null,
      sources: [{ citation: "Tedman et al. 2026", doi: "10.1038/s41467-026-76564-7" }],
      plddt: null,
      conservation_rank: null,
      median_conservation: null,
    },
  ],
};

test("TaggedSitesCard shows a Screen-validated section with the PME", () => {
  const html = renderToStaticMarkup(<TaggedSitesCard taggedSites={file} />);
  assert.match(html, /Screen-validated \(1\)/);
  assert.match(html, /PME 1234/);
});
