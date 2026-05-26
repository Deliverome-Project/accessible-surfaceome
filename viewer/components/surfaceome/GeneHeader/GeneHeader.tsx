import type { CatalogRow } from "../../../lib/surfaceome";
import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import type { StructureViewerData } from "../../../lib/structure-viewer-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { DatabasePresenceStrip } from "../DatabasePresenceCard/DatabasePresenceStrip";
import { FeedbackButton } from "../../FeedbackButton/FeedbackButton";
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

/** Reader-facing label for `executive_summary.state_dependence`:
 *  - `low` → Constitutive (surface call holds across cell states)
 *  - `moderate` → Conditional (call depends on cell state / context)
 *  - `high` → State-dependent (call only in specific states; e.g.
 *     cancer-only, stress-only)
 *  - `unclear` → Unclear (evidence too thin to call) */
function stateDependenceLabel(value: string): string {
  if (value === "low") return "Constitutive";
  if (value === "moderate") return "Conditional";
  if (value === "high") return "State-dependent";
  return "Unclear";
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

          {/* Executive summary one-paragraph. Headline risks + cited
              evidence chips were dropped from the header per user
              feedback — both are still visible:
                * headline_risks → the State-dependence vital below
                  (subtitle shows "N headline risks") + the §Risks card
                * cited_evidence_ids → the §Evidence ledger + each
                  per-row EvidenceChipList */}
          <p className={styles.execLede}>{exec.one_paragraph}</p>

          {/* Vitals 2×2 grid — Accessibility / Experimental surface
              evidence / Confidence / State dependence. The fourth
              vital is the editorial summary of `state_dependence`
              ("Constitutive" / "Conditional" / "State-dependent" /
              "Unclear"); the raw Sonnet triage prior moved off the
              gene-page hero — it's still in D1 if a reader wants it,
              but it isn't a headline signal. */}
          <dl className={styles.vitals}>
            {(() => {
              const accessTone = accessibilityTone(exec.surface_accessibility);
              const gradeT = gradeTone(exec.evidence_grade_summary);
              const confT = confidenceTone(exec.confidence);
              const stateT = stateDependenceTone(exec.state_dependence);
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
                        "Editorial summary of `executive_summary.state_dependence`: " +
                        "Constitutive (surface call holds across cell states) → " +
                        "Conditional (depends on context) → State-dependent " +
                        "(only in specific states; e.g. cancer-only, stress-only) → " +
                        "Unclear (evidence too thin to call). Replaces the raw " +
                        "Sonnet triage prior, which lives in D1's triage_run_public " +
                        "but isn't useful as a gene-page headline."
                      }
                    >
                      State dependence
                    </dt>
                    <dd className={styles.vitalV}>
                      <p className={`h-vital-display ${vitalToneClass(stateT)}`}>
                        {stateDependenceLabel(exec.state_dependence)}
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
        </div>

        {structureData ? (
          <aside className={styles.structureSlot} aria-label="3D structure">
            <StructureViewer
              data={structureData}
              geneSymbol={g.hgnc_symbol}
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
            {/* SURFACE-Bind stat — sits below the AFDB row inside the
                same structure aside so the reader sees patch-level
                targetability next to the model that scored it. When
                the protein isn't in SURFACE-Bind, render a neutral
                "not scored" pill rather than the count (zeroes here
                are an absence signal, not an actual measurement). */}
            <dl className={styles.structureStats} aria-label="SURFACE-Bind summary">
              <div className={styles.structureStat}>
                <dt
                  className={`label-mono ${styles.structureStatK}`}
                  title={
                    "SURFACE-Bind (Marchand 2026 PNAS, " +
                    "doi:10.1073/pnas.2506269123) — MaSIF / patch-based " +
                    "targetability mapping. Each site is a surface patch " +
                    "scored as designable for a de novo binder. Total " +
                    "seeds = candidate binder backbone fragments docked " +
                    "to all sites combined (α-helical + β-strand)."
                  }
                >
                  SURFACE-Bind
                </dt>
                <dd className={styles.structureStatV}>
                  {/* Three distinct states (intentionally NOT collapsed):
                      1. ``has_data=false`` — not in the SURFACE-Bind table at all
                         (SURFACE-Bind dropped it during structural-quality filtering;
                         common for inner-leaflet kinases like SRC).
                      2. ``has_data=true, n_sites=0`` — protein WAS scored by
                         SURFACE-Bind but no surface patches cleared the MaSIF
                         targetability threshold. GPR75 + CLDN18 land here.
                      3. ``has_data=true, n_sites>0`` — has scored targetable
                         patches; show the count + link out. EGFR is the
                         canonical example. */}
                  {!rec.deterministic_features.surface_bind.has_data ? (
                    <StatusPill
                      tone="neutral"
                      size="sm"
                      title="Not in SURFACE-Bind's dataset at all. SURFACE-Bind filtered the protein out during structural-quality screening — typically inner-leaflet anchors, soluble cytoplasmic proteins, or poorly-modeled targets. Distinct from 'scored with no patches'."
                    >
                      not in SURFACE-Bind
                    </StatusPill>
                  ) : rec.deterministic_features.surface_bind.n_sites === 0 ? (
                    <a
                      href={`https://surface-bind.inria.fr/protein.html?uniprot=${g.uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.structureStatLink}
                      title="In SURFACE-Bind's authoritative table but no surface patches cleared the MaSIF targetability threshold. The protein was scored; the surface chemistry didn't yield designable binder seeds. Distinct from 'not in SURFACE-Bind'."
                    >
                      scored · no patches ↗
                    </a>
                  ) : (
                    <a
                      href={`https://surface-bind.inria.fr/protein.html?uniprot=${g.uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.structureStatLink}
                    >
                      {rec.deterministic_features.surface_bind.n_sites} site
                      {rec.deterministic_features.surface_bind.n_sites === 1
                        ? ""
                        : "s"}{" "}
                      · {rec.deterministic_features.surface_bind.n_seeds_total.toLocaleString()}{" "}
                      seeds ↗
                    </a>
                  )}
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

    </header>
  );
}
