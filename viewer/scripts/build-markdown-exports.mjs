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
  lines.push(e.one_paragraph);
  lines.push("");

  // --- Filters ---
  const f = rec.filters;
  lines.push("## 2. Filters / catalog facets");
  lines.push("");
  lines.push("| Group | Facets |");
  lines.push("|---|---|");
  lines.push(
    `| Accessibility | overall=${prettyEnum(f.surface_accessibility)} · conf=${prettyEnum(f.confidence)} · subcategory=${prettyEnum(f.subcategory)} · grade=${prettyEnum(f.evidence_grade)} · ecd=${prettyEnum(f.ecd_accessibility_class)} · density=${prettyEnum(f.evidence_density)} |`,
  );
  lines.push(
    `| Expression | level=${prettyEnum(f.expression_level)} · breadth=${prettyEnum(f.expression_breadth)} · specificity=${prettyEnum(f.surface_specificity)} |`,
  );
  lines.push(
    `| Risks | shed=${f.has_shed_form} · secreted=${f.has_secreted_form} · coreceptor=${f.requires_coreceptor_for_expression} · masking=${f.has_epitope_masking} · subdomain=${f.has_restricted_subdomain} |`,
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

  // --- Surface evidence ---
  const se = rec.surface_evidence;
  lines.push("## 3. Surface evidence");
  lines.push("");
  lines.push(`**Evidence grade** · ${prettyEnum(se.evidence_grade)}`);
  lines.push("");
  lines.push(`${se.grade_rationale}`);
  lines.push("");
  for (const m of se.methods) {
    lines.push(
      `### ${prettyEnum(m.method_subclass)} — ${prettyEnum(m.accessibility_relevance)}`,
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
          `- ${ab.name}${meta ? ` (${meta})` : ""} — ${prettyEnum(ab.antibody_epitope_region)} epitope; ${prettyEnum(ab.validation_strength)} validation${ab.cross_reactivity_notes ? `; ${ab.cross_reactivity_notes}` : ""}`,
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
  if (bc.tissues.length) {
    lines.push("**Tissues × disease context**");
    lines.push("");
    lines.push("| Tissue | Disease context | Level (protein) | Cell types | Cell states |");
    lines.push("|---|---|---|---|---|");
    for (const t of bc.tissues) {
      lines.push(
        `| ${t.tissue} | ${prettyEnum(t.disease_context)} | ${prettyEnum(t.present)} | ${t.cell_types.join(", ") || "—"} | ${t.cell_states.join(", ") || "—"} |`,
      );
    }
    lines.push("");
  }
  lines.push(`**Primary subcellular compartment**: ${prettyEnum(bc.subcellular_localization.primary_compartment)}`);
  lines.push("");
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
        `- *${prettyEnum(m.category)}*${m.cell_state_trigger ? ` · trigger: ${prettyEnum(m.cell_state_trigger)}` : ""}${m.restricted_lineage ? ` · lineage: ${prettyEnum(m.restricted_lineage)}` : ""}: ${m.baseline_context} → ${m.modulating_state} — ${m.change}`,
      );
    }
    lines.push("");
  }

  // --- Isoforms (deterministic) ---
  lines.push("## 5. Isoforms");
  lines.push("");
  lines.push(
    `*Deterministic · UniProt + DeepTMHMM ${ct.tool_version}*`,
  );
  lines.push("");
  lines.push("| Isoform | UniProt | TM | N-term | Signal pep | ECD len | ICD len |");
  lines.push("|---|---|---|---|---|---|---|");
  lines.push(
    `| **canonical** | ${g.uniprot_acc} | ${ct.tm_helix_count} | ${prettyEnum(ct.n_terminal_orientation)} | ${ct.signal_peptide_length} aa | ${ct.ecd_length_residues} aa | ${ct.icd_length_residues} aa |`,
  );
  for (const iso of df.isoform_topologies) {
    lines.push(
      `| ${iso.isoform_id} | ${iso.uniprot_acc} | ${iso.tm_helix_count} | ${prettyEnum(iso.n_terminal_orientation)} | ${iso.signal_peptide_length} aa | ${iso.ecd_length_residues} aa | ${iso.icd_length_residues} aa |`,
    );
  }
  lines.push("");

  // --- Paralogs ---
  lines.push("## 6. Paralogs");
  lines.push("");
  if (df.paralogs.length) {
    lines.push(`*Compara ${df.paralogs[0].compara_version}*`);
    lines.push("");
    lines.push("| Paralog | UniProt | ECD %id | Family |");
    lines.push("|---|---|---|---|");
    for (const p of df.paralogs) {
      lines.push(
        `| ${p.paralog_symbol} | [${p.paralog_uniprot_acc}](https://www.uniprot.org/uniprotkb/${p.paralog_uniprot_acc}) | ${fmtPct(p.ecd_pct_identity)} | ${p.family_id} |`,
      );
    }
    lines.push("");
  }
  // PR23 round 10 dropped the LLM paralog cross-reactivity verdict.
  // Per-antibody cross-reactivity behavior is captured in §3
  // `AntibodyRef.cross_reactivity_notes`; the gene-family prior is
  // captured by `filters.max_paralog_ecd_pct_identity`.
  lines.push(
    `*Per-antibody cross-reactivity behavior is captured per-clone under §3 (Surface evidence → antibodies). The LLM cross-reactivity verdict is deferred to v1.x.*`,
  );
  lines.push("");

  // --- Orthologs ---
  lines.push("## 7. Orthologs");
  lines.push("");
  for (const species of ["mouse", "cynomolgus"]) {
    const entries = df.orthologs[species];
    if (!entries.length) continue;
    lines.push(`**${species.charAt(0).toUpperCase() + species.slice(1)}**`);
    lines.push("");
    lines.push("| Canonical | Isoform | Symbol | UniProt | Type | Full-length %id | ECD %id | ECD %sim | ECD len | TM |");
    lines.push("|---|---|---|---|---|---|---|---|---|---|");
    for (const o of entries) {
      lines.push(
        `| ${o.is_canonical ? "✓" : "alt"} | ${o.isoform_id} | ${o.ortholog_symbol} | [${o.ortholog_uniprot_acc}](https://www.uniprot.org/uniprotkb/${o.ortholog_uniprot_acc}) | ${prettyEnum(o.type)} | ${fmtPct(o.full_length_pct_identity_to_human_canonical)} | ${fmtPct(o.ecd_pct_identity_to_human_canonical)} | ${fmtPct(o.ecd_pct_similarity_to_human_canonical)} | ${o.ecd_length_residues} aa | ${o.tm_helix_count} |`,
      );
    }
    lines.push("");
  }

  // --- Accessibility risks ---
  const r = rec.accessibility_risks;
  lines.push("## 8. Accessibility risks");
  lines.push("");
  const riskBlocks = [
    ["Shed form", r.shed_form, ["mechanism", "sheddase_if_known"]],
    ["Secreted form", r.secreted_form, ["source", "ratio_to_membrane"]],
    ["Restricted subdomain", r.restricted_subdomain, ["domain", "rationale"]],
    ["Co-receptor requirements", r.co_receptor_requirements, ["surface_expression_dependency", "evidence_basis", "partners", "rationale"]],
    ["ECD size assessment", r.ecd_size_assessment, ["ecd_accessibility_class", "rationale"]],
    ["Epitope masking", r.epitope_masking, ["mechanism", "rationale"]],
  ];
  for (const [title, block] of riskBlocks) {
    lines.push(`**${title}**`);
    lines.push("");
    if ("present" in block) lines.push(`- present: ${block.present}`);
    if ("severity" in block) lines.push(`- severity: ${prettyEnum(block.severity)}`);
    if ("evidence_strength" in block) lines.push(`- evidence: ${prettyEnum(block.evidence_strength)}`);
    if ("mechanism" in block && block.mechanism != null) {
      // epitope_masking.mechanism is a list (PR23 round 6); other
      // blocks have a scalar mechanism. Render either as a comma
      // list of pretty enum values.
      const mech = Array.isArray(block.mechanism)
        ? block.mechanism.map(prettyEnum).join(", ")
        : prettyEnum(block.mechanism);
      lines.push(`- mechanism: ${mech}`);
    }
    if ("sheddase_if_known" in block && block.sheddase_if_known) lines.push(`- sheddase: ${block.sheddase_if_known}`);
    if ("source" in block && block.source) lines.push(`- source: ${prettyEnum(block.source)}`);
    if ("ratio_to_membrane" in block && block.ratio_to_membrane != null) lines.push(`- ratio to membrane: ${block.ratio_to_membrane}`);
    if ("domain" in block) lines.push(`- domain: ${prettyEnum(block.domain)}`);
    if ("surface_expression_dependency" in block) lines.push(`- dependency: ${prettyEnum(block.surface_expression_dependency)}`);
    if ("evidence_basis" in block) lines.push(`- evidence basis: ${prettyEnum(block.evidence_basis)}`);
    if ("partners" in block && block.partners?.length) lines.push(`- partners: ${block.partners.join(", ")}`);
    if ("ecd_accessibility_class" in block) lines.push(`- ECD class: ${prettyEnum(block.ecd_accessibility_class)}`);
    if ("rationale" in block && block.rationale) lines.push(`- rationale: ${block.rationale}`);
    lines.push("");
  }

  // --- Structure summary ---
  const s = df.structure;
  lines.push("## 9. Structure summary");
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
  lines.push("## 10. Evidence ledger");
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
      `- \`${ev.evidence_id}\` · *${prettyEnum(ev.evidence_tier)}* — ${ev.claim}${linkParts.length ? ` (${linkParts.join(" · ")})` : ""}`,
    );
    if (ev.spans?.[0]?.text) {
      lines.push(`  > "${ev.spans[0].text}"`);
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

  // AlphaFold model downloads — pulled from the same prediction-API
  // response the canonical sequence came from. Absent for no-model
  // proteins (e.g. megalin/LRP2), in which case this block is skipped.
  if (afdbEntry && (afdbEntry.cifUrl || afdbEntry.pdbUrl)) {
    lines.push("**AlphaFold model downloads**");
    lines.push("");
    if (afdbEntry.cifUrl)
      lines.push(`- mmCIF model: [${afdbEntry.cifUrl}](${afdbEntry.cifUrl})`);
    if (afdbEntry.pdbUrl)
      lines.push(`- PDB model: [${afdbEntry.pdbUrl}](${afdbEntry.pdbUrl})`);
    if (afdbEntry.paeDocUrl)
      lines.push(
        `- PAE (predicted aligned error) JSON: [${afdbEntry.paeDocUrl}](${afdbEntry.paeDocUrl})`,
      );
    const ver = afdbEntry.latestVersion ?? afdbEntry.modelCreatedDate;
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

async function main() {
  if (!existsSync(DATA_DIR)) {
    console.error(`No data dir at ${DATA_DIR}`);
    process.exit(1);
  }
  const jsonFiles = readdirSync(DATA_DIR).filter((n) => n.endsWith(".json"));
  if (jsonFiles.length === 0) {
    console.warn("No JSON records found under", DATA_DIR);
    return;
  }
  for (const name of jsonFiles) {
    const recordPath = path.join(DATA_DIR, name);
    const rec = JSON.parse(readFileSync(recordPath, "utf-8"));
    // Accept any schema v1.x. Pinning this to an exact "1.0.0" silently
    // skipped every record once the schema bumped to 1.1.0 — which is
    // what blanked the .md downloads (no file written → 404). Gate on the
    // MAJOR version only, so a future 1.2.0 minor bump can't re-break it;
    // a true breaking change (2.x) still skips loudly.
    const schemaMajor = String(rec.schema_version ?? "").split(".")[0];
    if (schemaMajor !== "1") {
      console.warn(
        `  ! ${name}: schema_version=${rec.schema_version}, skipping (only schema v1.x supported)`,
      );
      continue;
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
    const uniqAccs = [...new Set(seqAccs)];
    process.stdout.write(`→ ${name}: fetching ${uniqAccs.length} sequence(s)… `);
    const sequences = {};
    for (const acc of uniqAccs) sequences[acc] = await fetchSequence(acc);
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
