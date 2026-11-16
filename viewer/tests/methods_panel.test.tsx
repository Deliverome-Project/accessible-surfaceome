/*
 *   npx --yes tsx --import ./tests/helpers/register.mjs --test tests/methods_panel.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MethodsBody } from "../components/StudiesExplorer/MethodsPanel";
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
  instrument_source: "PXD000001 record",
  rationale: "Imputed matrix.",
  n_total_ids: 1000,
  n_in_reference: 310,
  overlap_cutoff: 0.2,
  source_files: [
    { file: "proteinGroups.txt", url: "https://ftp.pride.ebi.ac.uk/x.zip", archive: "x.zip", sha256: "ab".repeat(32) },
    { file: "Table S1.xlsx", sheet: "All" },
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

test("links only files with a public URL and falls back to the paper and deposit", () => {
  const html = renderToStaticMarkup(<MethodsBody arm={arm} m={m} />);
  assert.match(html, /href="https:\/\/ftp\.pride\.ebi\.ac\.uk\/x\.zip"[^>]*>proteinGroups\.txt</);
  assert.doesNotMatch(html, /href="[^"]*"[^>]*>Table S1\.xlsx</);
  assert.match(html, /Files without a link come from the paper&#x27;s supplement/);
  assert.match(html, /href="https:\/\/doi\.org\/10\.1\/x"/);
  assert.match(html, /GetDataset\?ID=PXD000001/);
  assert.match(html, /Orbitrap Exploris 480/);
  assert.match(html, /Imputed matrix\./);
  assert.match(html, /310 of 1,000 reported IDs/);
  assert.match(html, /drop rows flagged Reverse/);
  assert.match(html, /LFQ 1, LFQ 2/);
  assert.match(html, /3 whose species could not be resolved/);
});

test("repositoryUrl knows the major proteomics repositories only", () => {
  assert.equal(repositoryUrl("MSV000102332"), "https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=MSV000102332");
  assert.equal(repositoryUrl("JPST003825"), "https://repository.jpostdb.org/entry/JPST003825");
  assert.equal(repositoryUrl("none"), null);
});
