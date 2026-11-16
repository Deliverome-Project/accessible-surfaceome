/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/methods_panel.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { linkIds, MethodsBody } from "../components/StudiesExplorer/MethodsPanel";
import { repositoryUrl, type ArmMethods, type StudyArm } from "../lib/surface-proteomics";

const arm: StudyArm = {
  id: "x-2020",
  name: "Example surface capture",
  publication: "1",
  first_author: "Doe J",
  year: 2020,
  journal: null,
  title: null,
  pmid: "123",
  doi: "10.1/x",
  family: "biotin-amine",
  family_label: "Amine biotinylation",
  method_class: "intact_cell",
  intact_cell_labeling: "yes",
  intact_cell_verified: true,
  sample: "HeLa",
  status: "held",
  status_reason: "values are imputed, so detection can't be read per protein",
  admitted: false,
  n_proteins: 900,
  reference_overlap: 0.31,
  repository: "PRIDE",
  repository_ids: ["PXD000001"],
};

const m: ArmMethods = {
  method: "Sulfo-NHS-SS-biotin on intact cells",
  instrument: "Orbitrap Exploris 480",
  method_source: "Method as described in the paper's Methods (Nat Commun 2020; full text PMC1234567).",
  instrument_source: "Instrument as listed in the ProteomeXchange record PXD000001.",
  rationale: "Imputed matrix.",
  n_total_ids: 1000,
  n_in_reference: 310,
  overlap_cutoff: 0.2,
  source_files: [
    { file: "proteinGroups.txt", url: "https://ftp.pride.ebi.ac.uk/x.zip", archive: "x.zip", sha256: "ab".repeat(32) },
    { file: "Table S1.xlsx", sheet: "All" },
    { file: "control_surface_proteins.tsv", derived_from: [{ file: "media-4.xlsx", url: "https://example.org/media-4.xlsx", sheet: "Surface" }], derivation: "accession and gene columns copied" },
  ],
  extractions: [
    {
      file: "proteinGroups.txt",
      accession_column: "Majority protein IDs",
      filters: ["drop rows flagged Reverse"],
      sample_groups: [{ cell_type: "HeLa", condition: "surface", columns: ["LFQ 1", "LFQ 2"], min_observed: 2 }],
    },
  ],
  target_species: "Homo sapiens",
  n_species_excluded: 0,
  n_species_unresolved: 3,
};

test("every file states where it came from, what was read, and its checksum", () => {
  const html = renderToStaticMarkup(<MethodsBody arm={arm} m={m} />);
  assert.match(html, /Inside x\.zip, downloaded from <a[^>]*href="https:\/\/ftp\.pride\.ebi\.ac\.uk\/x\.zip"/);
  assert.match(html, /Where this file came from is not yet recorded\./);
  assert.match(html, /Derived by us from <span><a[^>]*href="https:\/\/example\.org\/media-4\.xlsx"[^>]*>media-4\.xlsx<\/a> \(sheet “Surface”\)<\/span>: accession and gene columns copied\./);
  assert.match(html, /Read the table, columns <span[^>]*>Majority protein IDs \(accession\)<\/span>, plus 2 sample columns/);
  assert.match(html, /Read sheet “All”/);
  assert.match(html, /SHA-256 of the exact copy we read/);
  assert.doesNotMatch(html, /Files without a link/);
  assert.match(html, /href="https:\/\/doi\.org\/10\.1\/x"/);
  assert.match(html, /GetDataset\?ID=PXD000001/);
  assert.match(html, /Orbitrap Exploris 480/);
  assert.match(html, /Imputed matrix\./);
  assert.match(html, /310 of 1,000 reported IDs/);
  assert.match(html, /drop rows flagged Reverse/);
  assert.match(html, /LFQ 1, LFQ 2/);
  assert.match(html, /3 whose species could not be resolved/);
});

test("source sentences link their identifiers", () => {
  const html = renderToStaticMarkup(<MethodsBody arm={arm} m={m} />);
  assert.match(html, /<a[^>]*href="https:\/\/pmc\.ncbi\.nlm\.nih\.gov\/articles\/PMC1234567\/"[^>]*>PMC1234567<\/a>/);
  assert.match(html, /ProteomeXchange record <a[^>]*GetDataset\?ID=PXD000001"[^>]*>PXD000001<\/a>\./);
  const doi = renderToStaticMarkup(<>{linkIds("Method as described in the preprint's Methods (bioRxiv 10.64898/2026.09.16.752145v1).")}</>);
  assert.match(doi, /href="https:\/\/doi\.org\/10\.64898\/2026\.09\.16\.752145"[^>]*>10\.64898\/2026\.09\.16\.752145v1<\/a>\)\./);
});

test("the accession-resolution steps link the catalog code by commit", () => {
  const html = renderToStaticMarkup(<MethodsBody arm={arm} m={m} />);
  assert.match(html, /How accessions were resolved/);
  assert.match(html, /blob\/[0-9a-f]{40}\/src\/accessible_surfaceome\/merge\/normalize\.py#L\d+/);
  assert.match(html, /blob\/[0-9a-f]{40}\/src\/accessible_surfaceome\/tools\/gene_lookup\.py#L\d+/);
  assert.match(html, /blob\/[0-9a-f]{40}\/src\/accessible_surfaceome\/merge\/__init__\.py#L\d+/);
  assert.match(html, /split into several human successors is not counted/);
  assert.doesNotMatch(html, /each of its\s+successors/);
});

test("repositoryUrl knows the major proteomics repositories only", () => {
  assert.equal(repositoryUrl("MSV000102332"), "https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=MSV000102332");
  assert.equal(repositoryUrl("JPST003825"), "https://repository.jpostdb.org/entry/JPST003825");
  assert.equal(repositoryUrl("none"), null);
});
