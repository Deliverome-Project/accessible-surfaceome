import type { CatalogRow } from "../../../lib/surfaceome";
import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import type { StructureViewerData } from "../../../lib/structure-viewer-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { tooltips } from "../../../lib/tooltips";
import { DatabasePresenceStrip } from "../DatabasePresenceCard/DatabasePresenceStrip";
import { FeedbackButton } from "../../FeedbackButton/FeedbackButton";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import { StructureViewer } from "../StructureViewerCard/StructureViewer";
import styles from "./GeneHeader.module.css";

/** Convert an isoform UniProt id like "P00533-2" into a reader-friendly
 *  tab label ("Isoform 2"). Falls back to the raw id when the suffix
 *  doesn't match the expected pattern. */
function _isoformLabel(isoformId: string): string {
  const m = /-(\d+)$/.exec(isoformId);
  return m ? `Isoform ${m[1]}` : isoformId;
}

/** Best-effort DeepTMHMM type inference from a per-residue topology
 *  string. The StructureViewerData type expects "TM" / "SP+TM" /
 *  "SP" / "BETA" / "GLOB"; the IsoformTopology Pydantic class
 *  doesn't carry the rolled-up type, so we approximate from the
 *  per-residue string. The result drives the GLOB-vs-TM caption only
 *  — no functional behavior depends on it. */
function _inferDeepTMHMMType(
  topology: string,
): import("../../../lib/structure-viewer-types").DeepTMHMMType {
  const hasS = topology.includes("S");
  const hasM = topology.includes("M");
  const hasB = topology.includes("B");
  if (hasB) return "BETA";
  if (hasS && hasM) return "SP+TM";
  if (hasM) return "TM";
  if (hasS) return "SP";
  return "GLOB";
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
  /** 5-DB surface-vote vector from the candidate-universe build.
   *  When present, a slim ``<DatabasePresenceStrip>`` renders inline
   *  above the executive summary so the reader sees DB consensus
   *  without scrolling. ``null`` for resolver-failure outliers — the
   *  strip is omitted in that case (same fall-back as the old
   *  section-card placement). */
  catalogRow?: CatalogRow | null;
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

/** Convert the derived `TriageSignal` enum back to the original
 *  triage verdict the agent actually emitted. The signal is a 1:1
 *  rename of `TriageVerdict` (yes | contextual | no), so the
 *  inversion is mechanical. Rendering the verdict instead of the
 *  signal matches what the synthesizer's prose quotes (e.g. SRC's
 *  confidence_reasoning: "Triage called verdict='no', …"). */
function triageVerdictLabel(signal: string): string {
  if (signal === "likely_accessible") return "Yes";
  if (signal === "possibly_accessible") return "Contextual";
  if (signal === "unlikely") return "No";
  return "Unknown";
}

/** Compare the Sonnet triage prior to the deep-dive surface verdict.
 *
 * Returns one of:
 * - `"agree"` — both sides on the same side of the binary surface call
 * - `"conflict"` — triage and deep-dive disagree (e.g. SRC's eSrc finding:
 *     triage said `unlikely`, deep dive said `high`)
 * - `"unclear"` — one or both sides emit `unknown` / `uncertain`, so no
 *     useful comparison
 *
 * The deep dive wins on conflict (it has the per-method evidence); the
 * triage row just flags the disagreement for transparency. */
function triageVsDeepDive(
  triage: string,
  accessibility: string,
): "agree" | "conflict" | "unclear" {
  const triagePositive =
    triage === "likely_accessible" || triage === "possibly_accessible";
  const triageNegative = triage === "unlikely";
  const deepPositive = accessibility === "high" || accessibility === "moderate";
  const deepNegative = accessibility === "low" || accessibility === "no";
  if (triagePositive && deepPositive) return "agree";
  if (triageNegative && deepNegative) return "agree";
  if (triagePositive && deepNegative) return "conflict";
  if (triageNegative && deepPositive) return "conflict";
  return "unclear";
}

function stateDependenceTone(value: string) {
  // low = always-on surface call → success / green; the safest target.
  // moderate = context-dependent → lavender; needs the right cell state.
  // high = only in specific states → amber; reader should pay attention.
  // unclear = neutral.
  if (value === "low") return "success" as const;
  if (value === "moderate") return "lavender" as const;
  if (value === "high") return "amber" as const;
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
export function GeneHeader({
  rec,
  geneName,
  structureData,
  catalogRow,
}: GeneHeaderProps) {
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
  // Four canonical external IDs only — SURFACE-Bind was dropped from
  // this row (it's already linked from the 3D viewer's ↗ control next
  // to the mode toggle, no need to surface it twice).
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
          {/* The descriptive HGNC name ("epidermal growth factor
              receptor") was removed from the header per user feedback —
              the gene symbol IS the page identity; the long name added
              visual weight without telling the target-discovery reader
              anything they didn't already know. Synonyms came off the
              same line; if a reader needs them they're available via
              the JSON / Markdown crumbs and in the per-gene record. */}

          {/* IDs row — small, immediately under the descriptive gene
              name. Was previously placed below the exec lede + headline
              risks; promoted here per user feedback so the external
              identifiers are visually attached to the gene-name strip. */}
          {/* IDs row + Submit-feedback CTA. The button sits inline at
              the end of the identifier strip so the call-to-action is
              visually attached to the IDs rather than floating
              elsewhere on the page; on narrow viewports the flex wrap
              puts it on its own line under the IDs. */}
          <div className={styles.idsRow}>
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
            <FeedbackButton
              gene={g.hgnc_symbol}
              uniprotAcc={g.uniprot_acc}
              variant="standalone"
            />
          </div>

          {/* DB-membership strip — was a full §section card; promoted
              to an inline strip immediately above the exec summary
              per user feedback. ``null`` for resolver-failure
              outliers, where we just omit the strip. */}
          {catalogRow ? <DatabasePresenceStrip row={catalogRow} /> : null}

          {/* Triage row — Sonnet first-pass surface verdict, sitting
              under the DB-presence strip for transparency. Tagged with
              "initial pass · no web search" so the reader knows this
              isn't the deep-dive call. When the triage disagrees with
              the deep-dive `surface_accessibility`, the row carries a
              warn pill that links the eye to the conflict (e.g. for
              SRC: triage=Unlikely vs deep-dive=High — the eSrc
              cancer-specific surface that the initial triage missed). */}
          {(() => {
            const verdict = triageVsDeepDive(
              rec.triage_signal,
              exec.surface_accessibility,
            );
            return (
              <p className={styles.triageRow}>
                <span className={`label-mono ${styles.triageLabel}`}>
                  Triage
                  <InfoTip>{tooltips.triage_signal}</InfoTip>
                </span>
                <span className={styles.triageValue}>
                  {triageVerdictLabel(rec.triage_signal)}
                </span>
                <span className={styles.triageQualifier}>
                  initial pass · no web search
                </span>
                {verdict === "conflict" ? (
                  <span className={styles.triageConflict}>
                    conflicts with deep dive
                  </span>
                ) : verdict === "agree" ? (
                  <span className={styles.triageAgree}>
                    agrees with deep dive
                  </span>
                ) : null}
              </p>
            );
          })()}

          {/* Executive summary one-paragraph. Headline risks + cited
              evidence chips were dropped from the header per user
              feedback — both are still visible:
                * headline_risks → the State-dependence vital below
                  (subtitle shows "N headline risks") + the §Risks card
                * cited_evidence_ids → the §Evidence ledger + each
                  per-row EvidenceChipList */}
          <p className={styles.execLede}>{exec.one_paragraph}</p>

          {/* Vitals 2×2 grid — Accessibility / Experimental surface
              evidence / Confidence / State dependence. Each label
              carries an <InfoTip> with provenance (LLM rollup vs
              deterministic source). The raw enum values render via
              prettyEnum so the reader sees the same labels they see
              in the data ledger. */}
          <dl className={styles.vitals}>
            {(() => {
              const accessTone = accessibilityTone(exec.surface_accessibility);
              const gradeT = gradeTone(exec.evidence_grade_summary);
              const confT = confidenceTone(exec.confidence);
              const stateT = stateDependenceTone(exec.state_dependence);
              return (
                <>
                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Accessibility
                      <InfoTip>{tooltips.surface_accessibility}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(accessTone)}`}>
                        {prettyEnum(exec.surface_accessibility)}
                      </p>
                      {/* Architecture + Family as label/value text pairs
                       *  beneath the accessibility value. Font matches
                       *  the StatusPill chip (uppercase, font-sans,
                       *  letter-spaced, 0.72rem); the value inherits the
                       *  accessibility tone color (success / teal / amber
                       *  / danger) so the text reads as colored metadata
                       *  belonging to this accessibility cell. */}
                      <p
                        className={`${styles.archFamilyInline} ${vitalToneClass(accessTone)}`}
                      >
                        <span className={styles.archFamilyLabel}>
                          Architecture
                        </span>
                        <span className={styles.archFamilyValue}>
                          {prettyEnum(exec.subcategory)}
                        </span>
                        <span className={styles.archFamilyLabel}>Family</span>
                        <span className={styles.archFamilyValue}>
                          {prettyEnum(exec.protein_family)}
                        </span>
                      </p>
                    </dd>
                  </div>

                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Experimental surface evidence
                      <InfoTip>{tooltips.experimental_surface_evidence}</InfoTip>
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
                    <dt className={`label-mono ${styles.vitalK}`}>
                      Confidence
                      <InfoTip>{tooltips.confidence}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(confT)}`}>
                        {prettyEnum(exec.confidence)}
                      </p>
                      <span className={styles.vitalSub}>
                        {counts.primary} primary · {counts.secondary} secondary
                      </span>
                      {/* "reasoning" — inline expander below the
                       *  confidence value. Uses the same `<details>` +
                       *  `.summary` pattern as the Evidence ledger card
                       *  (accent-colored cursor: pointer line, no
                       *  background; toggles to show the synthesizer's
                       *  user-facing prose). Hidden when reasoning is
                       *  empty/whitespace — high-confidence calls
                       *  typically don't populate the field per the
                       *  synth prompt's "writing for the reader"
                       *  guidance. */}
                      {rec.confidence_reasoning &&
                      rec.confidence_reasoning.trim().length > 0 ? (
                        <details className={styles.reasoningDrawer}>
                          <summary className={styles.reasoningSummary}>
                            reasoning
                          </summary>
                          <p className={styles.reasoningBody}>
                            {rec.confidence_reasoning}
                          </p>
                        </details>
                      ) : null}
                    </dd>
                  </div>

                  <div className={styles.vital}>
                    <dt className={`label-mono ${styles.vitalK}`}>
                      State dependence
                      <InfoTip>{tooltips.state_dependence}</InfoTip>
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(stateT)}`}>
                        {prettyEnum(exec.state_dependence)}
                      </p>
                      <span className={styles.vitalSub}>
                        {exec.headline_risks.length
                          ? `${exec.headline_risks.length} headline risk${
                              exec.headline_risks.length === 1 ? "" : "s"
                            }`
                          : "No headline risks"}
                        <InfoTip label="About headline risks">
                          {tooltips.headline_risks}
                        </InfoTip>
                      </span>
                    </dd>
                  </div>
                </>
              );
            })()}
          </dl>
        </div>

        {structureData ? (
          <aside className={styles.structureSlot} aria-label="3D structure">
            <StructureViewer
              data={structureData}
              geneSymbol={g.hgnc_symbol}
              // Canonical AFDB stats — the new caption inside the
              // viewer renders these for the canonical tab (and
              // lazy-fetches metadata for other AFDB variants when
              // the user switches tabs).
              canonicalStruct={{
                afdb_id: struct.afdb_id,
                afdb_version: struct.afdb_version,
                ecd_mean_plddt: struct.ecd_mean_plddt,
                ecd_disordered_fraction: struct.ecd_disordered_fraction,
                source: struct.source,
              }}
              // UniProt protein name (NCBI gene_info `name`) — shown
              // in italic above the AFDB stats for the canonical
              // tab, like the structure title shown for experimental.
              proteinName={geneName?.name ?? null}
              // Pass SURFACE-Bind anchor residues so each scored
              // patch gets a sphere + label on the 3D structure.
              // Empty array when the protein isn't in SURFACE-Bind
              // OR is in but no patches cleared scoring; the viewer
              // simply skips the overlay loop in that case.
              // Compartment per anchor is derived from the
              // DeepTMHMM ``per_residue_topology`` character at
              // the anchor residue (1-indexed): O=extracellular,
              // I=intracellular, M=membrane, S=signal, else
              // unknown. Lets the viewer's "Sites focus" mode
              // label each sphere with EC/IC at a glance so the
              // reader knows which sites are antibody-accessible.
              surfaceBindAnchors={rec.deterministic_features.surface_bind.sites.map(
                (s) => {
                  const topo = structureData.topology;
                  const idx = s.anchor_residue - 1;
                  const ch =
                    idx >= 0 && idx < topo.length ? topo.charAt(idx) : "?";
                  const compartment =
                    ch === "O"
                      ? ("extracellular" as const)
                      : ch === "I"
                        ? ("intracellular" as const)
                        : ch === "M"
                          ? ("membrane" as const)
                          : ch === "S"
                            ? ("signal" as const)
                            : ("unknown" as const);
                  return {
                    siteId: s.site_id,
                    residue: s.anchor_residue,
                    compartment,
                  };
                },
              )}
              // Variant tabs above the 3D canvas: alt isoforms
              // (sourced from `rec.deterministic_features.isoform_topologies`)
              // and 1:1 orthologs (mouse + cynomolgus). Each variant
              // carries its own per-residue topology so the topology
              // coloring + membrane slab work without extra fetches.
              //
              // Isoforms: the .3line UniProt acc has a `-N` suffix
              // (e.g. "P00533-2"). AFDB models the canonical
              // accession but applies the isoform-specific
              // sequence/topology, so the URL path strips the
              // suffix back to the bare canonical.
              //
              // Orthologs: rendered ONLY when the ortholog has a
              // matching topology cohort row in D1; we currently
              // ship topology for mouse + cyno orthologs in
              // `topology_public` but the per-residue strings live
              // there, not on `OrthologEntry`. For MVP we render
              // just the canonical + isoform variants and leave
              // orthologs for a follow-up commit that backfills the
              // ortholog topology strings onto the SurfaceomeRecord.
              variants={rec.deterministic_features.isoform_topologies.map(
                (iso) => ({
                  source: "afdb" as const,
                  id: `iso-${iso.isoform_id}`,
                  label: _isoformLabel(iso.isoform_id),
                  sublabel: iso.isoform_id,
                  uniprot_acc: iso.uniprot_acc,
                  uniprot_acc_full: iso.isoform_id,
                  topology: iso.per_residue_topology,
                  // IsoformTopology doesn't carry `deeptmhmm_type`
                  // (TM / SP+TM / etc.) — synthesize a best-effort
                  // value from the topology string so the GLOB
                  // caption etc. still render sensibly on variant
                  // switch.
                  deeptmhmm_type: _inferDeepTMHMMType(
                    iso.per_residue_topology,
                  ),
                }),
              )}
            />
            {/* Legend moved INSIDE <StructureViewer> so it can
                switch between the M/O/I/S/B topology key and the
                EC/IC/TM sites key based on the viewer's internal
                viewMode state. */}
            {/* AFDB stats moved INSIDE <StructureViewer> as part of
                the new per-variant caption. The caption renders the
                pLDDT pill + disordered fraction + AFDB entry link
                for the active variant (canonical reuses
                rec.deterministic_features.structure; isoforms /
                orthologs lazy-fetch AFDB metadata at click time;
                experimental shows resolution + method + RCSB link
                instead). */}
            {/* SURFACE-Bind summary <dl> was removed — it duplicated the
                §SURFACE-Bind card (which carries the same site count,
                seed total, and surface-bind.inria.fr link in a richer
                presentation) AND the Summary metrics SURFACE-Bind chip
                (which gives the catalog-filter view). One source of
                truth: the SurfaceBindCard section below. */}
            {/* Old DeepTMHMM-orientation caption removed — the new
                StructureViewer caption already names the model + the
                per-variant pLDDT / disordered stats; the orientation
                hint is implicit in the membrane slab shown above. */}
          </aside>
        ) : null}
      </div>

    </header>
  );
}
