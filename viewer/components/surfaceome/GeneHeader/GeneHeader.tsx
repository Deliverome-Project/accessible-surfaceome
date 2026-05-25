import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import type { StructureViewerData } from "../../../lib/structure-viewer-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { StatusPill } from "../StatusPill/StatusPill";
import { TopologyLegend } from "../IsoformsCard/TopologyBar";
import { StructureViewer } from "../StructureViewerCard/StructureViewer";
import styles from "./GeneHeader.module.css";

function presentTopologyStates(topology: string): string[] {
  if (!topology) return [];
  const seen = new Set<string>();
  for (const ch of topology) seen.add(ch);
  return ["M", "O", "I", "S", "B"].filter((s) => seen.has(s));
}

interface GeneHeaderProps {
  rec: SurfaceomeRecord;
  /** Descriptive gene name + synonyms from NCBI gene_info. The record
   *  itself doesn't carry the field; the page loads it server-side via
   *  ``loadGeneName(symbol)`` and passes it down. ``null`` when no
   *  entry exists for the symbol. */
  geneName?: { name: string; synonyms: string[] } | null;
  /** DeepTMHMM topology data for the canonical UniProt. Loaded
   *  server-side via ``loadStructureViewerData(uniprot_acc)``;
   *  ``null`` when no JSON exists for the UniProt — header
   *  collapses back to single-column. Membrane-anchored cytoplasmic
   *  proteins (DeepTMHMM type GLOB, e.g. SRC, myristoyl-anchored)
   *  CAN still have a JSON when emitted via the build script's
   *  ``--include-globular`` flag; the viewer paints them uniformly
   *  intracellular and the caption is adjusted to describe the
   *  membrane-anchoring rather than a transmembrane orientation. */
  structureData?: StructureViewerData | null;
}

function tierCounts(rec: SurfaceomeRecord) {
  let primary = 0;
  let secondary = 0;
  let tertiary = 0;
  for (const e of rec.evidence) {
    if (e.evidence_tier === "primary") primary += 1;
    else if (e.evidence_tier === "secondary") secondary += 1;
    else if (e.evidence_tier === "tertiary") tertiary += 1;
  }
  return { primary, secondary, tertiary, total: rec.evidence.length };
}

function accessibilityTone(value: string) {
  if (value === "high") return "success" as const;
  if (value === "moderate") return "teal" as const;
  if (value === "low") return "amber" as const;
  // `"no"` = confident negative call. Distinct from `"uncertain"`
  // (no signal); render in danger / red so the reader can scan for
  // it on the catalog.
  if (value === "no") return "danger" as const;
  return "neutral" as const;
}

function gradeTone(value: string) {
  if (value === "direct_multi_method") return "success" as const;
  if (value === "direct_single_method") return "teal" as const;
  if (value === "supportive_but_indirect") return "amber" as const;
  if (value === "conflicting") return "danger" as const;
  return "neutral" as const;
}

function triageTone(signal: string) {
  if (signal === "likely_accessible") return "success" as const;
  if (signal === "possibly_accessible") return "teal" as const;
  if (signal === "unlikely") return "amber" as const;
  return "neutral" as const;
}

function confidenceTone(value: string) {
  if (value === "high") return "success" as const;
  if (value === "moderate") return "lavender" as const;
  if (value === "low") return "amber" as const;
  return "neutral" as const;
}

function plddtTone(plddt: number) {
  if (plddt >= 90) return "success" as const;
  if (plddt >= 70) return "teal" as const;
  if (plddt >= 50) return "amber" as const;
  return "danger" as const;
}

/** Map a StatusPill tone enum to the `.h-vital-display` tone modifier
 *  class. Keeps the editorial display value tinted in the same hue as
 *  the supporting pill underneath. Returns empty string for `neutral`
 *  so the display value falls back to `var(--ink)`. */
function vitalToneClass(
  tone: "success" | "teal" | "lavender" | "amber" | "danger" | "neutral",
): string {
  if (tone === "neutral") return "";
  return `tone-${tone}`;
}

/**
 * GeneHeader — display-scale gene symbol, executive lede, identifier
 * links, and four vitals. Driven entirely by `executive_summary` +
 * derived counts from the evidence ledger; no v0.x targetability /
 * surface_biology fields.
 */
export function GeneHeader({ rec, geneName, structureData }: GeneHeaderProps) {
  const g = rec.gene;
  const exec = rec.executive_summary;
  const counts = tierCounts(rec);
  const struct = rec.deterministic_features.structure;
  // The fetcher signals what kind of pLDDT the number is via the
  // ``source`` string (see :func:`tools.afdb_plddt.fetch_afdb_plddt`).
  //   * "placeholder" — fetcher hasn't run, the 0.0 isn't a measurement.
  //   * "whole-protein" — protein has no extracellular residues (GLOB
  //     proteins like SRC); the fetcher reused the global metric so the
  //     schema field stays populated. Honest display: label "Whole pLDDT"
  //     so the reader doesn't think it's ECD-restricted, and omit the
  //     disordered fraction (the global frac-low + frac-very-low isn't
  //     comparable to the ECD-restricted threshold-based number on
  //     proper ECD proteins).
  //   * "ECD-restricted" — real ECD-restricted pLDDT computed from the
  //     CIF; label "ECD pLDDT" as the schema field intends.
  const structSource = struct.source.toLowerCase();
  const structPlaceholder = structSource.includes("placeholder");
  const structWholeProtein =
    !structPlaceholder && structSource.includes("whole-protein");
  const plddtLabel = structWholeProtein ? "Whole pLDDT" : "ECD pLDDT";
  const ids = [
    {
      label: "HGNC",
      value: g.hgnc_id,
      href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${g.hgnc_id}`,
    },
    {
      label: "UniProt",
      value: g.uniprot_acc,
      href: `https://www.uniprot.org/uniprotkb/${g.uniprot_acc}`,
    },
    {
      label: "NCBI Gene",
      value: String(g.ncbi_gene_id),
      href: `https://www.ncbi.nlm.nih.gov/gene/${g.ncbi_gene_id}`,
    },
    {
      label: "Ensembl",
      value: g.ensembl_gene,
      href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${g.ensembl_gene}`,
    },
  ];

  return (
    <header className={styles.header}>
      <div className={styles.headerGrid}>
        <div className={styles.headerText}>
          <h1 className={`h-gene ${styles.symbol}`}>{g.hgnc_symbol}</h1>
          {geneName?.name ? (
            <p className={styles.geneName}>
              {geneName.name}
              {geneName.synonyms.length > 0 ? (
                <span className={styles.geneSynonyms}>
                  {" · also known as "}
                  {geneName.synonyms.join(", ")}
                </span>
              ) : null}
            </p>
          ) : null}

          {/* Executive summary inlined here (no longer a separate
              section). Reader sees the gene name, then immediately the
              one-paragraph synthesis + headline risks + cited evidence
              chips. The structured signals (Accessibility, Grade,
              Confidence, Triage) live in the vitals row below. */}
          <p className={styles.execLede}>{exec.one_paragraph}</p>

          {exec.headline_risks.length > 0 ? (
            <p className={styles.risks}>
              <span className={`label-mono ${styles.risksLabel}`}>
                Headline risks
              </span>
              <span className={styles.risksValue}>
                {exec.headline_risks.map((r) => prettyEnum(r)).join(" · ")}
              </span>
            </p>
          ) : null}

          {exec.cited_evidence_ids.length > 0 ? (
            <EvidenceChipList
              ids={exec.cited_evidence_ids}
              label="Cited evidence"
            />
          ) : null}

          <ul className={styles.ids} aria-label="External identifiers">
            {ids.map((id) => (
              <li key={id.label} className={styles.idItem}>
                <a
                  className={styles.idLink}
                  href={id.href}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className={`label-mono ${styles.idLabel}`}>{id.label}</span>
                  <span className={styles.idValue}>{id.value}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>

        {structureData ? (
          <aside className={styles.structureSlot} aria-label="3D structure">
            <StructureViewer data={structureData} geneSymbol={g.hgnc_symbol} />
            <TopologyLegend
              presentStates={presentTopologyStates(structureData.topology)}
            />
            {/* AFDB structure stats — moved up from the §9
                StructureSummaryCard so the reader sees the pLDDT
                confidence next to the model it qualifies. The `struct`
                block is the canonical
                ``deterministic_features.structure``. */}
            <dl className={styles.structureStats} aria-label="AFDB structure stats">
              <div className={styles.structureStat}>
                <dt
                  className={`label-mono ${styles.structureStatK}`}
                  title={
                    structWholeProtein
                      ? "Whole-protein pLDDT — this gene has no extracellular residues per DeepTMHMM (GLOB / cytoplasmic), so the AFDB metric describes the entire model rather than an ECD subset."
                      : "Mean per-residue AlphaFold pLDDT across extracellular-domain residues (DeepTMHMM 'O' positions)."
                  }
                >
                  {plddtLabel}
                </dt>
                <dd className={styles.structureStatV}>
                  {structPlaceholder ? (
                    <StatusPill tone="neutral" size="sm">
                      pending
                    </StatusPill>
                  ) : (
                    <StatusPill tone={plddtTone(struct.ecd_mean_plddt)} size="sm">
                      {struct.ecd_mean_plddt.toFixed(1)}
                    </StatusPill>
                  )}
                </dd>
              </div>
              {/* Disordered fraction is meaningful only when computed
                  over ECD residues against the pLDDT<70 threshold. For
                  whole-protein fallback the JSON's value is global
                  frac_low + frac_very_low, which mixes thresholds —
                  hide rather than mislabel. */}
              {!structWholeProtein ? (
                <div className={styles.structureStat}>
                  <dt
                    className={`label-mono ${styles.structureStatK}`}
                    title="Fraction of ECD residues with pLDDT < 70 (AFDB low-confidence threshold). High fraction → flexible / disordered ECD, often correlates with epitope-masking risk."
                  >
                    Disordered
                  </dt>
                  <dd className={styles.structureStatV}>
                    <span className={styles.structureStatNum}>
                      {structPlaceholder
                        ? "—"
                        : `${(struct.ecd_disordered_fraction * 100).toFixed(0)}%`}
                    </span>
                  </dd>
                </div>
              ) : null}
              <div className={styles.structureStat}>
                <dt className={`label-mono ${styles.structureStatK}`}>AFDB</dt>
                <dd className={styles.structureStatV}>
                  {/* AFDB's /entry/ route resolves either form, but the
                      bare UniProt acc redirects through a search page
                      first. The full entry-id (AF-{acc}-F1) lands
                      directly on the model page — one fewer click. */}
                  <a
                    href={`https://alphafold.ebi.ac.uk/entry/${struct.afdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.structureStatLink}
                  >
                    {struct.afdb_id} · {struct.afdb_version}
                  </a>
                </dd>
              </div>
            </dl>
            <p className={styles.structureCaption}>
              {structureData.deeptmhmm_type === "GLOB" ? (
                <>
                  Soluble cytoplasmic (DeepTMHMM ={" "}
                  <span style={{ fontFamily: "var(--font-mono)" }}>GLOB</span>)
                  · membrane-association via lipid anchor / interaction, not a
                  TM helix
                </>
              ) : (
                <>DeepTMHMM topology · membrane horizontal, extracellular up</>
              )}
            </p>
          </aside>
        ) : null}
      </div>

      {/* Vitals — eyebrow label, italic-Playfair display value
          (`.h-vital-display`), then a small outlined StatusPill that
          carries the tonal cue. The display value carries the enum
          headline; the sub-line carries the supplemental detail
          (subcategory, evidence counts, triage risks). The pill stays
          so colorblind / scanning readers still get the tone cue and
          the tone modifier on the display value matches it. */}
      <dl className={styles.vitals}>
        {(() => {
          const accessTone = accessibilityTone(exec.surface_accessibility);
          const gradeT = gradeTone(exec.evidence_grade_summary);
          const confT = confidenceTone(exec.confidence);
          const triT = triageTone(rec.triage_signal);
          return (
            <>
              <div className={styles.vital}>
                <dt className={`label-mono ${styles.vitalK}`}>Accessibility</dt>
                <dd className={styles.vitalV}>
                  <p className={`h-vital-display ${vitalToneClass(accessTone)}`}>
                    {prettyEnum(exec.surface_accessibility)}
                  </p>
                  <StatusPill tone={accessTone} size="sm">
                    {prettyEnum(exec.subcategory)}
                  </StatusPill>
                </dd>
              </div>

              <div className={styles.vital}>
                <dt
                  className={`label-mono ${styles.vitalK}`}
                  title={
                    "Reader-facing relabel of `evidence_grade_summary` — " +
                    "rolls up A1's per-method `MethodObservation` blocks into " +
                    "one tier (direct_multi_method / direct_single_method / " +
                    "supportive_but_indirect / conflicting / weak)."
                  }
                >
                  Experimental surface evidence
                </dt>
                <dd className={styles.vitalV}>
                  <p className={`h-vital-display ${vitalToneClass(gradeT)}`}>
                    {prettyEnum(exec.evidence_grade_summary)}
                  </p>
                  <span className={styles.vitalSub}>
                    {counts.total} entries
                  </span>
                </dd>
              </div>

              <div className={styles.vital}>
                <dt className={`label-mono ${styles.vitalK}`}>Confidence</dt>
                <dd className={styles.vitalV}>
                  <p className={`h-vital-display ${vitalToneClass(confT)}`}>
                    {prettyEnum(exec.confidence)}
                  </p>
                  <span className={styles.vitalSub}>
                    {counts.primary} primary · {counts.secondary} secondary
                  </span>
                </dd>
              </div>

              <div className={styles.vital}>
                <dt
                  className={`label-mono ${styles.vitalK}`}
                  title={
                    "Genome-wide Sonnet triage prior — first-pass surface-vs-not " +
                    "call made before any deep literature work. Hydrated from " +
                    "public D1 `triage_run_public` (mainbench_canonical_v1 · " +
                    "variant=ncbi · model=claude-sonnet-4-6). Falls back to " +
                    "`unknown` when no triage row exists for the gene."
                  }
                >
                  Triage
                </dt>
                <dd className={styles.vitalV}>
                  <p className={`h-vital-display ${vitalToneClass(triT)}`}>
                    {prettyEnum(rec.triage_signal)}
                  </p>
                  <span className={styles.vitalSub}>
                    {exec.headline_risks.length
                      ? `${exec.headline_risks.length} headline risk${
                          exec.headline_risks.length === 1 ? "" : "s"
                        }`
                      : "No headline risks"}
                  </span>
                </dd>
              </div>
            </>
          );
        })()}
      </dl>
    </header>
  );
}
