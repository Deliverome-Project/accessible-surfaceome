/*
 * Server-render tests for the <TaggedSitesCard> — the dedicated §Tag sites
 * section (its own tab, distinct from Internalization). Pins:
 *  - both provenance groups render with their own subhead + count,
 *  - the canonical residue_label + deterministic range/pLDDT show,
 *  - a literature source renders as an external PubMed link,
 *  - validated_literature provenance is NOT rendered (matches the overlay),
 *  - the empty / no-data state renders without throwing.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/tagged_sites_card.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TaggedSitesCard } from "../components/surfaceome/TaggedSitesCard/TaggedSitesCard";
import type { TaggedSite, TaggedSitesFile } from "../lib/tag-sites-types";

function site(overrides: Partial<TaggedSite>): TaggedSite {
  return {
    site_id: "S1",
    gene_symbol: "TFRC",
    uniprot_acc: "P02786",
    provenance: "literature_retrieved",
    det_path: null,
    site_kind: "internal",
    insert_after_residue: 100,
    residue_before: "G",
    residue_after: "K",
    residue_label: "G100",
    residue_range: null,
    topology_state: "extracellular",
    extracellular: true,
    compartment: "extracellular" as TaggedSite["compartment"],
    tag_type: "ALFA",
    tag_length_aa: null,
    linker: null,
    evidence_type: "published tag insertion at this exact site",
    functional_impact_measured: "surface display retained",
    confidence: "high",
    rationale: "r [validation: surface_and_function; entailment_verified: true]",
    sources: [],
    plddt: null,
    conservation_rank: null,
    median_conservation: null,
    ...overrides,
  };
}

function file(sites: TaggedSite[]): TaggedSitesFile {
  return { has_data: true, gene_symbol: "TFRC", uniprot_acc: "P02786", sites };
}

test("renders both provenance groups with counts, residues, and a source link", () => {
  const html = renderToStaticMarkup(
    <TaggedSitesCard
      taggedSites={file([
        site({
          site_id: "lit1",
          residue_label: "F760",
          site_kind: "terminal_c",
          sources: [{ citation: "PMID 24973209", pmid: "24973209" }],
        }),
        site({
          site_id: "det1",
          provenance: "deterministic_computed",
          det_path: "disorder",
          residue_label: "V108",
          residue_range: "C89-R120",
          plddt: 37.5,
          confidence: "medium",
          sources: [],
        }),
        // validation-only provenance must NOT render:
        site({ site_id: "val1", provenance: "validated_literature", residue_label: "Z999" }),
      ])}
      n={7}
    />,
  );
  assert.match(html, /Tag sites/);
  assert.match(html, /Literature-validated \(1\)/);
  assert.match(html, /Computed candidates \(1\)/);
  assert.match(html, /F760/);
  assert.match(html, /V108/);
  assert.match(html, /C89-R120/);
  assert.match(html, /37\.5/);
  // source renders as an external PubMed link
  assert.match(html, /pubmed\.ncbi\.nlm\.nih\.gov\/24973209/);
  // validated_literature site is dropped
  assert.doesNotMatch(html, /Z999/);
});

test("renders an empty state when there are no rendered sites", () => {
  const html = renderToStaticMarkup(
    <TaggedSitesCard taggedSites={{ has_data: false, gene_symbol: "X", uniprot_acc: "Q0", sites: [] }} />,
  );
  assert.match(html, /No tag-site suggestions/);
});
