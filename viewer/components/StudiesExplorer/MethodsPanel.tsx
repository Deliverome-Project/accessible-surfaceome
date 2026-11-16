"use client";

import { useEffect, useState } from "react";
import {
  loadMethods,
  repositoryUrl,
  STATUS_LABEL,
  type ArmMethods,
  type SourceFile,
  type StudyArm,
} from "../../lib/surface-proteomics";
import styles from "./MethodsPanel.module.css";

const pct = (x: number | null | undefined) => (x == null ? null : `${(x * 100).toFixed(1)}%`);

/** "Methods and source": what the page can't show for one study. Loads on first open. */
export function MethodsPanel({ arm }: { arm: StudyArm }) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState<Record<string, ArmMethods> | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (open && !all) loadMethods().then(setAll, () => setError(true));
  }, [open, all]);
  const m = all?.[arm.id];

  return (
    <details className={styles.panel} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className={styles.summary}>
        Methods and source{" "}
        <span className={styles.hint}>
          source tables, method and instrument, filters, sample groups, and why it is marked{" "}
          {STATUS_LABEL[arm.status]}
        </span>
      </summary>
      {error ? (
        <p className={styles.muted}>Methods detail could not be loaded.</p>
      ) : !all ? (
        open ? <p className={styles.muted}>Loading…</p> : null
      ) : !m ? (
        <p className={styles.muted}>No methods detail recorded for this dataset.</p>
      ) : (
        <MethodsBody arm={arm} m={m} />
      )}
    </details>
  );
}

export function MethodsBody({ arm, m }: { arm: StudyArm; m: ArmMethods }) {
  const groups = (m.extractions ?? []).flatMap((e) => e.sample_groups ?? []);
  return (
    <div className={styles.body}>
      <section>
        <h3 className={styles.h}>Review decision</h3>
        <dl className={styles.dl}>
          <dt>Status</dt>
          <dd>
            {STATUS_LABEL[arm.status]}
            {arm.status_reason ? `: ${arm.status_reason}` : ""}
          </dd>
          {m.rationale ? (
            <>
              <dt>Rationale</dt>
              <dd>{m.rationale}</dd>
            </>
          ) : null}
          {m.n_total_ids != null ? (
            <>
              <dt>Reference overlap</dt>
              <dd>
                {(m.n_in_reference ?? 0).toLocaleString("en-US")} of{" "}
                {m.n_total_ids.toLocaleString("en-US")} reported IDs are Canonical or Likely
                {arm.reference_overlap != null ? ` (${pct(arm.reference_overlap)})` : ""}
                {m.overlap_cutoff != null ? `; screen ${pct(m.overlap_cutoff)}` : ""}
                {m.borderline_margin ? `, with a ${Math.round(m.borderline_margin * 100)}-point allowance` : ""}
              </dd>
            </>
          ) : null}
        </dl>
      </section>

      <section>
        <h3 className={styles.h}>Method</h3>
        <dl className={styles.dl}>
          {m.method ? (
            <>
              <dt>Labeling or fractionation</dt>
              <dd>{m.method}</dd>
            </>
          ) : null}
          {m.beads ? (
            <>
              <dt>Beads and reagent</dt>
              <dd>
                {m.beads}
                {m.lot && !/^not (stated|reported)/i.test(m.lot) ? `; lot ${m.lot}` : ""}
              </dd>
            </>
          ) : null}
          {m.instrument ? (
            <>
              <dt>Instrument</dt>
              <dd>
                {m.instrument}
                {m.instrument_detail ? <span className={styles.muted}> · {m.instrument_detail}</span> : null}
              </dd>
            </>
          ) : null}
          {m.method_source || m.instrument_source ? (
            <>
              <dt>Where these come from</dt>
              <dd className={styles.muted}>
                {[m.method_source, m.instrument_source && `instrument: ${m.instrument_source}`]
                  .filter(Boolean)
                  .join("; ")}
              </dd>
            </>
          ) : null}
          {m.cell_or_tissue ? (
            <>
              <dt>Cells or tissue</dt>
              <dd>{m.cell_or_tissue}</dd>
            </>
          ) : null}
        </dl>
      </section>

      <section>
        <h3 className={styles.h}>Source tables</h3>
        <ul className={styles.files}>
          {(m.source_files ?? []).map((f, i) => (
            <li key={i}>
              <FileLine f={f} />
            </li>
          ))}
        </ul>
        <p className={styles.muted}>
          {(m.source_files ?? []).some((f) => !f.url && !f.page)
            ? "Files without a link come from the paper's supplement"
            : "Paper"}
          {arm.doi ? (
            <>
              {" "}
              (
              <a href={`https://doi.org/${arm.doi}`} target="_blank" rel="noreferrer">
                DOI {arm.doi}
              </a>
              )
            </>
          ) : arm.pmid ? (
            <>
              {" "}
              (
              <a href={`https://pubmed.ncbi.nlm.nih.gov/${arm.pmid}/`} target="_blank" rel="noreferrer">
                PMID {arm.pmid}
              </a>
              )
            </>
          ) : null}
          {arm.repository_ids.length ? (
            <>
              {" "}
              {(m.source_files ?? []).some((f) => !f.url && !f.page) ? "or its deposit" : "; deposit"}
              {arm.repository ? ` in ${arm.repository}` : ""}:{" "}
              {arm.repository_ids.map((id, i) => {
                const url = repositoryUrl(id);
                return (
                  <span key={id}>
                    {i ? ", " : ""}
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer">
                        {id}
                      </a>
                    ) : (
                      id
                    )}
                  </span>
                );
              })}
            </>
          ) : null}
          . The SHA-256 checksum under each file identifies the exact copy we read.
        </p>
        {m.parent_study ? (
          <p className={styles.muted}>Split from the registry entry {m.parent_study}, which holds the paper&apos;s other arms.</p>
        ) : null}
      </section>

      <section>
        <h3 className={styles.h}>How we read the table</h3>
        {m.sample_scope ? <p className={styles.p}>{m.sample_scope}</p> : null}
        {(m.extractions ?? []).map((e, i) => (
          <dl key={i} className={styles.dl}>
            {e.file ? (
              <>
                <dt>Table</dt>
                <dd className={styles.mono}>{e.file}</dd>
              </>
            ) : null}
            <dt>ID columns</dt>
            <dd className={styles.mono}>
              {[e.accession_column, e.gene_column].filter(Boolean).join(" · ") || "—"}
            </dd>
            {e.filters?.length ? (
              <>
                <dt>Row filters</dt>
                <dd>
                  <ul className={styles.rules}>
                    {e.filters.map((r) => (
                      <li key={r} className={styles.mono}>
                        {r}
                      </li>
                    ))}
                  </ul>
                </dd>
              </>
            ) : null}
          </dl>
        ))}
        {groups.length ? (
          <div className={styles.scroll}>
            <table className={styles.table}>
              <caption className={styles.caption}>
                Sample-to-group mapping: a protein is listed for a group when at least “min observed” of its columns
                have a value{groups.some((g) => g.detection_floor != null) ? " above the detection floor" : ""}.
              </caption>
              <thead>
                <tr>
                  <th>Cells</th>
                  <th>Condition</th>
                  <th>Columns</th>
                  <th className={styles.num}>Min observed</th>
                  {groups.some((g) => g.detection_floor != null) ? <th className={styles.num}>Floor</th> : null}
                  <th>Counts toward membership</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g, i) => (
                  <tr key={i}>
                    <td>{g.cell_type ?? "—"}</td>
                    <td>{g.condition ?? "—"}</td>
                    <td className={styles.mono}>{g.columns.join(", ")}</td>
                    <td className={styles.num}>{g.min_observed ?? "—"}</td>
                    {groups.some((x) => x.detection_floor != null) ? (
                      <td className={styles.num}>{g.detection_floor ?? "—"}</td>
                    ) : null}
                    <td>{g.use_for_membership === false ? "no, measurement only" : "yes"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {m.target_species || m.species_note || m.n_species_excluded || m.n_species_unresolved ? (
        <section>
          <h3 className={styles.h}>Species</h3>
          <dl className={styles.dl}>
            {m.target_species ? (
              <>
                <dt>Kept</dt>
                <dd>{m.target_species} only; non-human IDs are dropped, never converted by ortholog</dd>
              </>
            ) : null}
            {m.n_species_excluded != null || m.n_species_unresolved != null ? (
              <>
                <dt>Dropped</dt>
                <dd>
                  {(m.n_species_excluded ?? 0).toLocaleString("en-US")} non-human,{" "}
                  {(m.n_species_unresolved ?? 0).toLocaleString("en-US")} whose species could not be resolved
                </dd>
              </>
            ) : null}
            {m.species_note ? (
              <>
                <dt>Note</dt>
                <dd>{m.species_note}</dd>
              </>
            ) : null}
          </dl>
        </section>
      ) : null}
    </div>
  );
}

function FileLine({ f }: { f: SourceFile }) {
  const href = f.url ?? f.page;
  const name = f.file ?? "file";
  return (
    <>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className={styles.mono}>
          {name}
        </a>
      ) : (
        <span className={styles.mono}>{name}</span>
      )}
      {f.sheet != null ? <span>, sheet “{f.sheet}”</span> : null}
      {f.archive ? <span className={styles.muted}> (in {f.archive})</span> : null}
      {f.page && !f.url ? <span className={styles.muted}> (supplement page; download by hand)</span> : null}
      {f.repository_path ? <div className={styles.muted}>{f.repository_path}</div> : null}
      {f.note ? <div className={styles.muted}>{f.note}</div> : null}
      {f.derived_from?.length ? (
        <div className={styles.muted}>
          Rebuilt from {f.derived_from.map((d) => d.file).join(", ")}
          {f.derivation ? `: ${f.derivation}` : ""}
        </div>
      ) : f.derivation ? (
        <div className={styles.muted}>{f.derivation}</div>
      ) : null}
      {f.sha256 ? <div className={`${styles.muted} ${styles.hash}`}>SHA-256 {f.sha256}</div> : null}
    </>
  );
}
