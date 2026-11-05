"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  isCounted,
  loadPresence,
  METHOD_CLASS_LABEL,
  paperUrl,
  shortCitation,
  STATUS_HELP,
  STATUS_LABEL,
  STUDIES_PATH,
  studyHref,
  type ArmStatus,
  type StudyArm,
  type StudyIndex,
} from "../../../lib/surface-proteomics";
import { InfoTip } from "../../InfoTip/InfoTip";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./StudyPresence.module.css";

interface Props {
  uniprotAcc: string;
  symbol: string;
}

const GROUPS: { key: string; label: string; statuses: ArmStatus[] }[] = [
  { key: "counted", label: "Counted · intact-cell labeling", statuses: ["core", "provisional"] },
  { key: "held", label: "Not counted · held or below screen", statuses: ["held", "below_screen"] },
  { key: "comparator", label: "Comparators · not extracellular evidence", statuses: ["comparator"] },
];

export function statusTone(s: ArmStatus) {
  if (s === "core") return "success" as const;
  if (s === "provisional") return "teal" as const;
  if (s === "comparator") return "amber" as const;
  return "neutral" as const;
}

/**
 * Presence of this protein across published cell-surface proteomics
 * studies (the S3E8 compendium), one dot per study arm. Only admitted
 * intact-cell labeling arms count as surface detections; held, below-
 * screen and comparator arms (membrane fractionation, lysate
 * glycoproteomes) are drawn separately and labelled as not counted.
 */
export function StudyPresence({ uniprotAcc, symbol }: Props) {
  const [data, setData] = useState<{ index: StudyIndex; hits: Set<number> } | null>(null);
  const [error, setError] = useState(false);
  const [showOther, setShowOther] = useState(false);
  const [showMissing, setShowMissing] = useState(false);

  useEffect(() => {
    let live = true;
    loadPresence(uniprotAcc)
      .then(({ index, entry }) => {
        if (live) setData({ index, hits: new Set(entry?.a ?? []) });
      })
      .catch(() => live && setError(true));
    return () => {
      live = false;
    };
  }, [uniprotAcc]);

  const summary = useMemo(() => {
    if (!data) return null;
    const arms = data.index.arms.map((arm, i) => ({ arm, i, hit: data.hits.has(i) }));
    const counted = arms.filter((x) => isCounted(x.arm));
    const countedHits = counted.filter((x) => x.hit);
    const pubs = new Set(counted.map((x) => x.arm.publication));
    const pubHits = new Set(countedHits.map((x) => x.arm.publication));
    const otherHits = arms.filter((x) => x.hit && !isCounted(x.arm)).length;
    return { arms, counted, countedHits, pubs, pubHits, otherHits };
  }, [data]);

  if (error) {
    return <p className={styles.empty}>Study presence data could not be loaded.</p>;
  }
  if (!data || !summary) {
    return <p className={styles.empty}>Loading study presence…</p>;
  }

  const { arms, counted, countedHits, pubs, pubHits, otherHits } = summary;
  const rows = arms
    .filter((x) => (showMissing || x.hit) && (showOther || isCounted(x.arm)))
    .sort(
      (a, b) =>
        Number(b.hit) - Number(a.hit) ||
        Number(isCounted(b.arm)) - Number(isCounted(a.arm)) ||
        (b.arm.year ?? 0) - (a.arm.year ?? 0),
    );

  return (
    <div className={styles.wrap}>
      <div className={`label-mono ${styles.subhead}`}>
        Published surface-proteomics studies
        <span className={styles.rollup}>
          detected in {countedHits.length} of {counted.length} counted datasets ({pubHits.size} of{" "}
          {pubs.size} papers)
          {otherHits > 0 ? ` · listed in ${otherHits} not-counted dataset${otherHits === 1 ? "" : "s"}` : ""}
        </span>
        <InfoTip wide label="About study presence">
          Whether {symbol} ({uniprotAcc}) appears in the protein list of each
          human cell-surface proteomics dataset we collected and audited
          ({data.index.n_arms} datasets from {data.index.n_publications} papers).
          Proteins are matched by UniProt accession, after mapping retired
          accessions to their current entry.
          <br />
          <br />
          <strong>Counted</strong> datasets label proteins on intact cells and
          pass review (core or provisional). <strong>Held</strong> and{" "}
          <strong>below screen</strong> datasets are listed but not counted.{" "}
          <strong>Comparators</strong> (membrane fractionation, lysate
          glycoproteomes) show that a protein co-purifies with membranes,
          not that it is reachable from outside the cell.
          <br />
          <br />
          Not detected means the protein is absent from that study&apos;s
          list. It is not evidence the protein is absent from the cell
          surface. Snapshot: {data.index.snapshot}.
        </InfoTip>
      </div>

      <div className={styles.strip} role="list" aria-label="Detection per dataset">
        {GROUPS.map((g) => {
          const items = arms.filter((x) => g.statuses.includes(x.arm.status));
          if (items.length === 0) return null;
          return (
            <div key={g.key} className={styles.group} role="listitem">
              <span className={styles.groupLabel}>{g.label}</span>
              <span className={styles.dots}>
                {items.map(({ arm, hit }) => (
                  <Dot key={arm.id} arm={arm} hit={hit} />
                ))}
              </span>
            </div>
          );
        })}
      </div>
      <p className={styles.legend}>
        <span className={`${styles.dot} ${styles.intact_cell} ${styles.hit}`} /> intact-cell labeling
        <span className={`${styles.dot} ${styles.fractionation} ${styles.hit}`} /> membrane fractionation
        <span className={`${styles.dot} ${styles.lysate} ${styles.hit}`} /> lysate
        <span className={styles.dot} /> not detected
      </p>

      {rows.length > 0 ? (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Study</th>
              <th>Detected</th>
              <th>Method</th>
              <th>Cell type / sample</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ arm, hit }) => {
              const url = paperUrl(arm);
              return (
                <tr key={arm.id} className={isCounted(arm) ? undefined : styles.notCounted}>
                  <td>
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer">
                        {shortCitation(arm)}
                      </a>
                    ) : (
                      shortCitation(arm)
                    )}
                    {arm.pmid ? <span className={styles.pmid}> PMID {arm.pmid}</span> : null}
                    <div className={styles.armName}>{arm.name}</div>
                  </td>
                  <td>{hit ? "Yes" : "No"}</td>
                  <td>
                    {METHOD_CLASS_LABEL[arm.method_class]}
                    <div className={styles.armName}>{arm.family_label}</div>
                  </td>
                  <td>{arm.sample}</td>
                  <td>
                    <StatusPill size="sm" tone={statusTone(arm.status)} title={STATUS_HELP[arm.status]}>
                      {STATUS_LABEL[arm.status]}
                    </StatusPill>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className={styles.empty}>
          {data.hits.size === 0
            ? `Not listed in any of the ${arms.length} datasets.`
            : "Not detected in any counted dataset; tick “include not-counted datasets” to see where it was listed."}
        </p>
      )}
      <p className={styles.actions}>
        <label>
          <input type="checkbox" checked={showOther} onChange={(e) => setShowOther(e.target.checked)} />{" "}
          include not-counted datasets
        </label>
        <label>
          <input type="checkbox" checked={showMissing} onChange={(e) => setShowMissing(e.target.checked)} />{" "}
          include datasets where it was not detected
        </label>
        <span aria-hidden="true">·</span>
        <Link href={STUDIES_PATH}>Explore all surface proteomics data →</Link>
      </p>
    </div>
  );
}

function Dot({ arm, hit }: { arm: StudyArm; hit: boolean }) {
  const label =
    `${shortCitation(arm)} — ${arm.name}\n${METHOD_CLASS_LABEL[arm.method_class]} · ${arm.sample ?? ""}\n` +
    `${hit ? "Detected" : "Not detected"} · ${STATUS_LABEL[arm.status]}${isCounted(arm) ? "" : " (not counted)"}`;
  const cls = [styles.dot, hit ? `${styles[arm.method_class]} ${styles.hit}` : "", isCounted(arm) ? "" : styles.dim]
    .filter(Boolean)
    .join(" ");
  return (
    <Link href={studyHref([arm.id])} className={cls} title={label} aria-label={label} />
  );
}
