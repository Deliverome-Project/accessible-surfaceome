/*
 * SurfaceBench model / variant handling: the rendered model and variant
 * sets come from the matrix payload (ordered by the label tables, unknown
 * ids appended under derived labels), refusals are a distinct cell state,
 * and TSV column prefixes stay unique within a model family.
 *
 *   npx --yes tsx --import ./tests/helpers/register.mjs \
 *       --test tests/benchmark_table_models.test.tsx
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { BenchmarkTable } from "../components/BenchmarkTable/BenchmarkTable";
import {
  MODEL_LABELS,
  cellStatus,
  fallbackModelLabel,
  modelLabelsFor,
  modelSlug,
  variantLabelsFor,
} from "../components/BenchmarkTable/benchmarkLabels";
import type { BenchmarkMatrix } from "../lib/surfaceome-types";

function matrix(models: string[], variants: string[]): BenchmarkMatrix {
  return {
    bench_version: null,
    universe_version: null,
    sources: ["uniprot", "go", "surfy", "cspa", "hpa"],
    models,
    variants,
    headline_variant: "ncbi",
    n_genes: 0,
    rows: [],
  };
}

// Payload order as the Worker sends it (not display order).
const PAYLOAD_MODELS = [
  "claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5",
  "claude-sonnet-5", "claude-opus-5",
  "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5",
];
const PAYLOAD_VARIANTS = ["naive", "ncbi", "web_ncbi", "pubmed_ncbi", "ncbi_effort_low"];

test("models render in family-then-version display order", () => {
  const labels = modelLabelsFor(matrix(PAYLOAD_MODELS, PAYLOAD_VARIANTS));
  assert.deepEqual(
    labels.map((m) => m.long),
    [
      "Haiku 4.5", "Haiku 5.5", "Sonnet 4.6", "Sonnet 5", "Sonnet 5.5",
      "Opus 4.8", "Opus 5", "Opus 5.5",
    ],
  );
});

test("low-effort variant sits next to ncbi", () => {
  const labels = variantLabelsFor(matrix(PAYLOAD_MODELS, PAYLOAD_VARIANTS));
  assert.deepEqual(
    labels.map((v) => v.id),
    ["naive", "ncbi", "ncbi_effort_low", "web_ncbi", "pubmed_ncbi"],
  );
});

test("unknown model and variant ids still render, after the known ones", () => {
  const m = matrix(
    ["claude-sonnet-4-6", "claude-sonnet-6-1"],
    ["ncbi", "ncbi_effort_max"],
  );
  assert.deepEqual(
    modelLabelsFor(m).map((l) => l.long),
    ["Sonnet 4.6", "Sonnet 6.1"],
  );
  assert.deepEqual(
    variantLabelsFor(m).map((l) => l.long),
    ["HGNC + UniProt + NCBI summary", "ncbi effort max"],
  );
  assert.equal(fallbackModelLabel("claude-mythos-7").long, "Mythos 7");
});

test("a model with cells but missing from `models` still renders", () => {
  const m = matrix(["claude-sonnet-4-6"], ["ncbi"]);
  m.rows = [
    {
      gene_symbol: "GENEX",
      uniprot_acc: "P00000",
      class: "x",
      truth_verdict: "yes",
      truth_signal: "",
      truth_reason: "",
      db: null,
      n_db_surface: 0,
      verdicts: { "claude-opus-5": { ncbi: null } },
    },
  ];
  assert.deepEqual(
    modelLabelsFor(m).map((l) => l.id),
    ["claude-sonnet-4-6", "claude-opus-5"],
  );
});

test("refusals are distinct from errors and from missing runs", () => {
  const base = {
    reason: null, confidence: null, key_uncertainty: null, reasoning: null,
    correct: null, latency_s: null, n_web_searches: null, created_at: null,
  };
  assert.equal(cellStatus(undefined), "missing");
  assert.equal(cellStatus(null), "missing");
  assert.equal(cellStatus({ ...base, verdict: null, error: "refusal" }), "refused");
  assert.equal(
    cellStatus({ ...base, verdict: null, error: "could not parse JSON from response" }),
    "errored",
  );
  assert.equal(cellStatus({ ...base, verdict: "yes", error: null }), "verdict");
});

test("TSV slugs are unique across every known model", () => {
  const slugs = MODEL_LABELS.map((m) => modelSlug(m.id));
  assert.equal(new Set(slugs).size, slugs.length);
  assert.equal(modelSlug("claude-sonnet-4-6"), "sonnet_4_6");
  assert.equal(modelSlug("claude-opus-5"), "opus_5");
});

test("header renders one sortable column per model, production marked", () => {
  const html = renderToStaticMarkup(
    React.createElement(BenchmarkTable, {
      matrix: matrix(PAYLOAD_MODELS, PAYLOAD_VARIANTS),
      deepDiveGenes: new Set<string>(),
    }),
  );
  for (const title of [
    "Haiku 4.5", "Haiku 5.5", "Sonnet 4.6", "Sonnet 5", "Sonnet 5.5",
    "Opus 4.8", "Opus 5", "Opus 5.5",
  ]) {
    assert.ok(html.includes(`title="${title} · `), `missing header for ${title}`);
  }
  assert.ok(html.includes("Sonnet 4.6 · HGNC + UniProt + NCBI summary · production configuration"));
  assert.ok(html.includes("compare all 5 prompt"));
});
