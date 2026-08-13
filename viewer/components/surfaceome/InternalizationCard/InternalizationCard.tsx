"use client";

import { useEffect, useState } from "react";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./InternalizationCard.module.css";

type Grade = "high" | "moderate" | "low" | "no" | "unknown";

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
  grades_by_mode: { basal: ModeGrade; native_ligand: ModeGrade; therapeutic: ModeGrade };
  observations: Observation[];
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

function Pill({ grade, label }: { grade: Grade | string; label?: string }) {
  const g = (grade || "unknown") as string;
  return <span className={`${styles.pill} ${styles["g_" + g] ?? styles.g_unknown}`}>{label ?? g}</span>;
}

function SourceLink({ id }: { id: string }) {
  if (id?.startsWith("PMID:")) {
    const num = id.slice(5);
    return (
      <a href={`https://pubmed.ncbi.nlm.nih.gov/${num}/`} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  if (id?.startsWith("PMC:")) {
    const num = id.slice(4);
    return (
      <a href={`https://www.ncbi.nlm.nih.gov/pmc/articles/${num}/`} target="_blank" rel="noreferrer">
        {id}
      </a>
    );
  }
  return <>{id}</>;
}

export function InternalizationCard({ symbol, n }: Props) {
  const [rec, setRec] = useState<Record | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "none">("loading");

  useEffect(() => {
    let live = true;
    fetch(`/data/internalization/${symbol}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!live) return;
        if (j) {
          setRec(j as Record);
          setState("ok");
        } else setState("none");
      })
      .catch(() => live && setState("none"));
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
                <p>{em(lit.rationale)}</p>
                <div className={styles.modes}>
                  {(["basal", "native_ligand", "therapeutic"] as const).map((k) => {
                    const mg = lit.grades_by_mode[k];
                    return (
                      <div key={k} className={styles.mode}>
                        <span className={styles.modeName}>{k.replace("_", " ")}</span>{" "}
                        <Pill grade={mg.grade} /> <span className={styles.muted}>{mg.confidence}</span>
                        <p className={styles.modeRat}>{em(mg.rationale)}</p>
                      </div>
                    );
                  })}
                </div>

                <h4 className={styles.h4}>Observations ({lit.observations.length})</h4>
                <div className={styles.tablewrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>assay</th>
                        <th>mode</th>
                        <th>cell line</th>
                        <th>mag</th>
                        <th>rate</th>
                        <th>value / summary</th>
                        <th>cites</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lit.observations.map((o, i) => (
                        <tr key={i}>
                          <td>{em(o.assay_type)}</td>
                          <td>{em(o.internalization_mode)}</td>
                          <td>{em(o.cell_line)}</td>
                          <td>
                            <Pill grade={o.magnitude} />
                          </td>
                          <td>{em(o.quant.rate_metric)}</td>
                          <td>
                            {o.quant.rate_value !== null
                              ? em(`${o.quant.rate_value} ${o.quant.rate_unit ?? ""}`)
                              : em(o.quant.quant_summary)}
                          </td>
                          <td className={styles.mono}>{em(o.cited_source_ids.join(", "))}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h4 className={styles.h4}>Cited sources ({lit.sources.length})</h4>
                <ul className={styles.sources}>
                  {lit.sources.map((s) => {
                    const sp = s.spans[0];
                    return (
                      <li key={s.evidence_id} className={styles.source}>
                        <div>
                          <code className={styles.eid}>{s.evidence_id}</code>{" "}
                          {sp && <SourceLink id={sp.source.source_id} />}{" "}
                          {s.entailment_verified ? (
                            <span className={styles.ok}>✓ span-verified</span>
                          ) : (
                            <span className={styles.bad}>unverified</span>
                          )}
                        </div>
                        {sp && <blockquote>{sp.quote}</blockquote>}
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </div>
        </div>
      )}
      </div>
    </SectionCard>
  );
}
