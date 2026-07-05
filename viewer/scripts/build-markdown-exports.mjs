#!/usr/bin/env node
// Build human-readable markdown exports next to each per-gene
// SurfaceomeRecord JSON.
//
// For every ``viewer/public/data/surfaceome/{SYMBOL}.json`` this script
// emits a sibling ``{SYMBOL}.md`` that bundles:
//
//   * the executive summary + every section in scientific section order
//   * a "Downloads & reproduction" appendix with:
//       - the AFDB entry URL + the prediction-API endpoint
//       - the full UniProt canonical sequence (fetched from AFDB API)
//       - the per-residue DeepTMHMM topology for canonical + every
//         alternative isoform on the record
//       - links back to the JSON record and the Pages page
//
// Run from the ``viewer/`` directory: ``node scripts/build-markdown-exports.mjs``.
// Safe to re-run — the script overwrites existing .md files.
//
// One-shot, side-effect-only — does not import any Next.js code. The
// markdown rendering lives here rather than in ``viewer/lib/`` to keep
// it server-build-only.

import { readFileSync, readdirSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VIEWER_ROOT = path.resolve(__dirname, "..");
const DATA_DIR = path.join(VIEWER_ROOT, "public", "data", "surfaceome");
const STRUCTURE_DIR = path.join(VIEWER_ROOT, "public", "structure-viewer");

const SITE_BASE = "https://surfaceome.deliverome.org";

// Where records come from. Default "api" = the D1-served model: the
// deep-dive sweep publishes to D1 and the build fetches the full published
// set from the public Worker, materializing {SYMBOL}.json + {SYMBOL}.md at
// build time (build artifacts, not committed). This is the D1-only path —
// the committed viewer/public/data/surfaceome/*.json are NOT read. Opt back
// into the in-tree snapshots with SURFACEOME_MD_SOURCE=snapshots (offline
// local dev only). SURFACEOME_API_BASE=local (or empty) skips the export
// entirely (CI offline smoke) rather than falling back to committed JSONs.
// SURFACEOME_MD_LIMIT caps the count (testing / incremental builds).
const MD_SOURCE = (process.env.SURFACEOME_MD_SOURCE || "api").toLowerCase();
// Worker base, normalized to EXCLUDE a trailing /v1 (the loader convention)
// so /v1 is appended uniformly below. Accepts both ".../surfaceome" (the
// Pages value) and ".../surfaceome/v1" (legacy) without doubling /v1.
const RAW_API_BASE = (
  process.env.SURFACEOME_API_BASE || "https://api.deliverome.org/surfaceome"
).trim();
const API_BASE = RAW_API_BASE.replace(/\/+$/, "").replace(/\/v1$/, "");

// --------------------------------------------------------------
// Pretty-print helpers — kept simple so the script has no deps.
// --------------------------------------------------------------

function prettyEnum(value) {
  if (value == null) return "—";
  const s = String(value);
  // Special cases that don't survive the title-case mapping.
  const overrides = {
    direct_multi_method: "Direct, multi-method",
    direct_single_method: "Direct, single method",
    supportive_but_indirect: "Supportive but indirect",
    GPCR: "GPCR",
    GPI_anchored: "GPI-anchored",
    single_pass_T1: "Single-pass type I",
    single_pass_T2: "Single-pass type II",
    multi_pass: "Multi-pass",
    plasma_membrane: "Plasma membrane",
    likely_accessible: "Likely accessible",
    no_literature: "No literature",
    outside_scope: "Outside scope",
    none_documented: "None documented",
  };
  if (overrides[s]) return overrides[s];
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Null-safe percent formatter. v1.1.0 records can carry a null
// `ecd_pct_identity` on a paralog row (Compara returned no aligned ECD),
// which used to crash `.toFixed` mid-run and abort the whole export.
function fmtPct(v) {
  return v == null ? "—" : `${v.toFixed(1)}%`;
}

// Null-safe fixed-decimal formatter for non-percent scalars (pLDDT etc.).
function fmtNum(v, digits = 1) {
  return v == null ? "—" : v.toFixed(digits);
}

// Thousands-separated integer (locale-independent, so the build is
// deterministic regardless of the runner's locale).
function fmtInt(v) {
  return v == null ? "—" : String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function alphafoldEntryUrl(uniprot) {
  return `https://alphafold.ebi.ac.uk/entry/${uniprot}`;
}

function alphafoldApiUrl(uniprot) {
  return `https://alphafold.ebi.ac.uk/api/prediction/${uniprot}`;
}

function wrapTopology(s, width = 60) {
  if (!s) return "";
  const lines = [];
  for (let i = 0; i < s.length; i += width) {
    const startResi = i + 1;
    const chunk = s.slice(i, i + width);
    lines.push(`${String(startResi).padStart(4, " ")}  ${chunk}`);
  }
  return lines.join("\n");
}

function wrapSequence(s, width = 60) {
  if (!s) return "";
  const lines = [];
  for (let i = 0; i < s.length; i += width) {
    const startResi = i + 1;
    const chunk = s.slice(i, i + width);
    lines.push(`${String(startResi).padStart(4, " ")}  ${chunk}`);
  }
  return lines.join("\n");
}

// --------------------------------------------------------------
// Sequence + structure-model fetch.
//
// The AFDB prediction API returns BOTH the UniProt canonical sequence
// and the model download URLs (cifUrl / pdbUrl / paeDocUrl) in one
// response, so we cache the parsed entry per accession and derive
// sequence + model links from it.
//
// Not every protein has an AFDB model — very large proteins (megalin /
// LRP2, ~4655 aa) return 404, and isoform accessions (e.g. P00533-2)
// are never keyed in AFDB. For those we fall back to UniProt's FASTA
// endpoint, which always carries the sequence, so a no-model protein
// or an alternative isoform still ships its full sequence for
// reanalysis. Each accession is fetched at most once per run.
// --------------------------------------------------------------

const FETCH_UA =
  "accessible-surfaceome-viewer/1.0 (build-markdown-exports.mjs)";

const afdbEntryCache = new Map();

async function fetchAfdbEntry(uniprot) {
  if (afdbEntryCache.has(uniprot)) return afdbEntryCache.get(uniprot);
  let entry = null;
  try {
    const resp = await fetch(alphafoldApiUrl(uniprot), {
      // AFDB's edge returns 403 for the default Node fetch UA; a named
      // UA passes. (They explicitly block "node" / "undici".)
      headers: { "User-Agent": FETCH_UA, Accept: "application/json" },
    });
    if (resp.ok) {
      const entries = await resp.json();
      entry = entries[0] ?? null;
    } else if (resp.status !== 404) {
      // 404 = no model (expected for big proteins); only warn on other
      // statuses so a real outage is still visible.
      console.warn(`  ! AFDB API returned ${resp.status} for ${uniprot}`);
    }
  } catch (err) {
    console.warn(`  ! AFDB API fetch failed for ${uniprot}: ${err.message}`);
  }
  afdbEntryCache.set(uniprot, entry);
  return entry;
}

async function fetchUniprotFasta(uniprot) {
  try {
    const resp = await fetch(
      `https://rest.uniprot.org/uniprotkb/${uniprot}.fasta`,
      { headers: { "User-Agent": FETCH_UA, Accept: "text/plain" } },
    );
    if (!resp.ok) {
      console.warn(`  ! UniProt FASTA returned ${resp.status} for ${uniprot}`);
      return null;
    }
    const text = await resp.text();
    const seq = text
      .split("\n")
      .filter((l) => l && !l.startsWith(">"))
      .join("")
      .trim();
    return seq || null;
  } catch (err) {
    console.warn(
      `  ! UniProt FASTA fetch failed for ${uniprot}: ${err.message}`,
    );
    return null;
  }
}

const sequenceCache = new Map();

async function fetchSequence(uniprot) {
  if (sequenceCache.has(uniprot)) return sequenceCache.get(uniprot);
  const entry = await fetchAfdbEntry(uniprot);
  let seq = entry?.uniprotSequence ?? null;
  // No AFDB model (large proteins, isoform accessions) → UniProt FASTA.
  if (!seq) seq = await fetchUniprotFasta(uniprot);
  sequenceCache.set(uniprot, seq);
  return seq;
}

// Assay-family grouping for §3 — mirrors the viewer's SurfaceEvidenceCard:
// antibody-based direct assays first (flow → IF → IHC), then surface MS +
// biochemical cousins, then functional, then the catch-all.
const FAMILY_ORDER = [
  "flow_cytometry",
  "immunofluorescence",
  "immunohistochemistry",
  "mass_spec",
  "biotinylation",
  "glycoproteomics",
  "proximity_labeling",
  "fractionation",
  "functional_surface_assay",
  "other",
];
const FAMILY_LABEL = {
  flow_cytometry: "Flow cytometry",
  immunofluorescence: "Immunofluorescence",
  immunohistochemistry: "Immunohistochemistry",
  mass_spec: "Surface mass spec",
  biotinylation: "Surface biotinylation",
  glycoproteomics: "Glycoproteomics",
  proximity_labeling: "Proximity labeling",
  fractionation: "Membrane fractionation",
  functional_surface_assay: "Functional surface assay",
  other: "Other",
};

// Render one accessibility-risk / context block as a bullet list. Shared by
// §8 (shed / secreted / ECD size / epitope masking) and §4 (restricted
// subdomain + co-receptor, which live under Biology in the viewer).
function pushRiskBlock(lines, title, block) {
  lines.push(`**${title}**`);
  lines.push("");
  if ("present" in block) lines.push(`- present: ${block.present}`);
  if ("severity" in block) lines.push(`- severity: ${prettyEnum(block.severity)}`);
  if ("evidence_strength" in block)
    lines.push(`- evidence: ${prettyEnum(block.evidence_strength)}`);
  if ("mechanism" in block && block.mechanism != null) {
    const mech = Array.isArray(block.mechanism)
      ? block.mechanism.map(prettyEnum).join(", ")
      : prettyEnum(block.mechanism);
    lines.push(`- mechanism: ${mech}`);
  }
  if ("sheddase_if_known" in block && block.sheddase_if_known)
    lines.push(`- sheddase: ${block.sheddase_if_known}`);
  if ("source" in block && block.source)
    lines.push(`- source: ${prettyEnum(block.source)}`);
  if ("ratio_to_membrane" in block && block.ratio_to_membrane != null)
    lines.push(`- ratio to membrane: ${block.ratio_to_membrane}`);
  if ("domain" in block) lines.push(`- domain: ${prettyEnum(block.domain)}`);
  if ("surface_expression_dependency" in block)
    lines.push(`- dependency: ${prettyEnum(block.surface_expression_dependency)}`);
  if ("evidence_basis" in block)
    lines.push(`- evidence basis: ${prettyEnum(block.evidence_basis)}`);
  if ("partners" in block && block.partners?.length)
    lines.push(`- partners: ${block.partners.join(", ")}`);
  if ("ecd_accessibility_class" in block)
    lines.push(`- ECD class: ${prettyEnum(block.ecd_accessibility_class)}`);
  if ("rationale" in block && block.rationale)
    lines.push(`- rationale: ${block.rationale}`);
  if ("cited_evidence_ids" in block && block.cited_evidence_ids?.length)
    lines.push(`- cites: ${block.cited_evidence_ids.join(", ")}`);
  lines.push("");
}

// "N aa" or em-dash for the combined homolog table cells.
function aaOrDash(v) {
  return v == null ? "—" : `${v} aa`;
}

// Compact citation-id suffix — " *(cites: a1_evi_03, a1_evi_04)*" or "".
function citeIds(ids, max = 8) {
  if (!ids || !ids.length) return "";
  const shown = ids.slice(0, max).join(", ");
  return ` *(cites: ${shown}${ids.length > max ? `, +${ids.length - max}` : ""})*`;
}

// ECD-identity tiers — same cutoffs the viewer's IsoformsCard uses.
// Ortholog conservation (higher = better, cross-species evidence transfers).
function orthologTier(pct) {
  if (pct == null) return "—";
  if (pct >= 85) return "high (≥85%)";
  if (pct >= 60) return "moderate";
  return "low";
}
// Paralog cross-reactivity (higher = worse — a binder may also bind it).
function paralogTier(pct) {
  if (pct == null) return "—";
  if (pct > 80) return "high-risk (>80%)";
  if (pct >= 60) return "caution";
  return "low-risk";
}

// Map UniProt acc → sequence embedded in the record's deterministic_features
// (the builder / backfill now store the sequence each per-residue topology
// indexes). Lets the appendix prefer record-embedded sequences over a live
// AFDB/UniProt fetch — same residues, no network round-trip, fully offline.
function collectRecordSequences(df) {
  const out = {};
  const add = (acc, seq) => {
    if (acc && seq) out[acc] = seq;
  };
  if (df.canonical_topology)
    add(df.canonical_topology.uniprot_acc, df.canonical_topology.sequence);
  for (const iso of df.isoform_topologies ?? []) add(iso.uniprot_acc, iso.sequence);
  for (const sp of ["mouse", "cynomolgus"]) {
    for (const o of df.orthologs?.[sp] ?? [])
      add(o.ortholog_uniprot_acc, o.sequence);
  }
  for (const p of df.paralogs ?? []) add(p.paralog_uniprot_acc, p.sequence);
  return out;
}

// --------------------------------------------------------------
// Markdown rendering
// --------------------------------------------------------------

function md(rec, structureData, sequences, afdbEntry) {
  const g = rec.gene;
  const e = rec.executive_summary;
  const df = rec.deterministic_features;
  const ct = df.canonical_topology;
  const lines = [];

  lines.push(`# ${g.hgnc_symbol} — Surface Accessibility Brief`);
  lines.push("");
  lines.push(
    `*Schema v${rec.schema_version} · generated ${rec.record_generated_at} · model \`${rec.model_path}\`*`,
  );
  lines.push("");
  lines.push(`> ${e.one_paragraph}`);
  lines.push("");

  lines.push("**Vitals**");
  lines.push("");
  lines.push(
    `| Field | Value |`,
  );
  lines.push(`|---|---|`);
  lines.push(`| HGNC | [${g.hgnc_id}](https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}) |`);
  lines.push(`| UniProt | [${g.uniprot_acc}](https://www.uniprot.org/uniprotkb/${g.uniprot_acc}) |`);
  lines.push(`| NCBI Gene | [${g.ncbi_gene_id}](https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}) |`);
  lines.push(`| Ensembl | [${g.ensembl_gene}](https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}) |`);
  lines.push(`| Subcategory | ${prettyEnum(e.subcategory)} |`);
  lines.push(`| Surface accessibility | ${prettyEnum(e.surface_accessibility)} |`);
  lines.push(`| Confidence | ${prettyEnum(e.confidence)} |`);
  lines.push(`| Evidence grade | ${prettyEnum(e.evidence_grade_summary)} |`);
  lines.push(`| Triage signal | ${prettyEnum(rec.triage_signal)} |`);
  if (e.headline_risks.length > 0) {
    lines.push(
      `| Headline risks | ${e.headline_risks.map(prettyEnum).join(", ")} |`,
    );
  }
  lines.push("");

  lines.push("## 1. Executive summary");
  lines.push("");
  if (e.accessibility_context_summary) {
    lines.push(`**${e.accessibility_context_summary}**`);
    lines.push("");
  }
  lines.push(e.one_paragraph);
  lines.push("");
  // Family / classification — curated UniProt family + HGNC gene group(s) +
  // the model's functional class (what the viewer renders as family chips).
  const famBits = [
    e.uniprot_family && `UniProt family: ${e.uniprot_family}`,
    e.hgnc_gene_groups?.length &&
      `HGNC gene group(s): ${e.hgnc_gene_groups.join("; ")}`,
    e.llm_family && `functional class: ${prettyEnum(e.llm_family)}`,
  ].filter(Boolean);
  if (famBits.length) {
    lines.push(`**Family / classification** — ${famBits.join(" · ")}.`);
    lines.push("");
  }
  // Upstream triage (first-pass Sonnet) reasoning behind the triage signal.
  if (rec.triage_reasoning) {
    lines.push(`**Triage first-pass reasoning** — ${rec.triage_reasoning}`);
    lines.push("");
  }

  // --- Filters ---
  const f = rec.filters;
  lines.push("## 2. Filters / catalog facets");
  lines.push("");
  lines.push("| Group | Facets |");
  lines.push("|---|---|");
  lines.push(
    `| Accessibility | overall=${prettyEnum(f.surface_accessibility)} · conf=${prettyEnum(f.confidence)} · subcategory=${prettyEnum(f.subcategory)} · ecd=${prettyEnum(f.ecd_accessibility_class)} |`,
  );
  lines.push(
    `| Classification | reason=${prettyEnum(f.surface_call_reason)} · family=${prettyEnum(f.llm_family)} · state-dependence=${prettyEnum(f.state_dependence)} · induction-trigger=${prettyEnum(f.induction_trigger)} |`,
  );
  lines.push(
    `| Expression | level=${prettyEnum(f.expression_level)} · breadth=${prettyEnum(f.expression_breadth)} · specificity=${prettyEnum(f.surface_specificity)} · low-endogenous=${f.low_endogenous_expression} · tumor-associated=${f.tumor_associated ?? "—"} · orphan-receptor=${f.has_known_ligand === false} · OE-precedent=${f.overexpression_surface_localization_observed} |`,
  );
  lines.push(
    `| Risks | shed=${f.has_shed_form} · secreted=${f.has_secreted_form} · co-receptor=${prettyEnum(f.co_receptor_dependency)} · masking=${f.has_epitope_masking} · restricted-subdomain=${f.has_restricted_subdomain} |`,
  );
  lines.push(
    `| Evidence | grade=${prettyEnum(f.evidence_grade)} · density=${prettyEnum(f.evidence_density)} · live-cell-surface=${f.has_live_cell_surface_evidence ?? "—"} · supporting(hi)=${f.n_supporting_claims_high_weight ?? "—"} · contradicting(hi)=${f.n_contradicting_claims_high_weight ?? "—"} |`,
  );
  // Cross-species fields are nullable in v1.0.0 (a gene with no
  // mouse/cyno ortholog row in compara_ortholog_ecd lands NULL here).
  const mouseId = f.mouse_ortholog_ecd_pct_identity;
  const cynoId = f.cyno_ortholog_ecd_pct_identity;
  lines.push(
    `| Cross-species | mouse=${mouseId == null ? "—" : `${mouseId.toFixed(1)}%`} · cyno=${cynoId == null ? "—" : `${cynoId.toFixed(1)}%`} |`,
  );
  lines.push(
    `| Paralogs | max %ECD identity = ${
      f.max_paralog_ecd_pct_identity == null
        ? "no Compara paralogs"
        : `${f.max_paralog_ecd_pct_identity.toFixed(1)}%`
    } |`,
  );
  lines.push(
    `| Topology | TM=${ct.tm_helix_count} · N-term-ECF=${f.n_term_extracellular} · C-term-ECF=${f.c_term_extracellular} |`,
  );
  lines.push("");
  // Facet rationales — the one-line "why" the viewer shows as expandable
  // reasoning under each Summary-metrics chip.
  const facetRationales = [
    ["Expression level", f.expression_level_rationale],
    ["Expression breadth", f.expression_breadth_rationale],
    ["Surface specificity", f.surface_specificity_rationale],
    ["Known ligand", f.has_known_ligand_rationale],
    ["Low endogenous expression", f.low_endogenous_expression_rationale],
    [
      "Overexpression surface localization",
      f.overexpression_surface_localization_observed_rationale,
    ],
  ].filter(([, v]) => v);
  if (facetRationales.length) {
    lines.push("**Facet rationales**");
    lines.push("");
    for (const [label, val] of facetRationales)
      lines.push(`- *${label}*: ${val}`);
    lines.push("");
  }
  // Cutoff provenance for the banded facets (the thresholds + citations the
  // viewer tooltips carry).
  lines.push(
    "**Cutoffs.** ECD size: large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues / 1103 ± 244 Å², [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)). Evidence density: high ≥30 supporting rows · moderate ≥10 · low <10. Ortholog ECD identity: ≥85% high · 60–85% intermediate · <60% higher-risk. Paralog ECD identity: >80% multitarget-likely · 60–80% caution · <60% lower-risk ([PMID 30297845](https://pubmed.ncbi.nlm.nih.gov/30297845/)).",
  );
  lines.push("");

  // --- Surface evidence ---
  const se = rec.surface_evidence;
  lines.push("## 3. Surface evidence");
  lines.push("");
  lines.push(`**Evidence grade** · ${prettyEnum(se.evidence_grade)}`);
  lines.push("");
  lines.push(`${se.grade_rationale}`);
  lines.push("");
  // Per-claim stance accounting behind the grade — the structured anatomy
  // (supports / contradicts / tangential, with weight) under the prose.
  if (se.claim_stances?.length) {
    lines.push("**Claim stances** *(what the grade weighs)*");
    lines.push("");
    lines.push("| Claim | Stance | Weight | Note |");
    lines.push("|---|---|---|---|");
    for (const cs of se.claim_stances) {
      lines.push(
        `| ${cs.claim_id} | ${prettyEnum(cs.stance)} | ${prettyEnum(cs.weight)} | ${cs.note ?? "—"} |`,
      );
    }
    lines.push("");
  }
  // Group method observations by assay family (mirrors the viewer).
  const familyBuckets = new Map();
  for (const m of se.methods) {
    const fam = m.method_family ?? "other";
    if (!familyBuckets.has(fam)) familyBuckets.set(fam, []);
    familyBuckets.get(fam).push(m);
  }
  const orderedFamilies = [
    ...FAMILY_ORDER.filter((f) => familyBuckets.has(f)),
    ...[...familyBuckets.keys()].filter((f) => !FAMILY_ORDER.includes(f)),
  ];
  for (const fam of orderedFamilies) {
    const fmethods = familyBuckets.get(fam);
    lines.push(
      `### ${FAMILY_LABEL[fam] ?? prettyEnum(fam)} (${fmethods.length} method${fmethods.length === 1 ? "" : "s"})`,
    );
    lines.push("");
    for (const m of fmethods) {
      lines.push(
        `#### ${prettyEnum(m.method_subclass)} — ${prettyEnum(m.accessibility_relevance)}${m.surface_claim_type ? ` · ${prettyEnum(m.surface_claim_type)}` : ""}`,
      );
      lines.push("");
      lines.push(
        `*Permeabilization: ${prettyEnum(m.permeabilization)} · expression: ${prettyEnum(m.expression_system)}*`,
      );
      lines.push("");
      if (m.antibodies.length) {
        lines.push("**Antibodies**");
        lines.push("");
        for (const ab of m.antibodies) {
          const meta = [ab.clone, ab.vendor, ab.catalog, ab.rrid]
            .filter(Boolean)
            .join(" · ");
          lines.push(
            `- ${ab.name}${meta ? ` (${meta})` : ""} — ${prettyEnum(ab.antibody_epitope_region)} epitope; ${prettyEnum(ab.monoclonal_or_polyclonal)}; ${prettyEnum(ab.validation_strength)} validation${ab.validation_strategy ? ` (${prettyEnum(ab.validation_strategy)})` : ""}${ab.cross_reactivity_notes ? `; ${ab.cross_reactivity_notes}` : ""}`,
          );
        }
        lines.push("");
      }
      if (m.expression_observations.length) {
        lines.push("**Observations**");
        lines.push("");
        lines.push("| Context | Sample | Level | Cites |");
        lines.push("|---|---|---|---|");
        for (const o of m.expression_observations) {
          lines.push(
            `| ${o.context} | ${prettyEnum(o.sample_type)} | ${prettyEnum(o.level)} | ${o.cited_evidence_ids.length} |`,
          );
        }
        lines.push("");
      }
      // Overexpression construct details — load-bearing for whether an
      // OE-positive result can ground a *native*-surface claim (did it use
      // the native signal peptide? what tag / cell line?).
      if (m.overexpression) {
        const ox = m.overexpression;
        const oxBits = [
          ox.signal_peptide_source &&
            `SP source: ${prettyEnum(ox.signal_peptide_source)}`,
          ox.signal_peptide_detail,
          ox.construct_tag && `tag: ${ox.construct_tag}`,
          ox.cell_line && `cell line: ${ox.cell_line}`,
        ].filter(Boolean);
        if (oxBits.length) {
          lines.push(
            `*Overexpression construct* — ${oxBits.join(" · ")}.${citeIds(ox.cited_evidence_ids)}`,
          );
          lines.push("");
        }
      }
    }
  }
  if (se.non_surface_expression.length) {
    lines.push("**Non-surface expression**");
    lines.push("");
    lines.push("| Context | Sample | Measurement | Level | Cites |");
    lines.push("|---|---|---|---|---|");
    for (const o of se.non_surface_expression) {
      lines.push(
        `| ${o.context} | ${prettyEnum(o.sample_type)} | ${prettyEnum(o.measurement_type)} | ${prettyEnum(o.level)} | ${o.cited_evidence_ids.length} |`,
      );
    }
    lines.push("");
  }
  if (se.contradicting_evidence.length) {
    lines.push("**Contradicting evidence**");
    lines.push("");
    for (const c of se.contradicting_evidence) {
      lines.push(`- *${prettyEnum(c.contradiction_type)}* (severity ${prettyEnum(c.severity_for_surface_accessibility)}): ${c.claim}`);
      if (c.likely_explanation) {
        lines.push(`  - Likely explanation: ${c.likely_explanation}`);
      }
    }
    lines.push("");
  }

  // --- Biological context ---
  const bc = rec.biological_context;
  lines.push("## 4. Biological context");
  lines.push("");
  // A2 rollup grade — the A2 analog of surface_evidence's evidence_grade.
  // Pre-rollup records default to "absent" with an empty rationale; only
  // surface it when there's something to say.
  if (bc.biological_context_grade && bc.biological_context_grade !== "absent") {
    lines.push(`**Biological-context grade** · ${prettyEnum(bc.biological_context_grade)}`);
    lines.push("");
    if (bc.grade_rationale) {
      lines.push(`${bc.grade_rationale}${citeIds(bc.grade_cited_evidence_ids)}`);
      lines.push("");
    }
  }
  const expressionRows = bc.expression ?? []; // transitional: pre-migration records lack `expression`
  if (expressionRows.length) {
    lines.push("**Expression × cell type × disease context**");
    lines.push("");
    lines.push("| Tissue | Cell type | Disease context | Level (protein) | Cell states |");
    lines.push("|---|---|---|---|---|");
    for (const row of expressionRows) {
      const disease = row.disease_label
        ? `${prettyEnum(row.disease_context)} (${row.disease_label})`
        : prettyEnum(row.disease_context);
      lines.push(
        `| ${row.tissue || "—"} | ${row.cell_type || "—"} | ${disease} | ${prettyEnum(row.present)} | ${row.cell_states.join(", ") || "—"} |`,
      );
    }
    lines.push("");
  }
  // Orthogonal cell-type + cell-state pivots (alternative to the tissue index).
  if (bc.cell_types?.length) {
    lines.push("**Cell types** *(orthogonal cell-type index)*");
    lines.push("");
    lines.push("| Cell type | Ontology | Present in tissues | Species | Cites |");
    lines.push("|---|---|---|---|---|");
    for (const c of bc.cell_types) {
      lines.push(
        `| ${c.cell_type} | ${c.ontology_id ?? "—"} | ${(c.present_in_tissues || []).join(", ") || "—"} | ${prettyEnum(c.species)} | ${(c.cited_evidence_ids || []).length} |`,
      );
    }
    lines.push("");
  }
  if (bc.cell_states?.length) {
    lines.push("**Cell states**");
    lines.push("");
    for (const s of bc.cell_states) {
      lines.push(`- *${s.state}* — ${s.descriptor}${citeIds(s.cited_evidence_ids)}`);
    }
    lines.push("");
  }
  const sl = bc.subcellular_localization;
  lines.push(
    `**Primary subcellular compartment**: ${prettyEnum(sl.primary_compartment)}`,
  );
  lines.push("");
  if (sl.dual_localization?.length) {
    lines.push("**Dual localization**");
    lines.push("");
    for (const d of sl.dual_localization) {
      const bits = [
        prettyEnum(d.compartment),
        d.fraction_estimate != null
          ? `~${(d.fraction_estimate * 100).toFixed(0)}%`
          : null,
        d.condition,
      ]
        .filter(Boolean)
        .join(" · ");
      lines.push(`- ${bits}${citeIds(d.cited_evidence_ids)}`);
    }
    lines.push("");
  }
  if (sl.membrane_subdomains?.length) {
    lines.push(
      `**Membrane subdomains**: ${sl.membrane_subdomains.map((s) => prettyEnum(s.subdomain)).join(", ")}`,
    );
    lines.push("");
  }
  if (bc.anatomical_accessibility.length) {
    lines.push("**Anatomical accessibility**");
    lines.push("");
    for (const a of bc.anatomical_accessibility) {
      lines.push(
        `- ${a.context} — ${prettyEnum(a.orientation)} · *${prettyEnum(a.accessibility_implication)}*: ${a.rationale}`,
      );
    }
    lines.push("");
  }
  if (bc.accessibility_modulation.length) {
    lines.push("**Accessibility modulation**");
    lines.push("");
    for (const m of bc.accessibility_modulation) {
      lines.push(
        `- *${prettyEnum(m.category)}*${m.cell_state_trigger ? ` · trigger: ${prettyEnum(m.cell_state_trigger)}` : ""}${m.restricted_lineage ? ` · lineage: ${prettyEnum(m.restricted_lineage)}` : ""}: ${m.baseline_context} → ${m.modulating_state} — ${m.change}${m.accessibility_implication ? ` *(→ ${prettyEnum(m.accessibility_implication)})*` : ""}${citeIds(m.cited_evidence_ids)}`,
      );
    }
    lines.push("");
  }

  // Restricted-subdomain + co-receptor — the viewer renders these under the
  // Biology card (subcellular localization / surface-expression dependency),
  // not the Risks card, so mirror that placement here.
  pushRiskBlock(
    lines,
    "Restricted-subdomain distribution",
    rec.accessibility_risks.restricted_subdomain,
  );
  pushRiskBlock(
    lines,
    "Co-receptor requirements",
    rec.accessibility_risks.co_receptor_requirements,
  );

  // --- Isoforms, orthologs & paralogs (deterministic) ---
  // One combined table mirroring the viewer's IsoformsCard, instead of three
  // separate sections. Rows: canonical → isoforms → mouse/cyno orthologs →
  // paralogs (sorted by ECD %id desc). %identity / ECD %id are vs the human
  // canonical for orthologs + paralogs (isoforms are alternative human forms).
  lines.push("## 5. Isoforms, orthologs & paralogs");
  lines.push("");
  const comparaVer =
    df.orthologs.mouse?.[0]?.compara_version ??
    df.paralogs?.[0]?.compara_version ??
    "—";
  lines.push(
    `*Deterministic · UniProt + DeepTMHMM ${ct.tool_version} · Ensembl ${comparaVer}. %identity / ECD %id are vs the human canonical (orthologs + paralogs only; isoforms are alternative human forms). Per-residue topology + full sequences are in the appendix.*`,
  );
  lines.push("");
  lines.push(
    "| Kind | Variant | UniProt | %identity | ECD %id | TM | ECD len | ICD len | Signal pep | N→C term | Tier |",
  );
  lines.push("|---|---|---|---|---|---|---|---|---|---|---|");
  lines.push(
    `| Isoform | **canonical** | ${g.uniprot_acc} | ref | ref | ${ct.tm_helix_count} | ${aaOrDash(ct.ecd_length_residues)} | ${aaOrDash(ct.icd_length_residues)} | ${aaOrDash(ct.signal_peptide_length)} | ${prettyEnum(ct.n_terminal_orientation)}→${prettyEnum(ct.c_terminal_orientation)} | — |`,
  );
  for (const iso of df.isoform_topologies) {
    lines.push(
      `| Isoform | ${iso.isoform_id} | ${iso.uniprot_acc} | ${fmtPct(iso.full_length_pct_identity_to_canonical)} | ${fmtPct(iso.ecd_pct_identity_to_canonical)} | ${iso.tm_helix_count} | ${aaOrDash(iso.ecd_length_residues)} | ${aaOrDash(iso.icd_length_residues)} | ${aaOrDash(iso.signal_peptide_length)} | ${prettyEnum(iso.n_terminal_orientation)}→${prettyEnum(iso.c_terminal_orientation)} | — |`,
    );
  }
  for (const species of ["mouse", "cynomolgus"]) {
    const label = species === "mouse" ? "Mouse ortholog" : "Cynomolgus ortholog";
    for (const o of df.orthologs[species] ?? []) {
      lines.push(
        `| ${label} | ${o.ortholog_symbol} | [${o.ortholog_uniprot_acc}](https://www.uniprot.org/uniprotkb/${o.ortholog_uniprot_acc}) | ${fmtPct(o.full_length_pct_identity_to_human_canonical)} | ${fmtPct(o.ecd_pct_identity_to_human_canonical)} | ${o.tm_helix_count ?? "—"} | ${aaOrDash(o.ecd_length_residues)} | — | — | — | ${orthologTier(o.ecd_pct_identity_to_human_canonical ?? o.full_length_pct_identity_to_human_canonical)} |`,
      );
    }
  }
  const sortedParalogs = [...df.paralogs].sort(
    (a, b) =>
      (b.ecd_pct_identity ?? b.full_length_pct_identity ?? 0) -
      (a.ecd_pct_identity ?? a.full_length_pct_identity ?? 0),
  );
  for (const p of sortedParalogs) {
    lines.push(
      `| Paralog | ${p.paralog_symbol} | [${p.paralog_uniprot_acc}](https://www.uniprot.org/uniprotkb/${p.paralog_uniprot_acc}) | ${fmtPct(p.full_length_pct_identity)} | ${fmtPct(p.ecd_pct_identity)} | ${p.tm_helix_count ?? "—"} | ${aaOrDash(p.ecd_length_residues)} | ${aaOrDash(p.icd_length_residues)} | ${aaOrDash(p.signal_peptide_length)} | ${p.n_terminal_orientation ? `${prettyEnum(p.n_terminal_orientation)}→${prettyEnum(p.c_terminal_orientation)}` : "—"} | ${paralogTier(p.ecd_pct_identity ?? p.full_length_pct_identity)} |`,
    );
  }
  lines.push("");
  lines.push(
    "**Tier cutoffs.** *Ortholog conservation* (higher = better — cross-species evidence can stand in for human): ≥85% high · 60–85% moderate · <60% low. *Paralog cross-reactivity* (higher = worse — a binder may also engage the paralog): >80% high-risk · 60–80% caution · <60% low-risk ([PMID 30297845](https://pubmed.ncbi.nlm.nih.gov/30297845/)).",
  );
  lines.push("");

  // --- Accessibility risks ---
  const r = rec.accessibility_risks;
  // Order mirrors the viewer's AccessibilityRisksCard. Restricted-subdomain
  // and co-receptor are NOT here — they render under §4 Biological context,
  // exactly as the viewer puts them in the Biology card.
  lines.push("## 6. Accessibility risks");
  lines.push("");
  pushRiskBlock(lines, "Shed form", r.shed_form);
  pushRiskBlock(lines, "Secreted form", r.secreted_form);
  pushRiskBlock(lines, "ECD size assessment", r.ecd_size_assessment);
  pushRiskBlock(lines, "Epitope masking", r.epitope_masking);
  lines.push(
    "**Definitions.** *Shed form* — ectodomain proteolytically released, competing with the surface form for binder occupancy. *Secreted form* — an alternative isoform secreted as free soluble protein (not EV-enclosed). *Epitope masking* — the targetable surface is shielded (partner heterodimerization, glycan shield, or conformational hiding). *ECD size class* — large ≥200 aa · moderate 60–199 · small 30–59 · minimal <30 (one antibody footprint ≈ 12 ± 3 residues, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)).",
  );
  lines.push("");

  // --- Structure summary ---
  const s = df.structure;
  lines.push("## 7. Structure summary");
  lines.push("");
  lines.push(
    `| Field | Value |`,
  );
  lines.push(`|---|---|`);
  lines.push(`| AFDB ID | [${s.afdb_id}](${alphafoldEntryUrl(g.uniprot_acc)}) |`);
  lines.push(`| AFDB version | ${s.afdb_version} |`);
  lines.push(`| ECD mean pLDDT | ${fmtNum(s.ecd_mean_plddt)} |`);
  lines.push(
    `| ECD disordered fraction | ${s.ecd_disordered_fraction == null ? "—" : `${(s.ecd_disordered_fraction * 100).toFixed(1)}%`} |`,
  );
  // ecd_solvent_accessible_fraction was dropped in PR23 round 9.
  lines.push("");
  lines.push(
    `Structure data from [AlphaFold DB](${alphafoldEntryUrl(g.uniprot_acc)}) · ${s.attribution} · licensed [${s.license}](https://creativecommons.org/licenses/by/4.0/)${s.citations.length ? ` · cite ${s.citations.map((c) => `\`${c}\``).join("; ")}` : ""}.`,
  );
  lines.push("");
  lines.push(
    "*pLDDT bands: >90 very high · 70–90 confident · 50–70 low · <50 very low. ECD-restricted metrics average only the extracellular (`O`) residues; disordered fraction = share of ECD residues with pLDDT < 70.*",
  );
  lines.push("");

  // Model variants + experimental structures — mirrors the viewer's
  // structure-viewer tabs (canonical AFDB + isoform / ortholog AFDB models +
  // experimental PDBs). AFDB entry URLs are deterministic from the
  // accession; not every isoform accession has a model (the entry says so).
  lines.push("**Model variants & experimental structures**");
  lines.push("");
  lines.push("| Structure | UniProt / PDB | Source |");
  lines.push("|---|---|---|");
  lines.push(
    `| Canonical | [${g.uniprot_acc}](${alphafoldEntryUrl(g.uniprot_acc)}) | AlphaFold DB (${s.afdb_id}, ${s.afdb_version}) |`,
  );
  for (const iso of df.isoform_topologies) {
    if (iso.uniprot_acc && iso.uniprot_acc !== g.uniprot_acc) {
      lines.push(
        `| Isoform ${iso.isoform_id} | [${iso.uniprot_acc}](${alphafoldEntryUrl(iso.uniprot_acc)}) | AlphaFold DB |`,
      );
    }
  }
  for (const species of ["mouse", "cynomolgus"]) {
    const entries = df.orthologs[species] ?? [];
    const canon = entries.find((o) => o.is_canonical) ?? entries[0];
    if (canon?.ortholog_uniprot_acc) {
      const label = species.charAt(0).toUpperCase() + species.slice(1);
      lines.push(
        `| ${label} ortholog (${canon.ortholog_symbol}) | [${canon.ortholog_uniprot_acc}](${alphafoldEntryUrl(canon.ortholog_uniprot_acc)}) | AlphaFold DB |`,
      );
    }
  }
  // Representative experimental structure — read from the record's
  // deterministic_features.surface_bind.representative_structure (PDBe
  // SIFTS best_structures, highest coverage_fraction / best
  // resolution_angstrom). Its construct sequence + projected topology
  // are embedded in the appendix.
  const repStruct = (df.surface_bind ?? {}).representative_structure;
  if (repStruct?.pdb_id) {
    const meth = [
      repStruct.method,
      repStruct.resolution_angstrom != null ? `${repStruct.resolution_angstrom} Å` : null,
    ]
      .filter(Boolean)
      .join(" ");
    const cov =
      repStruct.residue_start != null && repStruct.residue_end != null
        ? ` · UniProt ${repStruct.residue_start}–${repStruct.residue_end}${repStruct.coverage_fraction != null ? ` (${(repStruct.coverage_fraction * 100).toFixed(0)}% coverage_fraction)` : ""}`
        : "";
    lines.push(
      `| Experimental (best) | [${String(repStruct.pdb_id).toUpperCase()}](https://www.rcsb.org/structure/${repStruct.pdb_id}) chain ${repStruct.chain} | RCSB PDB${meth ? ` · ${meth}` : ""}${cov} |`,
    );
  }
  const sbStruct = df.surface_bind;
  if (sbStruct && Array.isArray(sbStruct.pdbs) && sbStruct.pdbs.length) {
    const shown = sbStruct.pdbs
      .slice(0, 5)
      .map((p) => `[${p}](https://www.rcsb.org/structure/${p})`)
      .join(", ");
    lines.push(
      `| Experimental (${sbStruct.pdbs.length} total) | ${shown}${sbStruct.pdbs.length > 5 ? `, … [all ${sbStruct.pdbs.length} →](https://www.rcsb.org/uniprot/${g.uniprot_acc})` : ""} | RCSB PDB |`,
    );
  }
  lines.push("");

  // --- SURFACE-Bind candidate sites ---
  // Deterministic MaSIF surface-patch scoring on the AlphaFold model.
  // Cite Balbi et al. 2026 (PMID 41604262 == DOI 10.1073/pnas.2506269123,
  // verified same paper) — NOT the record's surface_bind.source string,
  // which mislabels the first author as "Marchand".
  const sb = df.surface_bind;
  lines.push("## 8. SURFACE-Bind candidate sites");
  lines.push("");
  lines.push(
    `*Deterministic · MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · SURFACE-Bind v1, Correia lab (EPFL / Inria / Novo Nordisk)*`,
  );
  lines.push("");
  if (sb && sb.has_data && sb.n_sites > 0) {
    const classBits = [sb.protein_name, sb.main_class, sb.sub_class]
      .filter(Boolean)
      .join(" · ");
    lines.push(
      `${classBits ? `${classBits} · ` : ""}chain ${sb.chain} · ${sb.n_sites} scored site${sb.n_sites === 1 ? "" : "s"} · ${fmtInt(sb.n_seeds_total)} binder seeds (${fmtInt(sb.n_seeds_alpha)} α-helix / ${fmtInt(sb.n_seeds_beta)} β-strand).`,
    );
    lines.push("");
    lines.push(
      `Anchor = patch-center residue; BSA = buried surface area (the contact footprint a binder would form on the patch); seed counts are docked binder backbones split by α-helix / β-strand.`,
    );
    lines.push("");
    lines.push(
      "**Reading the scores.** BSA vs the average antibody–antigen interface ≈ 1103 ± 244 Å² ([PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)): ≥1500 Å² comfortable · 850–1500 workable · <850 thin. Seed pool: ≥1000 comfortable design margin · ≥100 workable · <100 thin/specialized. SURFACE-Bind excludes transmembrane regions but not necessarily intracellular domains — cross-check the anchor residue against the topology string in §5/appendix (`O` = extracellular/antibody-accessible, `I` = intracellular).",
    );
    lines.push("");
    lines.push(
      "| Site | Anchor residue | BSA (Å²) | α-helix seeds | β-strand seeds | Hydrophobicity |",
    );
    lines.push("|---|---|---|---|---|---|");
    for (const site of sb.sites) {
      lines.push(
        `| ${site.site_id} | ${site.anchor_residue} | ${fmtNum(site.area_a2)} | ${fmtInt(site.n_seeds_alpha)} | ${fmtInt(site.n_seeds_beta)} | ${fmtNum(site.hydrophobicity)} |`,
      );
    }
    lines.push("");
    if (Array.isArray(sb.pdbs) && sb.pdbs.length) {
      lines.push(
        `**Experimental structures** — ${sb.pdbs.length} PDB entr${sb.pdbs.length === 1 ? "y" : "ies"} for this protein (browse at [RCSB](https://www.rcsb.org/uniprot/${g.uniprot_acc})).`,
      );
      lines.push("");
    }
  } else if (sb && sb.has_data) {
    lines.push(
      "Scored, but no surface patch cleared the antibody-sized targetability threshold (`n_sites = 0`).",
    );
    lines.push("");
  } else {
    lines.push(
      "No SURFACE-Bind data — typically because the protein has no AlphaFold model (very large proteins).",
    );
    lines.push("");
  }

  // The standalone "Knowledge gaps" section was dropped in PR23
  // round 5 — uncertainty signal now flows through
  // contradicting_evidence + confidence_reasoning + evidence_grade
  // + per-section rationales.

  // --- Evidence ledger ---
  // Schema-tolerant evidence-source extraction.
  // v1.0.0 records: evidence[i].spans[j].source carries pmc_id / pmid / doi / url
  //   (snake_case keys, multiple spans per evidence claim).
  // Legacy: evidence[i].source carries pmcid / pmid / doi / url (single, top-level).
  // Walk every span's source for citation extraction, deduping by pmc_id/pmid.
  function evidenceSources(ev) {
    if (ev.spans && ev.spans.length) {
      return ev.spans
        .map((sp) => sp.source)
        .filter((s) => s != null);
    }
    return ev.source ? [ev.source] : [];
  }
  function pmcIdOf(src) {
    return src?.pmc_id || src?.pmcid || null;
  }

  let primary = 0, secondary = 0, tertiary = 0, pmcOa = 0;
  for (const ev of rec.evidence) {
    if (ev.evidence_tier === "primary") primary += 1;
    else if (ev.evidence_tier === "secondary") secondary += 1;
    else if (ev.evidence_tier === "tertiary") tertiary += 1;
    if (evidenceSources(ev).some((s) => pmcIdOf(s))) pmcOa += 1;
  }
  lines.push("## 9. Evidence ledger");
  lines.push("");
  lines.push(
    `${rec.evidence.length} entries · ${primary} primary · ${secondary} secondary · ${tertiary} tertiary · ${pmcOa} PMC OA.`,
  );
  lines.push("");
  for (const ev of rec.evidence) {
    const sources = evidenceSources(ev);
    const seen = new Set();
    const linkParts = [];
    for (const src of sources) {
      const doi = src.doi;
      const pmid = src.pmid;
      const pmcid = pmcIdOf(src);
      const url = src.url;
      if (doi && !seen.has(`doi:${doi}`)) {
        linkParts.push(`[doi:${doi}](https://doi.org/${doi})`);
        seen.add(`doi:${doi}`);
      }
      if (pmid && !seen.has(`pmid:${pmid}`)) {
        linkParts.push(`[PMID ${pmid}](https://pubmed.ncbi.nlm.nih.gov/${pmid}/)`);
        seen.add(`pmid:${pmid}`);
      }
      if (pmcid && !seen.has(`pmc:${pmcid}`)) {
        linkParts.push(`[${pmcid}](https://www.ncbi.nlm.nih.gov/pmc/articles/${pmcid}/)`);
        seen.add(`pmc:${pmcid}`);
      }
      if (url && !linkParts.length) {
        linkParts.push(url);
      }
    }
    lines.push(
      `- \`${ev.evidence_id}\` · *${prettyEnum(ev.evidence_tier)}*${ev.direction ? ` · ${prettyEnum(ev.direction)}` : ""}${ev.claim_type ? ` · ${prettyEnum(ev.claim_type)}` : ""} — ${ev.claim}${linkParts.length ? ` (${linkParts.join(" · ")})` : ""}`,
    );
    // Assay context — species / cell type / live-vs-fixed / permeabilization,
    // so a reader can tell which claims are human vs. mouse, live vs. fixed.
    const ac = ev.assay_context;
    if (ac) {
      const acBits = [
        ac.species && prettyEnum(ac.species),
        ac.cell_type_or_line,
        ac.fixation,
        ac.permeabilized != null
          ? ac.permeabilized
            ? "permeabilized"
            : "non-permeabilized"
          : null,
      ]
        .filter(Boolean)
        .join(" · ");
      if (acBits) lines.push(`  - *assay*: ${acBits}`);
    }
    // The schema field is `quote` (legacy records used `text`).
    const evQuote = ev.spans?.[0]?.quote ?? ev.spans?.[0]?.text;
    if (evQuote) {
      lines.push(`  > "${evQuote}"`);
    }
  }
  lines.push("");

  // --- Appendix: Downloads & reproduction ---
  lines.push("## Appendix · Downloads & reproduction");
  lines.push("");
  lines.push(
    `This Markdown is generated from the canonical JSON record at \`/data/surfaceome/${g.hgnc_symbol}.json\`. The JSON is the source of truth; this file is the human-readable mirror.`,
  );
  lines.push("");
  lines.push("**Links**");
  lines.push("");
  lines.push(`- Viewer page: [${SITE_BASE}/${g.hgnc_symbol}](${SITE_BASE}/${g.hgnc_symbol})`);
  lines.push(`- Canonical JSON: [${SITE_BASE}/data/surfaceome/${g.hgnc_symbol}.json](${SITE_BASE}/data/surfaceome/${g.hgnc_symbol}.json)`);
  lines.push(`- This Markdown: [${SITE_BASE}/data/surfaceome/${g.hgnc_symbol}.md](${SITE_BASE}/data/surfaceome/${g.hgnc_symbol}.md)`);
  lines.push(`- AlphaFold DB entry: [${alphafoldEntryUrl(g.uniprot_acc)}](${alphafoldEntryUrl(g.uniprot_acc)})`);
  lines.push(`- AFDB prediction API: [${alphafoldApiUrl(g.uniprot_acc)}](${alphafoldApiUrl(g.uniprot_acc)}) (returns current \`pdbUrl\`, \`cifUrl\`, \`uniprotSequence\`, …)`);
  lines.push(`- UniProt: [https://www.uniprot.org/uniprotkb/${g.uniprot_acc}](https://www.uniprot.org/uniprotkb/${g.uniprot_acc})`);
  lines.push("");

  // AlphaFold model downloads — prefer the URLs embedded in the record
  // (structure.model_{cif,pdb,pae}_url), falling back to the live
  // prediction-API response. Absent for no-model proteins (e.g.
  // megalin/LRP2), in which case this block is skipped.
  const cifUrl = s.model_cif_url ?? afdbEntry?.cifUrl;
  const pdbUrl = s.model_pdb_url ?? afdbEntry?.pdbUrl;
  const paeUrl = s.model_pae_url ?? afdbEntry?.paeDocUrl;
  if (cifUrl || pdbUrl) {
    lines.push("**AlphaFold model downloads**");
    lines.push("");
    if (cifUrl) lines.push(`- mmCIF model: [${cifUrl}](${cifUrl})`);
    if (pdbUrl) lines.push(`- PDB model: [${pdbUrl}](${pdbUrl})`);
    if (paeUrl)
      lines.push(
        `- PAE (predicted aligned error) JSON: [${paeUrl}](${paeUrl})`,
      );
    const ver = afdbEntry?.latestVersion ?? afdbEntry?.modelCreatedDate;
    if (ver != null) lines.push(`- AFDB model version: ${ver}`);
    lines.push("");
  }

  // Full canonical sequence (AFDB prediction API, or UniProt FASTA
  // fallback for no-model proteins like megalin).
  const canonicalSequence = sequences[g.uniprot_acc] ?? null;
  lines.push("### Canonical UniProt sequence");
  lines.push("");
  if (canonicalSequence) {
    lines.push(
      `*${canonicalSequence.length} aa · \`${g.uniprot_acc}\` · embedded at build time*`,
    );
    lines.push("");
    lines.push("```");
    lines.push(wrapSequence(canonicalSequence, 60));
    lines.push("```");
  } else {
    lines.push(
      `*Sequence not embedded — fetch from [https://rest.uniprot.org/uniprotkb/${g.uniprot_acc}.fasta](https://rest.uniprot.org/uniprotkb/${g.uniprot_acc}.fasta).*`,
    );
  }
  lines.push("");

  // Alternative-isoform sequences — the JSON record carries isoform
  // topology + ECD/ICD lengths but not the residues, so embed each
  // alternative isoform's full sequence here for isoform-level reanalysis.
  const isoSeqRows = (df.isoform_topologies ?? []).filter(
    (iso) =>
      iso.uniprot_acc &&
      iso.uniprot_acc !== g.uniprot_acc &&
      sequences[iso.uniprot_acc],
  );
  if (isoSeqRows.length) {
    lines.push("### Alternative-isoform sequences");
    lines.push("");
    for (const iso of isoSeqRows) {
      const seq = sequences[iso.uniprot_acc];
      lines.push(
        `**${iso.isoform_id}** (\`${iso.uniprot_acc}\` · ${seq.length} aa)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapSequence(seq, 60));
      lines.push("```");
      lines.push("");
    }
  }

  // Canonical ortholog sequences (mouse, cynomolgus) — the record carries
  // only %identity / %similarity of the ortholog ECD to the human
  // canonical, not the actual residues. Embed the canonical ortholog per
  // species so a reader can re-align cross-species without re-resolving
  // accessions. (Alternative-isoform orthologs are linked in §7.)
  const orthoSeqRows = [];
  for (const sp of ["mouse", "cynomolgus"]) {
    const entries = df.orthologs?.[sp] ?? [];
    const canon = entries.find((o) => o.is_canonical) ?? entries[0];
    if (canon?.ortholog_uniprot_acc && sequences[canon.ortholog_uniprot_acc]) {
      orthoSeqRows.push([sp, canon]);
    }
  }
  if (orthoSeqRows.length) {
    lines.push("### Canonical ortholog sequences");
    lines.push("");
    for (const [sp, o] of orthoSeqRows) {
      const seq = sequences[o.ortholog_uniprot_acc];
      const label = sp.charAt(0).toUpperCase() + sp.slice(1);
      lines.push(
        `**${label} — ${o.ortholog_symbol}** (\`${o.ortholog_uniprot_acc}\` · ${seq.length} aa)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapSequence(seq, 60));
      lines.push("```");
      lines.push("");
    }
  }

  // Close-paralog sequences — >80% ECD identity (the viewer's cutoff). The
  // numeric %identity-only family members (e.g. EGFR's, all <50%) don't
  // qualify, so this is empty for them and populated for tight gene families.
  const paralogSeqRows = (df.paralogs ?? []).filter((p) => {
    const id = p.ecd_pct_identity ?? p.full_length_pct_identity;
    return id != null && id > 80 && sequences[p.paralog_uniprot_acc];
  });
  if (paralogSeqRows.length) {
    lines.push("### Close-paralog sequences");
    lines.push("");
    for (const p of paralogSeqRows) {
      const seq = sequences[p.paralog_uniprot_acc];
      const id = p.ecd_pct_identity ?? p.full_length_pct_identity;
      lines.push(
        `**${p.paralog_symbol}** (\`${p.paralog_uniprot_acc}\` · ${id.toFixed(1)}% ECD identity · ${seq.length} aa)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapSequence(seq, 60));
      lines.push("```");
      lines.push("");
    }
  }

  // Representative experimental-structure sequence — the canonical residues
  // spanned by the best PDB construct (from the record's PDBe SIFTS pointer).
  // Sliced from the canonical sequence over the structure's mapped UniProt
  // range so it aligns 1:1 with the projected topology below.
  const canonSeqForStruct = sequences[g.uniprot_acc] ?? null;
  if (
    repStruct?.pdb_id &&
    canonSeqForStruct &&
    repStruct.residue_start != null &&
    repStruct.residue_end != null
  ) {
    const start = Number(repStruct.residue_start);
    const end = Number(repStruct.residue_end);
    const span = canonSeqForStruct.slice(start - 1, end);
    if (span) {
      const meth = [
        repStruct.method,
        repStruct.resolution_angstrom != null ? `${repStruct.resolution_angstrom} Å` : null,
      ]
        .filter(Boolean)
        .join(", ");
      lines.push("### Experimental-structure sequence");
      lines.push("");
      lines.push(
        `**${String(repStruct.pdb_id).toUpperCase()}** chain ${repStruct.chain}${meth ? ` · ${meth}` : ""} · covers UniProt residues ${start}–${end} (${span.length} aa). Residues sliced from the canonical sequence over the structure's SIFTS-mapped span; unresolved loops in the deposited coordinates are not removed here.`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapSequence(span, 60));
      lines.push("```");
      lines.push("");
    }
  }

  // Per-residue topology, canonical + each isoform
  lines.push("### Per-residue DeepTMHMM topology");
  lines.push("");
  lines.push(
    `*Five-letter alphabet: \`M\` = TM helix, \`O\` = extracellular, \`I\` = intracellular, \`S\` = signal peptide, \`B\` = β-strand. Aligned to the UniProt sequence above (residue indices in the left column).*`,
  );
  lines.push("");
  lines.push(`**canonical** (\`${g.uniprot_acc}\`, ${ct.tool_version})`);
  lines.push("");
  lines.push("```");
  lines.push(wrapTopology(ct.per_residue_topology, 60));
  lines.push("```");
  lines.push("");
  for (const iso of df.isoform_topologies) {
    lines.push(`**${iso.isoform_id}** (\`${iso.uniprot_acc}\`, ${iso.tool_version})`);
    lines.push("");
    lines.push("```");
    lines.push(wrapTopology(iso.per_residue_topology, 60));
    lines.push("```");
    lines.push("");
  }
  // Ortholog topology (canonical mouse/cyno) — projected onto the human
  // canonical, exactly the projection the viewer's TopologyBar renders.
  for (const species of ["mouse", "cynomolgus"]) {
    const entries = df.orthologs[species] ?? [];
    const canon = entries.find((o) => o.is_canonical) ?? entries[0];
    if (canon && canon.per_residue_topology) {
      const label = species.charAt(0).toUpperCase() + species.slice(1);
      lines.push(
        `**${label} ortholog — ${canon.ortholog_symbol}** (\`${canon.ortholog_uniprot_acc}\`, projected onto human canonical)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapTopology(canon.per_residue_topology, 60));
      lines.push("```");
      lines.push("");
    }
  }
  // Close-paralog topology — mirrors the viewer's >80%-ECD-identity cutoff
  // (no close paralogs ⟹ nothing renders, e.g. EGFR).
  for (const p of df.paralogs) {
    const id = p.ecd_pct_identity ?? p.full_length_pct_identity;
    if (id != null && id > 80 && p.per_residue_topology) {
      lines.push(
        `**Paralog — ${p.paralog_symbol}** (\`${p.paralog_uniprot_acc}\`, ${id.toFixed(1)}% ECD identity)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapTopology(p.per_residue_topology, 60));
      lines.push("```");
      lines.push("");
    }
  }
  // Representative experimental-structure topology — canonical DeepTMHMM
  // projected onto the best PDB's SIFTS-mapped UniProt span (same residues as
  // the experimental sequence above).
  if (
    repStruct?.pdb_id &&
    ct.per_residue_topology &&
    repStruct.residue_start != null &&
    repStruct.residue_end != null
  ) {
    const start = Number(repStruct.residue_start);
    const end = Number(repStruct.residue_end);
    const topoSpan = ct.per_residue_topology.slice(start - 1, end);
    if (topoSpan) {
      lines.push(
        `**Experimental — ${String(repStruct.pdb_id).toUpperCase()} chain ${repStruct.chain}** (UniProt residues ${start}–${end}, projected from canonical)`,
      );
      lines.push("");
      lines.push("```");
      lines.push(wrapTopology(topoSpan, 60));
      lines.push("```");
      lines.push("");
    }
  }
  if (structureData?.topology && structureData.topology !== ct.per_residue_topology) {
    lines.push(
      `**Build-pipeline DeepTMHMM JSON** (\`/structure-viewer/${g.uniprot_acc}.json\`)`,
    );
    lines.push("");
    lines.push("```");
    lines.push(wrapTopology(structureData.topology, 60));
    lines.push("```");
    lines.push("");
  }

  // --- Data sources footer ---
  lines.push("### Data sources");
  lines.push("");
  const comparaVersion = df.orthologs.mouse[0]?.compara_version ?? df.paralogs[0]?.compara_version ?? "—";
  lines.push(`- AlphaFold DB structures — ${s.license} (${s.attribution})`);
  lines.push(`- DeepTMHMM topology — ${ct.tool_version} · DTU Health Tech (Hallgren et al. 2022)`);
  lines.push(`- Ensembl Compara orthologs & paralogs — ${comparaVersion} · open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)`);
  lines.push(
    `- SURFACE-Bind binding-site scoring — MaSIF-based surface patch scoring on the AlphaFold model (Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/), PNAS) · [surface-bind.inria.fr](https://surface-bind.inria.fr/)`,
  );
  lines.push(`- UniProt — CC BY 4.0 (UniProt Consortium)`);
  lines.push("");
  // confidence: legacy schema = float 0-1; v1.0.0 = enum string ("low" /
  // "moderate" / "high" / "strong"). Render whichever shape is present.
  const confidenceStr =
    typeof rec.confidence === "number"
      ? rec.confidence.toFixed(2)
      : String(rec.confidence ?? "—");
  lines.push(
    `*Confidence ${confidenceStr} — ${rec.confidence_reasoning ?? ""}*`,
  );
  lines.push("");

  return lines.join("\n");
}

// --------------------------------------------------------------
// Driver
// --------------------------------------------------------------

// --------------------------------------------------------------
// Record sources. Both yield [{ name, rec }] with name = "{SYMBOL}.json";
// the render loop below is source-agnostic.
// --------------------------------------------------------------

async function fetchJson(url) {
  const resp = await fetch(url, {
    headers: {
      "User-Agent":
        "accessible-surfaceome-viewer/1.0 (build-markdown-exports.mjs)",
    },
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${url}`);
  return resp.json();
}

function loadRecordsFromSnapshots() {
  const jsonFiles = readdirSync(DATA_DIR).filter((n) => n.endsWith(".json"));
  return jsonFiles.map((name) => ({
    name,
    rec: JSON.parse(readFileSync(path.join(DATA_DIR, name), "utf-8")),
  }));
}

// Fetch EVERY published record from the public Worker (the D1-served
// model). Returns them in memory; main() materializes each {SYMBOL}.json
// next to its {SYMBOL}.md so the static build + fs-fallback resolve.
async function loadRecordsFromApi() {
  const listUrl = `${API_BASE}/v1/genes`;
  const list = await fetchJson(listUrl);
  let genes = list?.genes ?? [];
  const limit = parseInt(process.env.SURFACEOME_MD_LIMIT || "0", 10);
  if (limit > 0) genes = genes.slice(0, limit);
  console.log(
    `  api: ${genes.length} published genes from ${listUrl}` +
      (limit > 0 ? ` (limited to ${limit})` : ""),
  );
  const out = [];
  for (const g of genes) {
    const sym = g.gene_symbol;
    if (!sym) continue;
    try {
      const rec = await fetchJson(
        `${API_BASE}/v1/genes/${encodeURIComponent(sym)}`,
      );
      if (rec) out.push({ name: `${rec.gene?.hgnc_symbol ?? sym}.json`, rec });
    } catch (err) {
      console.warn(`  ! ${sym}: record fetch failed — ${err.message}`);
    }
  }
  return out;
}

async function main() {
  if (!existsSync(DATA_DIR)) {
    console.error(`No data dir at ${DATA_DIR}`);
    process.exit(1);
  }
  // Offline/CI: api mode with no reachable Worker skips entirely — never
  // falls back to the committed JSONs (this is the D1-only contract).
  if (MD_SOURCE === "api" && (!API_BASE || API_BASE === "local")) {
    console.warn(
      "[md-exports] SURFACEOME_API_BASE=local/empty in api mode — skipping " +
        "(offline build; no committed-JSON fallback).",
    );
    return;
  }
  const records =
    MD_SOURCE === "api"
      ? await loadRecordsFromApi()
      : loadRecordsFromSnapshots();
  if (records.length === 0) {
    console.warn(`No records to export (source=${MD_SOURCE}).`);
    return;
  }
  console.log(`Exporting ${records.length} records (source=${MD_SOURCE}).`);
  for (const { name, rec } of records) {
    // Accept schema v1.x and v2.x. Pinning this to an exact "1.0.0"
    // silently skipped every record once the schema bumped to 1.1.0 —
    // which is what blanked the .md downloads (no file written → 404).
    // Gate on known-compatible MAJOR versions so minor bumps can't
    // re-break it while a true future breaking change still skips loudly.
    const schemaMajor = String(rec.schema_version ?? "").split(".")[0];
    if (!["1", "2"].includes(schemaMajor)) {
      console.warn(
        `  ! ${name}: schema_version=${rec.schema_version}, skipping (only schema v1.x/v2.x supported)`,
      );
      continue;
    }
    // api mode: materialize the JSON snapshot next to the .md so
    // /data/surfaceome/{SYMBOL}.json resolves in the static build and the
    // viewer fs-fallback works. In snapshots mode it is already on disk.
    if (MD_SOURCE === "api") {
      writeFileSync(
        path.join(DATA_DIR, name),
        JSON.stringify(rec, null, 2) + "\n",
        "utf-8",
      );
    }
    const uniprot = rec.gene?.uniprot_acc;
    const structurePath = uniprot
      ? path.join(STRUCTURE_DIR, `${uniprot}.json`)
      : null;
    const structureData =
      structurePath && existsSync(structurePath)
        ? JSON.parse(readFileSync(structurePath, "utf-8"))
        : null;
    // Gather every UniProt acc we want a sequence for: canonical + human
    // isoforms + the canonical ortholog per species. Cross-species and
    // isoform sequences aren't in the JSON record (only %identity /
    // topology is), so embedding them makes the .md a self-contained
    // reanalysis bundle. fetchSequence caches per acc, so duplicates are
    // free.
    const dfx = rec.deterministic_features ?? {};
    const seqAccs = [];
    if (uniprot) seqAccs.push(uniprot);
    for (const iso of dfx.isoform_topologies ?? []) {
      if (iso.uniprot_acc && iso.uniprot_acc !== uniprot)
        seqAccs.push(iso.uniprot_acc);
    }
    for (const sp of ["mouse", "cynomolgus"]) {
      const entries = dfx.orthologs?.[sp] ?? [];
      const canon = entries.find((o) => o.is_canonical) ?? entries[0];
      if (canon?.ortholog_uniprot_acc) seqAccs.push(canon.ortholog_uniprot_acc);
    }
    // Close paralogs (>80% ECD identity — the viewer's cutoff).
    for (const p of dfx.paralogs ?? []) {
      const id = p.ecd_pct_identity ?? p.full_length_pct_identity;
      if (id != null && id > 80 && p.paralog_uniprot_acc) {
        seqAccs.push(p.paralog_uniprot_acc);
      }
    }
    const uniqAccs = [...new Set(seqAccs)];
    // Prefer sequences embedded in the record (deterministic_features now
    // carries them); only fetch the accessions the record doesn't cover.
    const sequences = {};
    const recSeqs = collectRecordSequences(dfx);
    for (const acc of uniqAccs) {
      if (recSeqs[acc]) sequences[acc] = recSeqs[acc];
    }
    const toFetch = uniqAccs.filter((acc) => !sequences[acc]);
    process.stdout.write(
      `→ ${name}: ${uniqAccs.length - toFetch.length}/${uniqAccs.length} seq from record, fetching ${toFetch.length}… `,
    );
    for (const acc of toFetch) sequences[acc] = await fetchSequence(acc);
    const canonSeq = uniprot ? sequences[uniprot] : null;
    process.stdout.write(
      canonSeq ? `canonical ${canonSeq.length} aa\n` : "(no canonical seq)\n",
    );
    const afdbEntry = uniprot ? await fetchAfdbEntry(uniprot) : null;
    const outPath = path.join(DATA_DIR, name.replace(/\.json$/, ".md"));
    writeFileSync(
      outPath,
      md(rec, structureData, sequences, afdbEntry),
      "utf-8",
    );
    console.log(`  wrote ${path.relative(VIEWER_ROOT, outPath)}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
