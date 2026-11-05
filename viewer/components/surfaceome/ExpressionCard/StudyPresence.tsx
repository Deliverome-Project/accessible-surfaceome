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
  countedRank,
  studyHref,
  type ArmStatus,
  type StudyArm,
  type StudyIndex,
} from "../../../lib/surface-proteomics";
import { InfoTip } from "../../InfoTip/InfoTip";
import tip from "../../InfoTip/InfoTip.module.css";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./StudyPresence.module.css";

interface Props {
  uniprotAcc: string;
  symbol: string;
}

const GROUPS: { key: string; label: string; desc: string; statuses: ArmStatus[] }[] = [
  {
    key: "counted",
    label: "Surface evidence",
    desc: "Proteins labeled on intact, living cells, in datasets that passed our quality checks. These count.",
    statuses: ["core", "provisional"],
  },
  {
    key: "held",
    label: "Surface experiments we don't count",
    desc: "Also intact-cell labeling, but the list is mostly background (below screen) or the published table can't be read per protein (held).",
    statuses: ["held", "below_screen"],
  },
  {
    key: "comparator",
    label: "Membrane preps, for context",
    desc: "Cells broken open and membranes purified, or labels that reach inside the cell. Shows a protein is on a membrane, not that it faces outward.",
    statuses: ["comparator"],
  },
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
 * screen and comparator arms (membrane fractionation, inner-leaflet
 * labeling) are drawn separately and labelled as not counted.
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
  const rank = countedRank(data.index.counted_detection_hist, countedHits.length);
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
          {rank ? (
            <>
              <strong>How {countedHits.length} compares.</strong>{" "}
              {rank.total.toLocaleString("en-US")} proteins are detected by at least one counted
              dataset; the median one is detected by {rank.median}. {symbol} is detected by more
              counted datasets than {Math.floor(rank.below * 100)}% of them.
              <br />
              <br />
            </>
          ) : null}
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
          <strong>Comparators</strong> (membrane fractionation, or labeling
          that reaches the inner side of the membrane) show that a protein
          co-purifies with membranes, not that it is reachable from outside
          the cell.
          <br />
          <br />
          Not detected means the protein is absent from that study&apos;s
          list. It is not evidence the protein is absent from the cell
          surface. Snapshot: {data.index.snapshot}.
        </InfoTip>
      </div>
      {rank ? (
        <p className={styles.rank}>
          <span className={styles.rankBar} aria-hidden="true">
            <span style={{ width: `${Math.max(2, rank.below * 100)}%` }} />
          </span>
          <span>
            Detected by more counted datasets than{" "}
            <strong>{Math.floor(rank.below * 100)}%</strong> of the{" "}
            {rank.total.toLocaleString("en-US")} proteins any counted dataset found (the median
            protein is found by {rank.median}).
          </span>
        </p>
      ) : null}

      <div className={styles.strip} role="list" aria-label="Detection per dataset">
        {GROUPS.map((g) => {
          const items = arms.filter((x) => g.statuses.includes(x.arm.status));
          if (items.length === 0) return null;
          return (
            <div key={g.key} className={styles.group} role="listitem">
              <span className={styles.groupLabel}>
                <span className={styles.groupName}>{g.label}</span>
                <span className={styles.groupDesc}>{g.desc}</span>
              </span>
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
  const counted = isCounted(arm);
  const label =
    `${shortCitation(arm)}: ${arm.name}. ${hit ? "Detected" : "Not detected"}; ` +
    `${STATUS_LABEL[arm.status]}${counted ? "" : ", not counted"}`;
  const cls = [styles.dot, hit ? `${styles[arm.method_class]} ${styles.hit}` : "", counted ? "" : styles.dim]
    .filter(Boolean)
    .join(" ");
  // Styled popover (the InfoTip one) rather than the OS title bubble.
  return (
    <span className={tip.wrap} data-infotip="">
      <Link href={studyHref([arm.id])} className={cls} aria-label={label} />
      <span role="tooltip" className={`${tip.popover} ${styles.dotTip}`}>
        <strong className={hit ? styles.tipHit : styles.tipMiss}>
          {hit ? "Detected" : "Not detected"}
        </strong>{" "}
        in {shortCitation(arm)}
        {arm.journal ? <span className={styles.tipMuted}> · {arm.journal}</span> : null}
        <br />
        {arm.name}
        <br />
        <span className={styles.tipMuted}>Method:</span> {METHOD_CLASS_LABEL[arm.method_class]} (
        {arm.family_label})
        <br />
        <span className={styles.tipMuted}>Cells:</span> {arm.sample ?? "—"}
        <br />
        <span className={styles.tipMuted}>Proteins in list:</span> {arm.n_proteins.toLocaleString("en-US")}
        {arm.reference_overlap != null
          ? ` · ${Math.round(arm.reference_overlap * 100)}% known surface`
          : ""}
        <br />
        <span className={styles.tipMuted}>Status:</span> {STATUS_LABEL[arm.status]},{" "}
        {counted ? "counted as surface evidence" : "not counted"}
        <br />
        <span className={styles.tipMuted}>Click to open this dataset&apos;s protein list.</span>
      </span>
    </span>
  );
}
