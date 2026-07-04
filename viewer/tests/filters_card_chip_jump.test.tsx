/*
 * Render tests for the §01 Summary metrics clickable-chip wiring.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/filters_card_chip_jump.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FiltersCard } from "../components/surfaceome/FiltersCard/FiltersCard";
import type { SurfaceomeRecord } from "../lib/surfaceome-types";
import { baseRecord } from "./helpers/fixtures";

test("biology ligand chip is wrapped in a ChipJumpButton when rationale exists", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "IGF-1 binding characterized (a1_evi_04).";
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<span[^>]*data-chip-jump-target="chip-jump-biology-ligand"/,
    "ligand chip must be wrapped in a ChipJumpButton on the live FiltersCard render",
  );
  assert.match(
    html,
    /aria-label="Jump to rationale: Known ligand"/,
    "aria-label must describe the destination",
  );
});

test("biology chip stays static when rationale is null (FiltersCard render)", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.filters.has_known_ligand = false;
  rec.filters.has_known_ligand_rationale = null;
  const html = renderFiltersCard(rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    "no chip-jump-target wrapper when rationale is null",
  );
});

test('biology chip stays static when rationale === "None" (FiltersCard render)', () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.filters.has_known_ligand = true;
  rec.filters.has_known_ligand_rationale = "None";
  const html = renderFiltersCard(rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-biology-ligand"/.test(html),
    false,
    'nz("None") is null → chip stays static',
  );
});

/** Extend the baseRecord() fixture with the minimum fields FiltersCard
 *  reads at render time: rec.gene (used by GROUP_META links), full
 *  deterministic_features block (orthologs / paralogs / surface_bind /
 *  homo_oligomerization + a fleshed-out canonical_topology), and a
 *  surface_evidence block for the contradiction chip logic. */
function withFiltersCardFixtures(rec: SurfaceomeRecord): SurfaceomeRecord {
  (rec as unknown as { gene: unknown }).gene = {
    hgnc_symbol: "TESTGENE",
    hgnc_id: "HGNC:1",
    uniprot_acc: "P00001",
    ncbi_gene_id: 1,
    ensembl_gene: "ENSG00000000001",
  };
  (rec as unknown as { surface_evidence: unknown }).surface_evidence = {
    evidence_grade: "absent",
    grade_rationale: "",
    claim_stances: [],
    methods: [],
    non_surface_expression: [],
    contradicting_evidence: [],
    excluded_as_ligand_engagement: [],
  };
  (rec as unknown as { deterministic_features: unknown }).deterministic_features = {
    canonical_topology: {
      ecd_length_residues: 100,
      tm_helix_count: 1,
      per_residue_topology: "OOOOMMMMIIII",
    },
    isoform_topologies: [],
    orthologs: { mouse: [], cynomolgus: [] },
    paralogs: [],
    structure: {
      afdb_id: "AF-P00001-F1",
      afdb_version: "v4",
      ecd_mean_plddt: 80,
      ecd_disordered_fraction: 0.1,
      source: "",
      license: "",
      attribution: "",
      citations: [],
    },
    surface_bind: {
      has_data: false,
      n_sites: 0,
      n_seeds_alpha: 0,
      n_seeds_beta: 0,
      n_seeds_total: 0,
      chain: null,
      sites: [],
      main_class: null,
      sub_class: null,
      protein_name: null,
      pdbs: [],
      source: "",
      attribution: "",
      citation: "",
    },
    homo_oligomerization: {
      is_homo_oligomer: false,
      is_ecd_only: false,
      has_higher_order_complex: false,
      source: "",
      citation: "",
    },
  };
  // executive_summary already exists on baseRecord; augment with the fields
  // FiltersCard reads (surface_call_reason for the reason chip, uniprot_family
  // / hgnc_gene_groups for the Family & gene group block).
  (rec.executive_summary as Record<string, unknown>).surface_call_reason =
    "classical_surface_receptor";
  (rec.executive_summary as Record<string, unknown>).uniprot_family = null;
  (rec.executive_summary as Record<string, unknown>).hgnc_gene_groups = [];
  return rec;
}

function renderFiltersCard(rec: SurfaceomeRecord): string {
  return renderToStaticMarkup(React.createElement(FiltersCard, { rec, n: 1 }));
}

test("primary chip is wrapped in a ChipJumpButton to the compartment block", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<span[^>]*data-chip-jump-target="chip-jump-primary-compartment"[^>]*data-chip-jump-tab="biology"/,
    "primary chip must jump to the Biology tab compartment block",
  );
});

test("contradiction chip stays static when severity is none", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.surface_evidence.contradicting_evidence = [];
  const html = renderFiltersCard(rec);
  assert.equal(
    /data-chip-jump-target="chip-jump-contradicting-evidence"/.test(html),
    false,
    'contradiction === "none" must not be clickable — no destination content',
  );
});

test("contradiction chip is wrapped when severity is present", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.surface_evidence.contradicting_evidence = [
    {
      claim: "Cytoplasmic staining reported.",
      contradiction_type: "alternative_localization",
      severity_for_surface_accessibility: "moderate",
      likely_explanation: null,
      cited_evidence_ids: [],
    },
  ];
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<span[^>]*data-chip-jump-target="chip-jump-contradicting-evidence"[^>]*data-chip-jump-tab="evidence"/,
    "contradiction chip must jump to the Evidence tab block",
  );
});

test("modulation category chip is wrapped and targets its row", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  rec.biological_context.accessibility_modulation = [
    {
      category: "cell_state_induced",
      category_other_label: null,
      cell_state_trigger: null,
      restricted_lineage: null,
      dual_loc_partner_compartment: null,
      baseline_context: "resting",
      modulating_state: "activated",
      change: "5x",
      accessibility_implication: "up",
      direction: "increases",
      cited_evidence_ids: [],
    },
  ];
  const html = renderFiltersCard(rec);
  assert.match(
    html,
    /<span[^>]*data-chip-jump-target="chip-jump-modulation-cell_state_induced"[^>]*data-chip-jump-tab="biology"/,
    "modulation category chip must jump to its row on the Biology tab",
  );
});

test("reason chip stays static (no clean destination)", () => {
  const rec = withFiltersCardFixtures(baseRecord());
  (rec.executive_summary as Record<string, unknown>).surface_call_reason =
    "classical_surface_receptor";
  const html = renderFiltersCard(rec);
  assert.equal(
    /aria-label="Jump to reason:/.test(html),
    false,
    "reason chip must remain a plain StatusPill",
  );
});
