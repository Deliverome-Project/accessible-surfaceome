"use client";

import { useEffect, useState, type ReactNode } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import { EvidenceChip } from "../EvidenceChip/EvidenceChip";
import { EvidenceDrawer } from "../EvidenceDrawer/EvidenceDrawer";
import type { Evidence } from "../../../lib/surfaceome-types";
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

interface IsoformPrior {
  isoform_id: string;
  is_canonical: boolean;
  length_aa: number | null;
  topology_summary: string;
  endocytic_motifs_noted: string | null;
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
  quant_summary: string;
}
interface Observation {
  assay_type: string;
  cell_line: string | null;
  cell_context: string;
  internalization_mode: string;
  ligand_name: string | null;
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
interface Record {
  gene_symbol: string;
  uniprot_acc: string;
  model_priors: ModelPriorTrack[];
  literature: Literature | null;
}

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
function QuantValue({
  value,
  unit,
  summary,
}: {
  value: number | null | undefined;
  unit: string | null | undefined;
  summary?: string | null;
}) {
  if (value === null || value === undefined) return em(summary);
  return (
    <>
      <strong>
        {value}
        {unit ? ` ${unit}` : ""}
      </strong>
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

// Magnitude ordinal (for the sortable "mag" column). Index signature — the card
// declares a local `Record` interface that shadows TS's generic Record<K,V>.
const MAG_RANK: { [k: string]: number } = {
  high: 4,
  moderate: 3,
  low: 2,
  none: 1,
  unknown: 0,
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

export function InternalizationCard({ symbol, n }: Props) {
  const [rec, setRec] = useState<Record | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "none">("loading");
  // Client-side sort for the observations table (empty key = original order).
  const [obsSort, setObsSort] = useState<{ key: string; dir: 1 | -1 }>({
    key: "",
    dir: 1,
  });
  const toggleObsSort = (k: string) =>
    setObsSort((p) => (p.key === k ? { key: k, dir: p.dir === 1 ? -1 : 1 } : { key: k, dir: 1 }));

  useEffect(() => {
    let live = true;
    setState("loading");
    // D1-backed Worker first (the full 3,357-gene sweep), then the committed
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

  const lit = rec?.literature ?? null;

  return (
    <SectionCard
      n={n}
      eyebrow="Internalization"
      title="Internalization evidence"
      meta="Two tracks — a sequence prior (model estimate) and PMID-anchored literature by mode"
    >
      <div className={styles.root}>
      {state === "loading" && <p className={styles.muted}>Loading…</p>}
      {state === "none" && (
        <p className={styles.muted}>No internalization record for {symbol} yet.</p>
      )}

      {state === "ok" && rec && (
        <div className={styles.body}>
          {/* Model-prior track */}
          <div className={styles.sub}>
            <div className={styles.subHead}>
              <span className={styles.trackLabelMp}>Sequence prior</span>
              <span className={styles.badge}>model estimate — not citation-backed</span>
            </div>
            {rec.model_priors.map((m) => (
              <div key={m.model} className={styles.mp}>
                <div className={styles.mpHead}>
                  <code>{m.model}</code> overall <Pill grade={m.overall_grade} /> ({m.overall_confidence})
                </div>
                {m.per_isoform.map((iso) => (
                  <div key={iso.isoform_id} className={styles.iso}>
                    <div>
                      <Pill grade={iso.grade} /> <code>{iso.isoform_id}</code>
                      {iso.is_canonical ? " · canonical" : ""} · {iso.confidence} conf
                    </div>
                    <div className={styles.mono}>{em(iso.topology_summary)}</div>
                    <div className={styles.muted}>motifs: {em(iso.endocytic_motifs_noted)}</div>
                    <p>{em(iso.rationale)}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Literature track */}
          <div className={styles.sub}>
            <div className={styles.subHead}>
              <span className={styles.trackLabelLit}>Literature</span>
              {lit && (
                <span className={styles.muted}>
                  {lit.n_papers_discovered} discovered · {lit.n_papers_fetched} fetched
                </span>
              )}
            </div>
            {!lit && <p className={styles.muted}>No literature track.</p>}
            {lit && (
              <>
                <div className={styles.overall}>
                  overall <Pill grade={lit.overall_grade} /> ({lit.overall_confidence}) · species {em(lit.species_scope)}
                </div>
                <p>{linkifyIntEvi(lit.rationale)}</p>
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
                        <Pill grade={mg.grade} /> <span className={styles.muted}>{mg.confidence}</span>
                        <p className={styles.modeRat}>{linkifyIntEvi(mg.rationale)}</p>
                      </div>
                    );
                  })}
                </div>

                <h4 className={styles.h4}>Observations ({lit.observations.length})</h4>
                <div className={styles.tablewrap}>
                  <table className={styles.table}>
                    <colgroup>
                      <col className={styles.colAssay} />
                      <col className={styles.colMode} />
                      <col className={styles.colCell} />
                      <col className={styles.colMag} />
                      <col className={styles.colMetric} />
                      <col />
                      <col className={styles.colCites} />
                    </colgroup>
                    <thead>
                      <tr>
                        <SortTh k="assay" label="assay" sort={obsSort} onSort={toggleObsSort} />
                        <SortTh k="mode" label="mode" sort={obsSort} onSort={toggleObsSort} />
                        <SortTh k="cell_line" label="cell line" sort={obsSort} onSort={toggleObsSort} />
                        <SortTh k="mag" label="mag" sort={obsSort} onSort={toggleObsSort} />
                        <SortTh k="metric" label="value type" sort={obsSort} onSort={toggleObsSort} />
                        <th>value / summary</th>
                        <th>cites</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortObs(lit.observations, obsSort).map((o, i) => (
                        <tr key={i}>
                          <td><Badge value={o.assay_type} /></td>
                          <td><Badge value={o.internalization_mode} /></td>
                          <td>{em(o.cell_line)}</td>
                          <td>
                            <Pill grade={o.magnitude} />
                          </td>
                          <td><Badge value={o.quant.rate_metric} /></td>
                          <td>
                            <QuantValue
                              value={o.quant.rate_value}
                              unit={o.quant.rate_unit}
                              summary={o.quant.quant_summary}
                            />
                          </td>
                          <td><CiteChips ids={o.cited_source_ids} /></td>
                        </tr>
                      ))}
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

                {/* No standalone "Cited sources" list — every cite in the tables
                    above is an EvidenceChip that opens the drawer below with the
                    claim, verbatim quote, and source link. */}
                {/* One drawer instance fed this card's own sources. The
                    page-level EvidenceClickDelegator dispatches the open event;
                    this drawer only opens for ``int_evi_*`` ids (the deep-dive
                    drawer ignores them — namespaces don't collide), so an
                    evidence chip in the tables above slides open the same
                    detail panel the rest of the page uses. */}
                <EvidenceDrawer
                  evidence={lit.sources as unknown as Evidence[]}
                />
              </>
            )}
          </div>
        </div>
      )}
      </div>
    </SectionCard>
  );
}
