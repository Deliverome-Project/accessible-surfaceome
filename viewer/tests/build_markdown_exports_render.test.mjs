/*
 * Rendering tests for build-markdown-exports.mjs — pins the per-gene
 * Markdown brief against the defects a 2026-10 audit found in the
 * published briefs:
 *   - appendix links pointed at surfaceome.deliverome.org/data/surfaceome/
 *     {SYM}.json|.md, which 404 (prune-export.mjs deletes them);
 *   - "null → null" printed for single-context accessibility-modulation rows;
 *   - "None validation (None)" on antibodies with no validation;
 *   - raw HTML (<h4>, <i>, <sup>, <sub>) inside verbatim quote blockquotes;
 *   - "Ensembl —" when a gene has no mouse ortholog but does have a
 *     cynomolgus one;
 *   - the evidence endpoint's `papers` citation map was dropped, so the
 *     ledger showed bare accessions (and PMID-only sources no PMID link).
 *
 * Fixture-based: each test deep-clones the committed CD63 snapshot and
 * mutates only the fields under test, so md() runs on a real record shape.
 * Importing the module does not touch the network or the filesystem (its
 * main() only auto-runs when executed directly).
 *
 *   node --test tests/build_markdown_exports_render.test.mjs
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// A non-public Worker base: proves the appendix links use the public
// constant, never the env-overridable fetch base.
process.env.SURFACEOME_API_BASE = "https://example.test/surfaceome";
process.env.SURFACEOME_MD_SOURCE = "snapshots";

const {
  md,
  quoteToMarkdown,
  evidenceCitations,
  modulationContrast,
  antibodyValidationClause,
  comparaVersionOf,
} = await import("../scripts/build-markdown-exports.mjs");

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = JSON.parse(
  readFileSync(path.join(__dirname, "..", "public", "data", "surfaceome", "CD63.json"), "utf-8"),
);

function fixture() {
  return structuredClone(FIXTURE);
}

function render(rec, papers = null) {
  return md(rec, null, {}, null, papers);
}

// ----------------------------------------------------------------
// 1. Appendix links
// ----------------------------------------------------------------

test("appendix links point at the public API, never the pruned /data/surfaceome/ files", () => {
  const out = render(fixture());
  assert.ok(!out.includes("/data/surfaceome/"), "no link to the pruned per-gene files");
  assert.ok(!out.includes("example.test"), "an overridden fetch base must not leak into the brief");
  const base = "https://api.deliverome.org/surfaceome/v1/genes/CD63";
  assert.ok(out.includes(`[${base}](${base})`), "record JSON link");
  assert.ok(out.includes(`[${base}/evidence](${base}/evidence)`), "evidence ledger link");
  assert.ok(out.includes(`[${base}.md](${base}.md)`), "this-Markdown link");
});

// ----------------------------------------------------------------
// 2. Accessibility-modulation contrast
// ----------------------------------------------------------------

test("modulationContrast: arrow only when both sides are set; one side is labelled; neither → empty", () => {
  assert.equal(modulationContrast({ baseline_context: "resting", modulating_state: "activated" }), "resting → activated — ");
  assert.equal(modulationContrast({ baseline_context: "resting", modulating_state: null }), "reference: resting — ");
  assert.equal(modulationContrast({ baseline_context: null, modulating_state: "activated" }), "modulating state: activated — ");
  assert.equal(modulationContrast({ baseline_context: null, modulating_state: null }), "");
  assert.equal(modulationContrast({}), "");
});

test("md: a single-context modulation row never prints 'null → null'", () => {
  const rec = fixture();
  const row = rec.biological_context.accessibility_modulation[0];
  rec.biological_context.accessibility_modulation = [
    { ...row, baseline_context: null, modulating_state: null, change: "Only-context change." },
    { ...row, baseline_context: "resting X", modulating_state: "activated X", change: "Contrast change." },
  ];
  const out = render(rec);
  assert.ok(!out.includes("null"), "no literal null anywhere in the brief");
  assert.match(out, /: Only-context change\./);
  assert.match(out, /: resting X → activated X — Contrast change\./);
});

// ----------------------------------------------------------------
// 3. Antibody validation clause
// ----------------------------------------------------------------

test("antibodyValidationClause: 'none' reads 'no validation'; a none/null strategy is hidden", () => {
  assert.equal(antibodyValidationClause({ validation_strength: "none", validation_strategy: "none" }), "; no validation");
  assert.equal(antibodyValidationClause({ validation_strength: "None", validation_strategy: null }), "; no validation");
  assert.equal(antibodyValidationClause({ validation_strength: "strong", validation_strategy: "genetic_KO" }), "; Strong validation (Genetic KO)");
  assert.equal(antibodyValidationClause({ validation_strength: "weak", validation_strategy: "null" }), "; Weak validation");
  assert.equal(antibodyValidationClause({ validation_strength: null, validation_strategy: null }), "");
});

test("md: an unvalidated antibody never renders 'None validation (None)'", () => {
  const rec = fixture();
  const m = rec.surface_evidence.methods.find((x) => x.antibodies.length);
  m.antibodies = [{ ...m.antibodies[0], name: "anti-TEST", validation_strength: "none", validation_strategy: "none" }];
  const out = render(rec);
  assert.ok(!/None validation|\(None\)/.test(out));
  assert.match(out, /- anti-TEST[^\n]*; no validation/);
});

// ----------------------------------------------------------------
// 4. Raw HTML in verbatim quotes
// ----------------------------------------------------------------

test("quoteToMarkdown: converts trivial inline tags and strips block tags without changing words", () => {
  assert.equal(quoteToMarkdown("reduced upon <i>GENEX</i> loss."), "reduced upon *GENEX* loss.");
  assert.equal(quoteToMarkdown("an <em>in vivo</em> assay"), "an *in vivo* assay");
  assert.equal(quoteToMarkdown("dermal X<sup>+</sup> cells"), "dermal X^+ cells");
  assert.equal(quoteToMarkdown("10<sup>8</sup> particles"), "10^8 particles");
  assert.equal(quoteToMarkdown("EC<sub>50 </sub>values; C3(H<sub>2</sub>O)"), "EC50 values; C3(H2O)");
  // Headings become the same inline "Label:" marker the viewer's
  // stripInlineHtml renders, instead of colliding into the next sentence.
  assert.equal(
    quoteToMarkdown("the domain.<h4>Conclusions</h4>Disruption of glycosylation"),
    "the domain. Conclusions: Disruption of glycosylation",
  );
  assert.equal(quoteToMarkdown("<h4>Background & aims</h4>A sheddase"), "Background & aims: A sheddase");
  assert.equal(quoteToMarkdown("<i> padded </i>word"), "*padded* word");
  assert.equal(quoteToMarkdown("a <b>bold</b> and <strong>strong</strong> claim"), "a **bold** and **strong** claim");
  assert.equal(quoteToMarkdown("first<br/>second"), "first second");
  // JATS-flavoured tags the viewer also scrubs.
  assert.equal(
    quoteToMarkdown('<italic>GENEX</italic><superscript>-/-</superscript> mice <xref ref-type="bibr">(12)</xref>'),
    "*GENEX*^-/- mice (12)",
  );
});

test("quoteToMarkdown: leaves non-tag angle brackets and tag-free quotes untouched", () => {
  for (const s of [
    "significant at p<0.05 and n>3",
    "an ECD of <10 aa and a 2 < 3 > 1 chain",
    "plain  quote with  double spaces",
    "",
  ]) {
    assert.equal(quoteToMarkdown(s), s);
  }
  assert.equal(quoteToMarkdown(null), null);
});

test("md: ledger quote blockquotes carry no raw HTML", () => {
  const rec = fixture();
  rec.evidence[0].spans[0].quote =
    "Surface level of <i>GENEX</i> rose.<h4>Results</h4>CD63<sup>+</sup> cells, EC<sub>50</sub> 2 nM.";
  const out = render(rec);
  assert.ok(out.includes('  > "Surface level of *GENEX* rose. Results: CD63^+ cells, EC50 2 nM."'));
  for (const line of out.split("\n").filter((l) => l.startsWith("  > "))) {
    assert.ok(!/<\/?(?:h[1-6]|i|em|b|strong|sup|sub)>/i.test(line), line);
  }
});

// ----------------------------------------------------------------
// 5. Compara label fallback
// ----------------------------------------------------------------

test("comparaVersionOf: mouse → cynomolgus → paralogs → em-dash", () => {
  const v = (x) => [{ compara_version: x }];
  assert.equal(comparaVersionOf({ orthologs: { mouse: v("m"), cynomolgus: v("c") }, paralogs: v("p") }), "m");
  assert.equal(comparaVersionOf({ orthologs: { mouse: [], cynomolgus: v("c") }, paralogs: v("p") }), "c");
  assert.equal(comparaVersionOf({ orthologs: { mouse: [], cynomolgus: [] }, paralogs: v("p") }), "p");
  assert.equal(comparaVersionOf({ orthologs: { mouse: [], cynomolgus: [] }, paralogs: [] }), "—");
});

test("md: a gene with only a cynomolgus ortholog names its Compara release, not '—'", () => {
  const rec = fixture();
  const df = rec.deterministic_features;
  df.orthologs.mouse = [];
  df.paralogs = [];
  df.orthologs.cynomolgus = df.orthologs.cynomolgus.map((o) => ({ ...o, compara_version: "ensembl_compara_TEST" }));
  const out = render(rec);
  assert.ok(out.includes("Ensembl ensembl_compara_TEST."), "§5 label");
  assert.ok(out.includes("Ensembl Compara orthologs & paralogs — ensembl_compara_TEST ·"), "data-sources footer");
  assert.ok(!out.includes("Ensembl —"));
});

// ----------------------------------------------------------------
// 6. Ledger citations from the `papers` map
// ----------------------------------------------------------------

const PAPERS = {
  "PMC:PMC111": { source_id: "PMC:PMC111", pmid: "1001", pmc_id: "PMC111", authors_short: "Doe et al.", year: 2020 },
  "PMID:2002": { source_id: "PMID:2002", pmid: "2002", pmc_id: null, authors_short: "Roe & Poe", year: 2019 },
};

test("evidenceCitations: author/year + PubMed link from `papers`, PMC link kept, deduped by source", () => {
  const pmc = { source_id: "PMC:PMC111", pmc_id: "PMC111", url: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC111/" };
  const pmidOnly = { source_id: "PMID:2002", pmc_id: null, url: "https://pubmed.ncbi.nlm.nih.gov/2002/" };
  assert.equal(
    evidenceCitations([pmc, pmc, pmidOnly], PAPERS),
    "Doe et al. 2020, [PMID 1001](https://pubmed.ncbi.nlm.nih.gov/1001/) · [PMC111](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC111/); " +
      "Roe & Poe 2019, [PMID 2002](https://pubmed.ncbi.nlm.nih.gov/2002/)",
  );
  // No metadata (snapshot path): bare accessions, still a PMID link for a
  // PMID-keyed source.
  assert.equal(
    evidenceCitations([pmc, pmidOnly], null),
    "[PMC111](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC111/); [PMID 2002](https://pubmed.ncbi.nlm.nih.gov/2002/)",
  );
  // A url-only source keeps the raw-url fallback.
  assert.equal(evidenceCitations([{ url: "https://example.org/x" }], null), "https://example.org/x");
});

test("md: ledger entries use the papers map when given, and degrade without it", () => {
  const rec = fixture();
  const span = rec.evidence[0].spans[0];
  span.source = { ...span.source, source_id: "PMC:PMC111", pmc_id: "PMC111" };
  const withPapers = render(rec, PAPERS);
  assert.match(
    withPapers,
    /- `a1_evi_01` [^\n]*\(Doe et al\. 2020, \[PMID 1001\]\(https:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/1001\/\) · \[PMC111\]\(https:\/\/www\.ncbi\.nlm\.nih\.gov\/pmc\/articles\/PMC111\/\)\)/,
  );
  const without = render(rec);
  assert.match(without, /- `a1_evi_01` [^\n]*\(\[PMC111\]\(https:\/\/www\.ncbi\.nlm\.nih\.gov\/pmc\/articles\/PMC111\/\)\)/);
});

// ----------------------------------------------------------------
// 8. Deterministic output (no export timestamp)
// ----------------------------------------------------------------

test("md: output is a pure function of its inputs (no export timestamp churning record-history hashes)", async () => {
  const rec = fixture();
  const a = render(rec, PAPERS);
  await new Promise((r) => setTimeout(r, 5));
  const b = render(structuredClone(rec), PAPERS);
  assert.equal(a, b);
});
