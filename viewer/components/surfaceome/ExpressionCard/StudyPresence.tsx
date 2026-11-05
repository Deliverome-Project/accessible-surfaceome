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
  FAMILY_ORDER,
  formatQuant,
  ordinalPct,
  shareBelow,
  studyHref,
  TIER_LABEL,
  tierOf,
  type ArmStatus,
  type TierCode,
  type StudyArm,
  type StudyIndex,
} from "../../../lib/surface-proteomics";
import { InfoTip } from "../../InfoTip/InfoTip";
import { HoverTip } from "../_shared/HoverTip";
import tip from "../../InfoTip/InfoTip.module.css";
import { FamilyChip } from "../../StudiesExplorer/FamilyChip";
import { SortableHeader } from "../_shared/SortableHeader";
import { useTableSort, type SortValue } from "../_shared/useTableSort";
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
    desc: "Also intact-cell labeling, but most of the list is intracellular background (high background), or the published table can't tell us which proteins were detected (held).",
    statuses: ["held", "below_screen"],
  },
  {
    key: "comparator",
    label: "Membrane preps, for context",
    desc: "Cells broken open and membranes purified, or labels that reach inside the cell. Shows a protein is on a membrane, not that it faces outward.",
    statuses: ["comparator"],
  },
];

type RowSort = "study" | "found" | "amount" | "method" | "family" | "sample" | "status";
const STATUS_ORDER: ArmStatus[] = ["core", "provisional", "held", "below_screen", "comparator"];
const pct = (x: number) => `${Math.floor(x * 100)}%`;

/** "Detected in 18 of 25 lines", with the lines listed on hover. */
function LineDetail({ lines, hitLines }: { lines: string[]; hitLines: number[] }) {
  const hitSet = new Set(hitLines);
  return (
    <div className={styles.lineDetail}>
      Detected in <strong>{hitLines.length} of {lines.length}</strong> lines{" "}
      <InfoTip label="Which cell lines">
        <span className={styles.tipLine}>
          <strong>Detected:</strong> {hitLines.map((j) => lines[j]).join(", ") || "none"}
        </span>
        <span className={styles.tipLine}>
          <strong>Not detected:</strong>{" "}
          {lines.filter((_, j) => !hitSet.has(j)).join(", ") || "none"}
        </span>
      </InfoTip>
    </div>
  );
}

/** The dataset's own value for the protein, its unit, and its within-dataset rank. */
function Amount({ arm, hit, q }: { arm: StudyArm; hit: boolean; q?: [number, number] }) {
  if (!hit) return <span className={styles.muted}>—</span>;
  if (!q || !arm.quant_unit) {
    return (
      <HoverTip tip="This dataset publishes a protein list without a per-protein quantity.">
        <span className={styles.muted}>list only</span>
      </HoverTip>
    );
  }
  const [value, pct] = q;
  return (
    <div className={styles.amount}>
      <div>
        <strong>{formatQuant(value)}</strong> <span className={styles.unit}>{arm.quant_unit}</span>
      </div>
      <HoverTip
        tip={`Value: ${arm.quant_note}. Percentile: rank among the ${arm.n_quantified?.toLocaleString("en-US")} proteins this dataset quantified. Values aren't comparable across datasets; percentiles are.`}
      >
      <div className={styles.pctLine}>
        <span className={styles.pctBar} aria-hidden="true">
          <span style={{ width: `${Math.max(2, pct)}%` }} />
        </span>
        {ordinalPct(pct)}
      </div>
      </HoverTip>
    </div>
  );
}

function RankLine({ share, text }: { share: number; text: React.ReactNode }) {
  return (
    <p className={styles.rank}>
      <span className={styles.rankBar} aria-hidden="true">
        <span style={{ width: `${Math.max(2, share * 100)}%` }} />
      </span>
      <span>{text}</span>
    </p>
  );
}

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
 * labeling) are drawn separately and labeled as not counted.
 */
export function StudyPresence({ uniprotAcc, symbol }: Props) {
  const [data, setData] = useState<{
    index: StudyIndex;
    hits: Set<number>;
    tier: TierCode | "none";
    lines: Record<string, number[]>;
    quant: Record<string, [number, number]>;
  } | null>(null);
  const [error, setError] = useState(false);
  const [showOther, setShowOther] = useState(false);
  const [showMissing, setShowMissing] = useState(false);
  const { sortKey, sortDir, onSort, ariaSort, sortRows } = useTableSort<RowSort>();

  useEffect(() => {
    let live = true;
    loadPresence(uniprotAcc)
      .then(({ index, entry }) => {
        if (live)
          setData({
            index,
            hits: new Set(entry?.a ?? []),
            tier: entry ? tierOf(entry) : "none",
            lines: entry?.l ?? {},
            quant: entry?.q ?? {},
          });
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
  const hists = data.index.cohort_detection_hist;
  const k = countedHits.length;
  const vsCohort = shareBelow(hists?.all, k);
  const vsTier = data.tier !== "none" ? shareBelow(hists?.[data.tier], k) : null;
  const filtered = arms.filter((x) => (showMissing || x.hit) && (showOther || isCounted(x.arm)));
  const rows =
    sortKey === null
      ? [...filtered].sort(
          (a, b) =>
            Number(b.hit) - Number(a.hit) ||
            Number(isCounted(b.arm)) - Number(isCounted(a.arm)) ||
            (b.arm.year ?? 0) - (a.arm.year ?? 0),
        )
      : sortRows(filtered, {
          study: (r) => shortCitation(r.arm),
          found: (r) => Number(r.hit),
          amount: (r) => data.quant[String(r.i)]?.[1] ?? -1,
          method: (r) => r.arm.method_class,
          family: (r) => r.arm.family_label,
          sample: (r) => r.arm.sample ?? "",
          status: (r) => STATUS_ORDER.indexOf(r.arm.status),
        } satisfies Record<RowSort, (r: (typeof filtered)[number]) => SortValue>);
  const th = (key: RowSort, text: string) => (
    <th aria-sort={ariaSort(key)}>
      <SortableHeader k={key} active={sortKey === key} direction={sortDir} onSort={onSort}>
        {text}
      </SortableHeader>
    </th>
  );

  return (
    <div className={styles.wrap}>
      <div className={`label-mono ${styles.subhead}`}>
        Published surface-proteomics studies
        <span className={styles.rollup}>
          Detected in {countedHits.length} of {counted.length} counted datasets ({pubHits.size} of{" "}
          {pubs.size} papers)
          {otherHits > 0 ? ` · listed in ${otherHits} not-counted dataset${otherHits === 1 ? "" : "s"}` : ""}
        </span>
        <InfoTip wide label="About study presence">
          Whether {symbol} ({uniprotAcc}) appears in the protein list of each
          human cell-surface proteomics dataset we collected and audited
          ({data.index.n_arms} datasets from {data.index.n_publications} papers).
          Each reported accession is mapped to the gene&apos;s canonical UniProt
          entry through its HGNC ID, the same resolver the rest of the site uses.
          <br />
          <br />
          <strong>Counted</strong> datasets label proteins on intact cells and
          pass review (core or provisional). <strong>Held</strong> and{" "}
          <strong>high-background</strong> datasets are listed but not counted.{" "}
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
      {vsCohort ? (
        <div className={styles.rankBox}>
          <RankLine
            share={vsCohort.below}
            text={
              <>
                Found in more counted datasets than <strong>{pct(vsCohort.below)}</strong> of the{" "}
                {vsCohort.total.toLocaleString("en-US")} surface candidates we deep-dived
              </>
            }
          />
          {vsTier && data.tier !== "none" ? (
            <RankLine
              share={vsTier.below}
              text={
                <>
                  and than <strong>{pct(vsTier.below)}</strong> of the{" "}
                  {vsTier.total.toLocaleString("en-US")} proteins in its tier,{" "}
                  {TIER_LABEL[data.tier]}
                </>
              }
            />
          ) : null}
        </div>
      ) : null}

      <div className={styles.strip} role="list" aria-label="Detection per dataset">
        {GROUPS.map((g) => {
          const items = arms.filter((x) => g.statuses.includes(x.arm.status));
          if (items.length === 0) return null;
          return (
            <div key={g.key} className={styles.group} role="listitem">
              <span className={styles.groupLabel}>
                <span className={styles.groupName}>{g.label}</span>
                <InfoTip label={`About ${g.label}`}>{g.desc}</InfoTip>
                <span className={styles.groupStatus}>
                  {g.statuses.map((st) => STATUS_LABEL[st]).join(" + ")}
                </span>
              </span>
              <span className={styles.dots}>
                {/* One cluster per labeling technology, in a fixed order. */}
                {FAMILY_ORDER.map((fam) => {
                  const inFam = items
                    .filter((x) => x.arm.family === fam)
                    .sort((a, b) => Number(b.hit) - Number(a.hit) || (b.arm.year ?? 0) - (a.arm.year ?? 0));
                  if (!inFam.length) return null;
                  return (
                    <span
                      key={fam}
                      className={styles.famCluster}
                      aria-label={`${inFam[0].arm.family_label}: ${inFam.filter((x) => x.hit).length} of ${inFam.length} detected`}
                    >
                      {inFam.map(({ arm, hit, i }) => (
                        <Dot key={arm.id} arm={arm} hit={hit} q={data.quant[String(i)]} />
                      ))}
                    </span>
                  );
                })}
              </span>
            </div>
          );
        })}
      </div>
      <p className={styles.legend}>
        {FAMILY_ORDER.filter((fam) => arms.some((x) => x.arm.family === fam)).map((fam) => (
          <span key={fam} className={styles.legendItem}>
            <span className={`${styles.dot} ${styles.hit} ${styles[`fam_${fam.replace(/-/g, "_")}`]}`} />
            {arms.find((x) => x.arm.family === fam)?.arm.family_label}
          </span>
        ))}
        <span className={styles.legendItem}>
          <span className={styles.dot} /> not detected
        </span>
      </p>

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

      {rows.length > 0 ? (
        <div className={styles.tableScroll}>
        <table className={`${styles.table} ${styles.fixedTable}`}>
          {/* Fixed widths, so toggling which rows show never re-flows the columns. */}
          <colgroup>
            <col style={{ width: "12rem" }} />
            <col style={{ width: "6.75rem" }} />
            <col style={{ width: "10.5rem" }} />
            <col style={{ width: "9rem" }} />
            <col style={{ width: "13.75rem" }} />
            <col />
            <col style={{ width: "10rem" }} />
          </colgroup>
          <thead>
            <tr>
              {th("study", "Study")}
              {th("found", "Detected")}
              {th("amount", "Amount in dataset")}
              {th("method", "Method")}
              {th("family", "Chemistry")}
              {th("sample", "Cell type / sample")}
              {th("status", "Status")}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ arm, hit, i }) => {
              const url = paperUrl(arm);
              return (
                <tr key={arm.id} className={isCounted(arm) ? undefined : styles.notCounted}>
                  <td className={styles.studyCell}>
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
                  <td>
                    <StatusPill size="sm" tone={hit ? "success" : "neutral"}>
                      {hit ? "Yes" : "No"}
                    </StatusPill>
                  </td>
                  <td className={styles.amountCell}>
                    <Amount arm={arm} hit={hit} q={data.quant[String(i)]} />
                  </td>
                  <td className={styles.nowrap}>{METHOD_CLASS_LABEL[arm.method_class]}</td>
                  <td>
                    <FamilyChip arm={arm} />
                  </td>
                  <td className={styles.sampleCell}>
                    {arm.sample}
                    {arm.lines && hit ? (
                      <LineDetail lines={arm.lines} hitLines={data.lines[String(i)] ?? []} />
                    ) : null}
                  </td>
                  <td>
                    <StatusPill size="sm" tone={statusTone(arm.status)} title={STATUS_HELP[arm.status]}>
                      {STATUS_LABEL[arm.status]}
                    </StatusPill>
                    {arm.status_reason ? (
                      <div className={styles.statusReason}>{arm.status_reason}</div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      ) : (
        <p className={styles.empty}>
          {data.hits.size === 0
            ? `Not listed in any of the ${arms.length} datasets.`
            : "Not detected in any counted dataset; tick “include not-counted datasets” to see where it was listed."}
        </p>
      )}
    </div>
  );
}

function Dot({ arm, hit, q }: { arm: StudyArm; hit: boolean; q?: [number, number] }) {
  const counted = isCounted(arm);
  const label =
    `${shortCitation(arm)}: ${arm.name}. ${hit ? "Detected" : "Not detected"}; ` +
    `${STATUS_LABEL[arm.status]}${counted ? "" : ", not counted"}`;
  const cls = [
    styles.dot,
    hit ? `${styles[`fam_${arm.family.replace(/-/g, "_")}`] ?? ""} ${styles.hit}` : "",
    counted ? "" : styles.dim,
  ]
    .filter(Boolean)
    .join(" ");
  // Styled popover (the InfoTip one) rather than the OS title bubble.
  return (
    <span className={tip.wrap} data-infotip="">
      <Link href={studyHref([arm.id])} className={cls} aria-label={label} />
      <span role="tooltip" className={`${tip.popover} ${styles.dotTip}`}>
        <span className={styles.tipLine}>
          <strong className={hit ? styles.tipHit : styles.tipMiss}>
            {hit ? "Detected" : "Not detected"}
          </strong>{" "}
          in {shortCitation(arm)}
          {arm.journal ? <span className={styles.tipMuted}> · {arm.journal}</span> : null}
        </span>
        <span className={styles.tipLine}>{arm.name}</span>
        <span className={styles.tipLine}>
          <span className={styles.tipMuted}>Method:</span> {METHOD_CLASS_LABEL[arm.method_class]},{" "}
          {arm.family_label.toLowerCase()}
        </span>
        <span className={styles.tipLine}>
          <span className={styles.tipMuted}>Cells:</span> {arm.sample ?? "—"}
        </span>
        <span className={styles.tipLine}>
          <span className={styles.tipMuted}>Proteins in list:</span>{" "}
          {arm.n_proteins.toLocaleString("en-US")}
          {arm.reference_overlap != null
            ? `, ${Math.round(arm.reference_overlap * 100)}% known surface`
            : ""}
        </span>
        {hit && q && arm.quant_unit ? (
          <span className={styles.tipLine}>
            <span className={styles.tipMuted}>Amount:</span> {formatQuant(q[0])} {arm.quant_unit},{" "}
            {ordinalPct(q[1])} in this dataset
          </span>
        ) : null}
        <span className={styles.tipLine}>
          <span className={styles.tipMuted}>Status:</span> {STATUS_LABEL[arm.status]},{" "}
          {counted ? "counted as surface evidence" : "not counted"}
        </span>
        <span className={`${styles.tipLine} ${styles.tipMuted}`}>
          Click to open this dataset&apos;s protein list.
        </span>
      </span>
    </span>
  );
}
