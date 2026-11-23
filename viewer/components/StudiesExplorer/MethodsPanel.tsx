"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  loadMethods,
  repositoryUrl,
  STATUS_LABEL,
  type ArmMethods,
  type Extraction,
  type SourceFile,
  type StudyArm,
} from "../../lib/surface-proteomics";
import { tooltips } from "../../lib/tooltips";
import { InfoTip } from "../InfoTip/InfoTip";
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
          <dt>
            Status{" "}
            <InfoTip wide align="start" label="About Status">
              {tooltips.arm_status}
            </InfoTip>
          </dt>
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
              <dt>
                Reference overlap{" "}
                <InfoTip wide align="start" label="About the reference">
                  {tooltips.reference}
                </InfoTip>
              </dt>
              <dd>
                {(m.n_in_reference ?? 0).toLocaleString("en-US")} of{" "}
                {m.n_total_ids.toLocaleString("en-US")} reported IDs are Canonical or Likely
                {arm.reference_overlap != null ? ` (${pct(arm.reference_overlap)})` : ""}
                {m.overlap_cutoff != null ? `; screen ${pct(m.overlap_cutoff)}` : ""}
                {m.borderline_margin ? `, with a ${Math.round(m.borderline_margin * 100)}-point allowance` : ""}
              </dd>
            </>
          ) : null}
          {arm.screen_basis === "abundance" && arm.abundance_share != null ? (
            <>
              <dt>Abundance screen</dt>
              <dd>
                {pct(arm.abundance_share)} of its length-corrected protein amount is Canonical or
                Likely; screen {pct(arm.abundance_cutoff ?? 0.25)}. This dataset reports
                per-protein amounts, so it is judged on them rather than on its protein list.
                {arm.auroc_rescued && arm.abundance_auroc != null
                  ? ` It counts through the AUROC rescue: its amounts rank Canonical or Likely proteins above its other proteins (AUROC ${arm.abundance_auroc.toFixed(2)}, rescue ${(arm.auroc_rescue_cutoff ?? 0.58).toFixed(2)}), so a long tail of faint background does not hold it back.`
                  : ""}
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
              <dt>Where we read these</dt>
              <dd>
                {m.method_source ? <p className={styles.sentence}>{linkIds(m.method_source)}</p> : null}
                {m.instrument_source ? <p className={styles.sentence}>{linkIds(m.instrument_source)}</p> : null}
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
              <FileLine f={f} extraction={extractionFor(f, m.extractions)} />
            </li>
          ))}
        </ul>
        <PaperLine arm={arm} />
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

      <AccessionResolution />

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

/** The paper and its data deposit, linked. */
function PaperLine({ arm }: { arm: StudyArm }) {
  if (!arm.doi && !arm.pmid && !arm.repository_ids.length) return null;
  return (
    <p className={styles.muted}>
      {arm.doi ? (
        <>
          Paper:{" "}
          <a href={`https://doi.org/${arm.doi}`} target="_blank" rel="noreferrer">
            DOI {arm.doi}
          </a>
          .{" "}
        </>
      ) : arm.pmid ? (
        <>
          Paper:{" "}
          <a href={`https://pubmed.ncbi.nlm.nih.gov/${arm.pmid}/`} target="_blank" rel="noreferrer">
            PMID {arm.pmid}
          </a>
          .{" "}
        </>
      ) : null}
      {arm.repository_ids.length ? (
        <>
          Data deposit{arm.repository ? ` in ${arm.repository}` : ""}:{" "}
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
          .
        </>
      ) : null}
    </p>
  );
}

const PERMALINK = "https://github.com/Deliverome-Project/accessible-surfaceome/blob/15a22d8c8c4df322e5e83e8d142de14a6ff7325c";

/** How reported accessions were matched to genes, with links to the catalog code that defines each step. */
function AccessionResolution() {
  const code = (path: string, line: number, label: string) => (
    <a href={`${PERMALINK}/${path}#L${line}`} target="_blank" rel="noreferrer" className={styles.mono}>
      {label}
    </a>
  );
  return (
    <section>
      <h3 className={styles.h}>How accessions were resolved</h3>
      <ol className={styles.steps}>
        <li>
          Each reported UniProt accession is brought up to date with UniProt&apos;s accession history (the
          release files sec_ac.txt and delac_sp.txt of January 28, 2026): a deleted Swiss-Prot entry is dropped, a
          merged (secondary) accession becomes its current primary, and a split accession becomes its human
          successor; one split into several human successors is not counted, as in the catalog (
          {code("src/accessible_surfaceome/merge/normalize.py", 28, "merge/normalize.py")} and{" "}
          {code("src/accessible_surfaceome/merge/__init__.py", 234, "merge/__init__.py")}).
        </li>
        <li>
          The current accession is matched to its gene through the HGNC gene ID (HGNC&apos;s own UniProt cross-reference
          first, then UniProt&apos;s HGNC cross-reference), and replaced by that gene&apos;s canonical accession in the
          catalog. Never via a gene symbol; an accession that reaches no gene, or more than one, is kept as reported.
          See {code("scripts/build/build_surface_proteomics_studies.py", 673, "normalize_accessions")} and{" "}
          {code("src/accessible_surfaceome/tools/gene_lookup.py", 706, "resolve_by_hgnc_id")}.
        </li>
        <li>
          A table that reports only gene symbols is matched to approved HGNC symbols with MyGene (aliases and previous
          symbols resolve; ambiguous ones do not), then to the gene&apos;s HGNC ID and canonical accession, as in{" "}
          {code("src/accessible_surfaceome/merge/gene_symbols.py", 87, "merge/gene_symbols.py")}.
        </li>
      </ol>
    </section>
  );
}

/** The extraction that reads this file, matched by file name. */
function extractionFor(f: SourceFile, extractions: Extraction[] | undefined): Extraction | undefined {
  return (extractions ?? []).find((e) => e.file && e.file === f.file);
}

const external = (href: string, label: ReactNode, mono = false) => (
  <a href={href} target="_blank" rel="noreferrer" className={mono ? styles.mono : undefined}>
    {label}
  </a>
);

/** Where one source file came from, in words: downloaded, saved by hand, deposited, or derived by us. */
function Origin({ f }: { f: SourceFile }) {
  if (f.derived_from?.length || f.derivation) {
    return (
      <>
        Derived by us
        {f.derived_from?.length ? (
          <>
            {" "}
            from{" "}
            {f.derived_from.map((d, i) => (
              <span key={i}>
                {i ? ", " : ""}
                {d.url ? external(d.url, d.file ?? d.url, true) : <span className={styles.mono}>{d.file}</span>}
                {d.sheet != null ? ` (sheet “${d.sheet}”)` : ""}
              </span>
            ))}
          </>
        ) : null}
        {f.derivation ? `: ${f.derivation.replace(/\.?$/, ".")}` : "."}
      </>
    );
  }
  if (f.url) {
    return (
      <>
        {f.archive ? <>Inside {f.archive}, downloaded from </> : <>Downloaded from </>}
        {external(f.url, f.url)}.
      </>
    );
  }
  if (f.page) {
    return <>Saved by hand from {external(f.page, f.page)}, which offers no direct download link.</>;
  }
  if (f.repository_path) return <>Repository file {f.repository_path}.</>;
  return <>Where this file came from is not yet recorded.</>;
}

/** What we read from the file: the sheet and the columns. */
function ReadFrom({ f, e }: { f: SourceFile; e?: Extraction }) {
  const cols = [
    e?.accession_column && `${e.accession_column} (accession)`,
    e?.gene_column && `${e.gene_column} (gene)`,
  ].filter(Boolean);
  const sampleCols = (e?.sample_groups ?? []).reduce((n, g) => n + g.columns.length, 0);
  if (f.sheet == null && !cols.length) return null;
  return (
    <div>
      Read {f.sheet != null ? <>sheet “{f.sheet}”</> : <>the table</>}
      {cols.length ? (
        <>
          , columns <span className={styles.mono}>{cols.join(", ")}</span>
        </>
      ) : null}
      {sampleCols ? `, plus ${sampleCols} sample column${sampleCols === 1 ? "" : "s"} (below)` : ""}.
    </div>
  );
}

function FileLine({ f, extraction }: { f: SourceFile; extraction?: Extraction }) {
  return (
    <>
      <span className={styles.mono}>{f.file ?? "file"}</span>
      <div>
        <Origin f={f} />
      </div>
      <ReadFrom f={f} e={extraction} />
      {f.note ? <div className={styles.muted}>{f.note}</div> : null}
      {f.sha256 ? (
        <div className={styles.muted}>
          SHA-256 of the exact copy we read: <span className={styles.hash}>{f.sha256}</span>
        </div>
      ) : null}
    </>
  );
}

/** Identifiers we link inside the source sentences. */
const ID_PATTERN = /\b(PMC\d+|R?PXD\d{6}|MSV\d{9}|JPST\d{6}|10\.\d{4,9}\/[^\s;,()']+[^\s;,()'.])/g;

function idHref(id: string): string | null {
  if (id.startsWith("PMC")) return `https://pmc.ncbi.nlm.nih.gov/articles/${id}/`;
  if (id.startsWith("10.")) return `https://doi.org/${id.replace(/v\d+$/, "")}`;
  return repositoryUrl(id);
}

/** A source sentence with its PMC ids, DOIs and repository accessions linked. */
export function linkIds(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(ID_PATTERN)) {
    const id = match[0];
    const href = idHref(id);
    if (!href) continue;
    out.push(text.slice(last, match.index));
    out.push(
      <a key={match.index} href={href} target="_blank" rel="noreferrer">
        {id}
      </a>,
    );
    last = (match.index ?? 0) + id.length;
  }
  out.push(text.slice(last));
  return out;
}
