"use client";

import { useEffect, useState, type ReactNode } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import { EvidenceChip } from "../EvidenceChip/EvidenceChip";
import type { PaperMetadataMap } from "../../../lib/surfaceome-types";
import { EvidenceDrawer } from "../EvidenceDrawer/EvidenceDrawer";
import type { Evidence } from "../../../lib/surfaceome-types";
import { INTERNALIZATION_FATE_LABELS } from "../../../lib/internalization";
import styles from "./InternalizationCard.module.css";

/** Strip of clickable evidence chips for a table "cites" cell — each opens the
 *  card's EvidenceDrawer (same UX as the deep-dive), replacing the raw
 *  ``int_evi_NN`` ids. Falls back to a dash when a row cites nothing. */
function CiteChips({ ids }: { ids: readonly string[] }) {
  if (!ids.length) return <span className={styles.muted}>—</span>;
  return (
    <span className={styles.citeChips}>
      {ids.map((id) => (
        <EvidenceChip key={id} evidenceId={id} />
      ))}
    </span>
  );
}

// The sequence (model-prior) track uses the 5-point SeqGrade; the literature
// track's per-mode Grade retains `no` (and legacy records may carry it). Keep
// both unions here so a record from either track renders.
type Grade =
  | "very_high"
  | "high"
  | "moderate"
  | "low"
  | "very_low"
  | "no"
  | "unknown";

// Shared public Worker (D1-backed) — same base the catalog table uses. Falls
// back to the production deployment when the build-time public env isn't set
// (the Worker serves both prod + dev viewers).
const API_BASE =
  process.env.NEXT_PUBLIC_SURFACEOME_API_BASE ??
  "https://api.deliverome.org/surfaceome";

interface MotifHit {
  motif_type: string;
  sequence: string;
  region: string;
  approx_position: string | null;
  functional_context: boolean;
  note: string;
}
interface IsoformPrior {
  isoform_id: string;
  is_canonical: boolean;
  length_aa: number | null;
  topology_summary: string;
  endocytic_motifs_noted: string | null;
  motifs?: MotifHit[];
  grade: Grade;
  confidence: string;
  rationale: string;
}
interface ModelPriorTrack {
  model: string;
  overall_grade: Grade;
  overall_confidence: string;
  model_reasoning: string;
  per_isoform: IsoformPrior[];
}
interface ModeGrade {
  grade: Grade;
  confidence: string;
  rationale: string;
  cited_source_ids: string[];
}
interface Quant {
  rate_metric: string | null;
  rate_value: number | null;
  rate_unit: string | null;
  time_point?: string | null;
  quant_summary: string;
  // Additive schema 0.3.0 normalized continuous kinetics & single-endpoint estimates.
  derived_ke_min_inv?: number | null;
  derived_t_half_min?: number | null;
  apparent_t_half_min?: number | null;
  derived_kinetics_basis?: string | null;
}
interface Observation {
  assay_type: string;
  cell_line: string | null;
  cell_context: string;
  species?: string | null;
  internalization_mode: string;
  ligand_name: string | null;
  binder_type?: string | null;
  binder_valency?: string | null;
  expression_context?: string | null;
  post_uptake_fate?: string | null;
  rate_class?: string | null;
  steady_state_internal_pct?: number | null;
  mechanism: string | null;
  magnitude: string;
  quant: Quant;
  controls_note: string | null;
  cited_source_ids: string[];
}
interface ModulatorObs {
  modulator: string;
  perturbation: string;
  effect_on_target: string;
  cell_line: string | null;
  cell_context: string;
  magnitude: string;
  quant: Quant;
  note: string;
  cited_source_ids: string[];
}
interface Source {
  evidence_id: string;
  evidence_type: string;
  confidence: string;
  entailment_verified: boolean;
  spans: { source: { source_id: string; url: string }; section: string; quote: string }[];
}
interface Literature {
  overall_grade: Grade;
  overall_confidence: string;
  rationale: string;
  cross_condition_note: string;
  species_scope: string;
  // Additive schema 0.3.0 synthesis summaries & flags.
  predominant_fate?: string | null;
  trafficking_summary?: string | null;
  ligand_dependence_summary?: string | null;
  epitope_or_valency_dependence_note?: string | null;
  has_primary_or_invivo_evidence?: boolean | null;
  grades_by_mode: {
    basal: ModeGrade;
    native_ligand: ModeGrade;
    therapeutic: ModeGrade;
    // Additive 4th mode (schema 0.1.6+); absent on older records.
    pathogen_entry?: ModeGrade;
  };
  observations: Observation[];
  modulator_observations?: ModulatorObs[];
  sources: Source[];
  n_papers_discovered: number;
  n_papers_fetched: number;
}
export interface InternalizationRecord {
  papers?: PaperMetadataMap;
  gene_symbol: string;
  uniprot_acc: string;
  model_priors: ModelPriorTrack[];
  literature: Literature | null;
}
type Record = InternalizationRecord;

interface Props {
  symbol: string;
  n: number;
}

function em(v: unknown) {
  if (v === null || v === undefined || v === "") return <span className={styles.empty}>—</span>;
  return <>{String(v)}</>;
}

// Structured rate value + its human context. A bare "2.5 fold" or "45 %" is
// ambiguous without the comparator ("...higher than the unconjugated antibody",
// "...of surface pool internalized at 1 h") — which the grader records in
// quant_summary. Always show the summary next to the number so the reader knows
// what the value is relative to; fall back to the summary alone when there is no
// structured value.
function fmtKinetic(v: number): string {
  if (!Number.isFinite(v)) return "";
  if (Math.abs(v) < 0.01) return v.toExponential(2);
  if (Math.abs(v) < 1) return Number(v.toPrecision(3)).toString();
  return Number(v.toFixed(2)).toString();
}

function hasAnyQuant(o: Observation): boolean {
  const q = o.quant;
  return (
    q.rate_value != null ||
    q.derived_ke_min_inv != null ||
    q.derived_t_half_min != null ||
    q.apparent_t_half_min != null
  );
}

function prettyFate(v: string | null | undefined): string {
  if (!v) return "";
  return INTERNALIZATION_FATE_LABELS[v] ?? prettyLabel(v);
}

function prettyBinder(v: string | null | undefined): string {
  if (!v || v === "unknown") return "";
  const map: { [k: string]: string } = {
    none_constitutive: "constitutive",
    native_ligand: "native ligand",
    nanobody_or_fab: "nanobody / Fab",
    bispecific_or_biparatopic: "bispecific",
    nanoparticle_or_lnp: "LNP / NP",
    viral_or_toxin: "viral / toxin",
    small_molecule: "small mol",
    adc: "ADC",
  };
  return map[v] ?? prettyLabel(v);
}

function QuantValue({
  value,
  unit,
  summary,
  quant,
}: {
  value: number | null | undefined;
  unit: string | null | undefined;
  summary?: string | null;
  quant?: Quant;
}) {
  const fittedParts: string[] = [];
  if (quant?.derived_t_half_min != null) {
    fittedParts.push(`t½ ${fmtKinetic(quant.derived_t_half_min)} min`);
  }
  if (quant?.derived_ke_min_inv != null) {
    fittedParts.push(`kₑ ${fmtKinetic(quant.derived_ke_min_inv)} min⁻¹`);
  }
  const basisTitle = quant?.derived_kinetics_basis
    ? `Derived kinetics basis: ${prettyLabel(quant.derived_kinetics_basis)}`
    : "Fitted continuous internalization kinetics";
  const fittedTag = fittedParts.length ? (
    <span className={styles.kineticTag} title={basisTitle}>
      {fittedParts.join(" · ")}
    </span>
  ) : null;
  const apparentTag =
    !fittedTag && quant?.apparent_t_half_min != null ? (
      <span
        className={styles.apparentTag}
        title="Single-endpoint apparent t½ (≤4 h uptake estimate, distinct from fitted kinetics)"
      >
        apparent t½ {fmtKinetic(quant.apparent_t_half_min)} min
      </span>
    ) : null;

  const tp = quant?.time_point ? ` (${quant.time_point})` : "";

  if (value === null || value === undefined) {
    if (!summary && !fittedTag && !apparentTag) return em(summary);
    return (
      <>
        {fittedTag}
        {apparentTag}
        {summary ? (
          <span className={styles.muted}>
            {fittedTag || apparentTag ? " — " : ""}
            {summary}
          </span>
        ) : null}
      </>
    );
  }
  return (
    <>
      <strong>
        {value}
        {unit ? ` ${unit}` : ""}
        {tp}
      </strong>
      {fittedTag}
      {apparentTag}
      {summary ? <span className={styles.muted}> — {summary}</span> : null}
    </>
  );
}

function Pill({ grade, label }: { grade: Grade | string; label?: string }) {
  const g = (grade || "unknown") as string;
  return <span className={`${styles.pill} ${styles["g_" + g] ?? styles.g_unknown}`}>{label ?? g}</span>;
}

// Prettify a snake_case enum for a badge ("adc_internalization" -> "ADC
// internalization"), upper-casing common acronyms.
const _ACRONYMS = /\b(adc|pet|ph|rna|dna|aav|lnp|immunopet)\b/gi;
function prettyLabel(v: string | null | undefined): string {
  if (!v) return "";
  return v.replace(/_/g, " ").replace(_ACRONYMS, (m) => m.toUpperCase());
}

// Small neutral category chip for the assay / mode / metric columns — makes each
// a distinct field rather than run-on text.
function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className={styles.empty}>—</span>;
  return <span className={styles.badge}>{prettyLabel(value)}</span>;
}

// Confidence, explicitly labeled so it's not a mystery "(moderate)" in parens.
function Conf({ level }: { level: string | null | undefined }) {
  if (!level) return null;
  return (
    <span className={styles.conf}>
      confidence <strong>{level}</strong>
    </span>
  );
}

// Magnitude ordinal (for the sortable "mag" column). Index signature — the card
// declares a local `Record` interface that shadows TS's generic Record<K,V>.
const MAG_RANK: { [k: string]: number } = {
  high: 4,
  moderate: 3,
  low: 2,
  none: 1,
  unknown: 0,
};

// Reader-facing labels for the structured endocytic-motif types.
const MOTIF_LABEL: { [k: string]: string } = {
  yxxphi: "YXXΦ",
  npxy: "NPXY",
  dileucine: "dileucine",
  acidic_cluster: "acidic cluster",
  other: "motif",
};

// Turn inline `int_evi_NN` refs in grader prose into clickable EvidenceChips
// ("int_evi_03 shows…" -> "[3] shows…") so mode rationales link into the same
// drawer as the table cites instead of showing raw internal ids.
function linkifyIntEvi(text: string | null | undefined): ReactNode {
  if (!text) return <span className={styles.empty}>—</span>;
  const parts = text.split(/(int_evi_\d+)/g);
  if (parts.length === 1) return text;
  return parts.map((p, i) =>
    /^int_evi_\d+$/.test(p) ? <EvidenceChip key={i} evidenceId={p} /> : p,
  );
}

// Sort the observations by the active column. String columns sort
// alphabetically; `mag` by ordinal rank; `value` by the numeric rate_value.
function sortObs(
  obs: readonly Observation[],
  sort: { key: string; dir: 1 | -1 },
): Observation[] {
  if (!sort.key) return [...obs];
  const { key, dir } = sort;
  const v = (o: Observation): string | number => {
    if (key === "mag") return MAG_RANK[o.magnitude] ?? 0;
    if (key === "value") return o.quant.rate_value ?? Number.NEGATIVE_INFINITY;
    if (key === "metric") return o.quant.rate_metric ?? "";
    if (key === "assay") return o.assay_type ?? "";
    if (key === "mode") return o.internalization_mode ?? "";
    if (key === "species") return o.species ?? "";
    if (key === "cell_line") return o.cell_line ?? "";
    return "";
  };
  return [...obs].sort((a, b) => {
    const av = v(a);
    const bv = v(b);
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

// Clickable sortable table header cell.
function SortTh({
  k,
  label,
  sort,
  onSort,
}: {
  k: string;
  label: string;
  sort: { key: string; dir: 1 | -1 };
  onSort: (k: string) => void;
}) {
  const active = sort.key === k;
  return (
    <th
      className={styles.sortable}
      onClick={() => onSort(k)}
      aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
    >
      {label}
      <span className={styles.sortArrow}>{active ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</span>
    </th>
  );
}

export function InternalizationCardBody({
  rec,
  obsSort,
  toggleObsSort,
  obsModeFilter = "all",
  setObsModeFilter,
  obsQuantOnly = false,
  setObsQuantOnly,
}: {
  rec: InternalizationRecord;
  obsSort: { key: string; dir: 1 | -1 };
  toggleObsSort: (k: string) => void;
  obsModeFilter?: string;
  setObsModeFilter?: (m: string) => void;
  obsQuantOnly?: boolean;
  setObsQuantOnly?: (v: boolean) => void;
}) {
  const lit = rec.literature ?? null;

  const allObs = lit?.observations ?? [];
  const fittedHalfLives = allObs
    .map((o) => o.quant.derived_t_half_min)
    .filter((v): v is number => v != null && Number.isFinite(v) && v > 0);
  const fastestTHalf = fittedHalfLives.length
    ? Math.min(...fittedHalfLives)
    : null;
  const nQuantObs = allObs.filter(hasAnyQuant).length;

  const modeCounts = new Map<string, number>();
  for (const o of allObs) {
    if (o.internalization_mode) {
      modeCounts.set(
        o.internalization_mode,
        (modeCounts.get(o.internalization_mode) ?? 0) + 1,
      );
    }
  }
  const presentModes = Array.from(modeCounts.entries());

  const visibleObs = sortObs(
    allObs.filter((o) => {
      if (obsModeFilter !== "all" && o.internalization_mode !== obsModeFilter) {
        return false;
      }
      if (obsQuantOnly && !hasAnyQuant(o)) return false;
      return true;
    }),
    obsSort,
  );

  const summaryNotes: { label: string; text: string }[] = [];
  if (lit?.trafficking_summary) {
    summaryNotes.push({ label: "Trafficking", text: lit.trafficking_summary });
  }
  if (lit?.ligand_dependence_summary) {
    summaryNotes.push({
      label: "Ligand dependence",
      text: lit.ligand_dependence_summary,
    });
  }
  if (lit?.epitope_or_valency_dependence_note) {
    summaryNotes.push({
      label: "Epitope / valency",
      text: lit.epitope_or_valency_dependence_note,
    });
  }
  if (lit?.cross_condition_note) {
    summaryNotes.push({
      label: "Cross-condition",
      text: lit.cross_condition_note,
    });
  }

  return (
    <div className={styles.body}>
      {/* Literature track FIRST — observed, PMID/DOI-anchored evidence */}
      <div className={styles.sub}>
        <div className={styles.subHead}>
          <span className={styles.trackLabelLit}>Literature</span>
          {lit && (
            <span className={styles.muted}>
              {lit.n_papers_discovered} papers discovered · {lit.sources.length} evidence sources
            </span>
          )}
        </div>
        {!lit && <p className={styles.muted}>No literature track.</p>}
        {lit && (
          <>
            <div className={styles.overall}>
              overall <Pill grade={lit.overall_grade} /> <Conf level={lit.overall_confidence} />
              {lit.species_scope && lit.species_scope !== "unspecified" ? (
                <> · species {lit.species_scope}</>
              ) : null}
              {lit.predominant_fate && lit.predominant_fate !== "unknown" ? (
                <> · fate <span className={styles.badge}>{prettyFate(lit.predominant_fate)}</span></>
              ) : null}
              {lit.has_primary_or_invivo_evidence ? (
                <> · <span className={styles.tealBadge}>primary / in vivo</span></>
              ) : null}
              {fastestTHalf != null ? (
                <> · <span className={styles.kineticTag}>fastest fitted t½ {fmtKinetic(fastestTHalf)} min</span></>
              ) : null}
            </div>
            <p>{linkifyIntEvi(lit.rationale)}</p>
            {summaryNotes.length > 0 && (
              <div className={styles.summaryNotes}>
                {summaryNotes.map((n) => (
                  <p key={n.label} className={styles.summaryNote}>
                    <strong>{n.label}:</strong> {linkifyIntEvi(n.text)}
                  </p>
                ))}
              </div>
            )}
            <div className={styles.modes}>
              {(
                ["basal", "native_ligand", "therapeutic", "pathogen_entry"] as const
              ).map((k) => {
                const mg = lit.grades_by_mode[k];
                // pathogen_entry is additive + usually unknown — only surface
                // it when it carries a real grade, so the card isn't cluttered
                // with an empty 4th row for every gene (and old records that
                // lack the field entirely just skip it).
                if (!mg) return null;
                if (
                  k === "pathogen_entry" &&
                  (!mg.grade || mg.grade === "unknown")
                )
                  return null;
                return (
                  <div key={k} className={styles.mode}>
                    <span className={styles.modeName}>{k.replace(/_/g, " ")}</span>{" "}
                    <Pill grade={mg.grade} /> <Conf level={mg.confidence} />
                    <p className={styles.modeRat}>{linkifyIntEvi(mg.rationale)}</p>
                  </div>
                );
              })}
            </div>

            <h4 className={styles.h4}>
              Observations ({visibleObs.length}
              {visibleObs.length !== allObs.length ? ` of ${allObs.length}` : ""})
            </h4>
            {(presentModes.length > 1 || nQuantObs > 0) && setObsModeFilter && setObsQuantOnly && (
              <div className={styles.obsFilterBar} role="group" aria-label="Filter observations">
                {presentModes.length > 1 && (
                  <>
                    <button
                      type="button"
                      className={`${styles.obsFilterChip} ${obsModeFilter === "all" ? styles.obsFilterChipOn : ""}`}
                      onClick={() => setObsModeFilter("all")}
                    >
                      All ({allObs.length})
                    </button>
                    {presentModes.map(([mode, count]) => (
                      <button
                        key={mode}
                        type="button"
                        className={`${styles.obsFilterChip} ${obsModeFilter === mode ? styles.obsFilterChipOn : ""}`}
                        onClick={() =>
                          setObsModeFilter(obsModeFilter === mode ? "all" : mode)
                        }
                      >
                        {prettyLabel(mode)} ({count})
                      </button>
                    ))}
                  </>
                )}
                {nQuantObs > 0 && (
                  <button
                    type="button"
                    className={`${styles.obsFilterChip} ${obsQuantOnly ? styles.obsFilterChipOn : ""}`}
                    onClick={() => setObsQuantOnly(!obsQuantOnly)}
                  >
                    quantitative only ({nQuantObs})
                  </button>
                )}
              </div>
            )}
            <div className={styles.tablewrap}>
              <table className={styles.table}>
                <colgroup>
                  <col className={styles.colAssay} />
                  <col className={styles.colMode} />
                  <col className={styles.colCell} />
                  <col className={styles.colMode} />
                  <col className={styles.colMag} />
                  <col />
                  <col className={styles.colCites} />
                </colgroup>
                <thead>
                  <tr>
                    <SortTh k="assay" label="assay / mech" sort={obsSort} onSort={toggleObsSort} />
                    <SortTh k="mode" label="mode / binder" sort={obsSort} onSort={toggleObsSort} />
                    <SortTh k="cell_line" label="system" sort={obsSort} onSort={toggleObsSort} />
                    <th>fate</th>
                    <SortTh k="mag" label="mag" sort={obsSort} onSort={toggleObsSort} />
                    <SortTh k="value" label="kinetics / summary" sort={obsSort} onSort={toggleObsSort} />
                    <th>cites</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleObs.map((o, i) => {
                    const binder = prettyBinder(o.binder_type);
                    const valency =
                      o.binder_valency &&
                      o.binder_valency !== "unknown" &&
                      o.binder_valency !== "not_applicable"
                        ? o.binder_valency
                        : "";
                    const mech =
                      o.mechanism &&
                      o.mechanism !== "unknown" &&
                      o.mechanism !== "receptor_mediated_unspecified"
                        ? prettyLabel(o.mechanism)
                        : "";
                    const expr =
                      o.expression_context && o.expression_context !== "unknown"
                        ? prettyLabel(o.expression_context)
                        : "";
                    const fate =
                      o.post_uptake_fate && o.post_uptake_fate !== "unknown"
                        ? prettyFate(o.post_uptake_fate)
                        : "";
                    return (
                      <tr key={i}>
                        <td>
                          <div className={styles.cellStack}>
                            <Badge value={o.assay_type} />
                            {mech ? <span className={styles.cellSub}>{mech}</span> : null}
                          </div>
                        </td>
                        <td>
                          <div className={styles.cellStack}>
                            <Badge value={o.internalization_mode} />
                            {(binder || valency) ? (
                              <span className={styles.cellSub}>
                                {[binder, valency].filter(Boolean).join(" · ")}
                              </span>
                            ) : null}
                            {o.ligand_name ? (
                              <span className={styles.cellSub}>{o.ligand_name}</span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <div className={styles.cellStack}>
                            <span>{em(o.cell_line || o.cell_context)}</span>
                            {(o.species || expr) ? (
                              <span className={styles.cellSub}>
                                {[o.species ? prettyLabel(o.species) : "", expr]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <div className={styles.cellStack}>
                            {fate ? <span className={styles.badge}>{fate}</span> : <span className={styles.empty}>—</span>}
                            {o.steady_state_internal_pct != null ? (
                              <span className={styles.cellSub}>
                                SS {o.steady_state_internal_pct}% internal
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <Pill grade={o.magnitude} />
                        </td>
                        <td>
                          {o.quant.rate_metric ? (
                            <span style={{ marginRight: "0.35rem" }}>
                              <Badge value={o.quant.rate_metric} />
                            </span>
                          ) : null}
                          <QuantValue
                            value={o.quant.rate_value}
                            unit={o.quant.rate_unit}
                            summary={o.quant.quant_summary}
                            quant={o.quant}
                          />
                        </td>
                        <td><CiteChips ids={o.cited_source_ids} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {lit.modulator_observations && lit.modulator_observations.length > 0 && (
              <>
                <h4 className={styles.h4}>
                  Cross-gene modulators ({lit.modulator_observations.length})
                </h4>
                <p className={styles.muted}>
                  Perturbing a <em>different</em> gene changes this protein&apos;s
                  internalization. Recorded separately — these do <em>not</em> drive the grade.
                </p>
                <div className={styles.tablewrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>modulator</th>
                        <th>perturbation</th>
                        <th>effect on target</th>
                        <th>cell line</th>
                        <th>value / summary</th>
                        <th>cites</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lit.modulator_observations.map((m, i) => (
                        <tr key={i}>
                          <td className={styles.mono}>{em(m.modulator)}</td>
                          <td>{em(m.perturbation)}</td>
                          <td>{em(m.effect_on_target)}</td>
                          <td>{em(m.cell_line)}</td>
                          <td>
                            <QuantValue
                              value={m.quant.rate_value}
                              unit={m.quant.rate_unit}
                              summary={m.quant.quant_summary || m.note}
                              quant={m.quant}
                            />
                          </td>
                          <td><CiteChips ids={m.cited_source_ids} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* One drawer instance fed this card's own sources. */}
            <EvidenceDrawer
              evidence={lit.sources as unknown as Evidence[]}
              papers={rec.papers}
            />
          </>
        )}
      </div>

      {/* Model-prior track SECOND — sequence/topology estimate */}
      {rec.model_priors && rec.model_priors.length > 0 && (
        <div className={styles.sub}>
          <div className={styles.subHead}>
            <span className={styles.trackLabelMp}>Sequence prior</span>
            <span className={styles.badge}>model estimate — not citation-backed</span>
          </div>
          {rec.model_priors.map((m) => (
            <div key={m.model} className={styles.mp}>
              <div className={styles.mpHead}>
                <code>{m.model}</code> overall <Pill grade={m.overall_grade} /> <Conf level={m.overall_confidence} />
              </div>
              {m.per_isoform.map((iso) => (
                <div key={iso.isoform_id} className={styles.iso}>
                  <div>
                    <Pill grade={iso.grade} /> <code>{iso.isoform_id}</code>
                    {iso.is_canonical ? " · canonical" : ""} · <Conf level={iso.confidence} />
                  </div>
                  <div className={styles.mono}>{em(iso.topology_summary)}</div>
                  {iso.motifs && iso.motifs.length > 0 ? (
                    <div className={styles.motifs}>
                      {iso.motifs.map((mo, mi) => (
                        <span
                          key={mi}
                          className={`${styles.motif} ${mo.functional_context ? styles.motifOn : ""}`}
                          title={`${mo.region}${mo.approx_position ? ` · ${mo.approx_position}` : ""}${mo.note ? ` — ${mo.note}` : ""}`}
                        >
                          <span className={styles.motifType}>
                            {MOTIF_LABEL[mo.motif_type] ?? mo.motif_type}
                          </span>{" "}
                          <code>{mo.sequence}</code>
                          {mo.functional_context ? (
                            <span className={styles.motifOk}> ✓ cytoplasmic</span>
                          ) : (
                            <span className={styles.muted}> · {mo.region}</span>
                          )}
                        </span>
                      ))}
                    </div>
                  ) : iso.endocytic_motifs_noted ? (
                    <div className={styles.muted}>motifs: {em(iso.endocytic_motifs_noted)}</div>
                  ) : null}
                  <p>{em(iso.rationale)}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function InternalizationCard({ symbol, n }: Props) {
  const [rec, setRec] = useState<Record | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "none">("loading");
  // Client-side sort + filters for the observations table.
  const [obsSort, setObsSort] = useState<{ key: string; dir: 1 | -1 }>({
    key: "",
    dir: 1,
  });
  const [obsModeFilter, setObsModeFilter] = useState<string>("all");
  const [obsQuantOnly, setObsQuantOnly] = useState<boolean>(false);
  const toggleObsSort = (k: string) =>
    setObsSort((p) => (p.key === k ? { key: k, dir: p.dir === 1 ? -1 : 1 } : { key: k, dir: 1 }));

  useEffect(() => {
    let live = true;
    setState("loading");
    // D1-backed Worker first (the full 3,213-gene sweep), then the committed
    // static snapshot (curated / offline / Worker-down fallback). The Worker
    // returns `null` (200) for a gene not in the sweep — fall through to the
    // snapshot rather than declaring "none" prematurely.
    (async () => {
      for (const url of [
        `${API_BASE}/v1/internalization/${symbol}`,
        `/data/internalization/${symbol}.json`,
      ]) {
        try {
          const r = await fetch(url);
          if (!r.ok) continue;
          const j = await r.json();
          if (!live) return;
          if (j) {
            setRec(j as Record);
            setState("ok");
            return;
          }
        } catch {
          /* try the next source */
        }
      }
      if (live) setState("none");
    })();
    return () => {
      live = false;
    };
  }, [symbol]);

  return (
    <SectionCard
      n={n}
      eyebrow="Internalization"
      title="Internalization evidence"
      meta="PMID/DOI-anchored literature evidence by mode, followed by the sequence prior (model estimate)"
    >
      <div className={styles.root}>
      {state === "loading" && <p className={styles.muted}>Loading…</p>}
      {state === "none" && (
        <p className={styles.muted}>No internalization record for {symbol} yet.</p>
      )}

      {state === "ok" && rec && (
        <InternalizationCardBody
          rec={rec}
          obsSort={obsSort}
          toggleObsSort={toggleObsSort}
          obsModeFilter={obsModeFilter}
          setObsModeFilter={setObsModeFilter}
          obsQuantOnly={obsQuantOnly}
          setObsQuantOnly={setObsQuantOnly}
        />
      )}
      </div>
    </SectionCard>
  );
}
