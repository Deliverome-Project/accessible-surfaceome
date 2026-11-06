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
  PREF_LABEL,
  surfacePreference,
  type PresenceEntry,
  formatQuant,
  ordinalPct,
  studyHref,
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

/** Short labels shown above each technology's cluster of dots. */
const FAMILY_SHORT: Record<string, string> = {
  "biotin-amine": "Amine biotin",
  "glycoprotein-capture": "Glycoprotein",
  "glycopeptide-capture": "Glycopeptide",
  "peroxidase-proximity": "Peroxidase",
  "other-chemoproteomic": "Other",
  "membrane-fractionation": "Fractionation",
};

type RowSort = "study" | "found" | "bg" | "amount" | "method" | "family" | "sample" | "status";
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

/** This dataset's percentile minus each reference: the per-study version of
 *  the surface-preference score. */
/** This dataset's percentile minus the mean of the available references, or null. */
function studyPrefMean(pct: number | undefined, refs: [number | null, number | null]): number | null {
  if (pct == null) return null;
  const diffs = refs.filter((x): x is number => x != null).map((r) => pct - r);
  return diffs.length ? Math.round(diffs.reduce((a, b) => a + b, 0) / diffs.length) : null;
}

function StudyPref({ pct, refs }: { pct: number; refs: [number | null, number | null] }) {
  const [procan, membrane] = refs;
  const mean = studyPrefMean(pct, refs);
  if (mean == null) return null;
  const tone = mean >= 10 ? "success" : mean <= -10 ? "amber" : "neutral";
  const verdict =
    mean >= 10 ? "surface-enriched" : mean <= -10 ? "intracellular carryover" : "no clear difference";
  const short = mean >= 10 ? "enriched" : mean <= -10 ? "carryover" : "no difference";
  return (
    <StatusPill
      size="sm"
      tone={tone}
      title={
        <>
          <span className={styles.tipLine}>
            <strong>
              {signed(mean)} in this study: {verdict}
            </strong>
          </span>
          {procan != null ? (
            <span className={styles.tipLine}>
              {signed(pct - procan)} vs the ProCan whole proteome ({ordinalPct(pct)} here,{" "}
              {ordinalPct(procan)} in ProCan)
            </span>
          ) : null}
          {membrane != null ? (
            <span className={styles.tipLine}>
              {signed(pct - membrane)} vs membrane preps ({ordinalPct(membrane)} median)
            </span>
          ) : null}
          <span className={`${styles.tipLine} ${styles.tipMuted}`}>
            Average of the comparisons. +10 or more = surface-enriched (green), −10 or less =
            intracellular carryover (yellow).
          </span>
        </>
      }
    >
      {signed(mean)} {short}
    </StatusPill>
  );
}

/** Diverging bar: -50 … +50 percentile points around a center line. */
function DivBar({ value }: { value: number }) {
  const w = Math.min(50, Math.abs(value));
  return (
    <span className={styles.divBar} aria-hidden="true">
      <span
        className={value >= 0 ? styles.divPos : styles.divNeg}
        style={value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
      />
      <span className={styles.divMid} />
    </span>
  );
}

const signed = (x: number) => (x > 0 ? `+${x}` : `${x}`);

/** Whether the protein ranks higher in surface preps than in a whole proteome
 *  (ProCan) and than in membrane preps: enrichment by intact-cell labeling vs
 *  carryover from internal membranes. */
function PreferenceBox({
  pref,
  meta,
}: {
  pref: PresenceEntry["p"];
  meta: StudyIndex["surface_preference"];
}) {
  const { vsProcan, vsMembrane, mean, verdict } = surfacePreference(pref);
  const tip = (
    <>
      <span className={styles.tipLine}>
        Compares where this protein ranks in surface preps with where it ranks elsewhere. Each
        number is the median within-dataset percentile across the counted surface datasets that
        quantified it, minus its percentile in a reference: the ProCan whole proteome (949 cancer
        cell lines,{" "}
        <a href="https://pubmed.ncbi.nlm.nih.gov/35839778/" target="_blank" rel="noreferrer">
          Gonçalves 2022, PMID 35839778
        </a>
        ) and our membrane-fraction datasets.
      </span>
      <span className={styles.tipLine}>
        Intact-cell labeling enriches outward-facing proteins, so true surface proteins rank
        higher in surface preps. Abundant intracellular proteins that ride along (lysosome and
        ER membrane proteins, but also cytosolic ones) rank lower. At least +10 reads as surface-enriched, at most −10 as a carryover
        pattern.
      </span>
      {meta?.auroc_canonical_vs_low_or_not.vs_procan ? (
        <span className={styles.tipLine}>
          Check: separates Canonical from Low / Not-surface proteins with AUROC{" "}
          {meta.auroc_canonical_vs_low_or_not.vs_procan} (vs whole proteome) and{" "}
          {meta.auroc_canonical_vs_low_or_not.vs_membrane} (vs membrane preps).
        </span>
      ) : null}
      <span className={styles.tipLine}>
        Limits: comparisons across studies and cell types; very abundant proteins sit near the top
        everywhere, so they score near 0; proteins ProCan misses get no whole-proteome number.
      </span>
    </>
  );
  return (
    <div className={styles.prefBox}>
      <div className={styles.prefHead}>
        <span className={styles.groupName}>Surface preference</span>
        <InfoTip wide label="About surface preference">
          {tip}
        </InfoTip>
        {verdict ? (
          <StatusPill
            size="sm"
            tone={verdict === "enriched" ? "success" : verdict === "carryover" ? "amber" : "neutral"}
          >
            {PREF_LABEL[verdict]}
          </StatusPill>
        ) : null}
      </div>
      {!pref ? (
        <p className={styles.prefLine}>
          Not enough data: needs a value in at least {meta?.min_surface_values ?? 5} quantified
          counted datasets.
        </p>
      ) : (
        <>
          {vsProcan != null ? (
            <p className={styles.prefLine}>
              <DivBar value={vsProcan} />
              <span>
                <strong>{signed(vsProcan)}</strong> vs whole proteome: {ordinalPct(pref[0])} in
                surface preps, {ordinalPct(pref[2] ?? 0)} in ProCan
              </span>
            </p>
          ) : (
            <p className={styles.prefLine}>Not in ProCan, so no whole-proteome comparison.</p>
          )}
          {vsMembrane != null ? (
            <p className={styles.prefLine}>
              <DivBar value={vsMembrane} />
              <span>
                <strong>{signed(vsMembrane)}</strong> vs membrane preps: {ordinalPct(pref[0])} in
                surface preps, {ordinalPct(pref[1] ?? 0)} in membrane fractions
              </span>
            </p>
          ) : (
            <p className={styles.prefLine}>Too few membrane-fraction values to compare.</p>
          )}
        </>
      )}
      {mean != null ? (
        <p className={styles.prefRule}>
          Average of the two: <strong>{signed(mean)}</strong> percentile points. We call{" "}
          <strong>+10 or more</strong> surface-enriched, <strong>−10 or less</strong> an
          intracellular carryover pattern, and anything in between no clear difference.
        </p>
      ) : null}
    </div>
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
    pref: PresenceEntry["p"];
    /** References for per-dataset comparisons: [ProCan pct, membrane median]. */
    refs: [number | null, number | null];
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
            pref: entry?.p,
            refs: [entry?.w ?? null, entry?.m ?? null],
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
  const filtered = arms.filter((x) => (showMissing || x.hit) && (showOther || isCounted(x.arm)));
  const rows =
    sortKey === null
      ? [...filtered].sort(
          (a, b) =>
            Number(b.hit) - Number(a.hit) ||
            Number(isCounted(b.arm)) - Number(isCounted(a.arm)) ||
            // Most enriched over background first; datasets without a value last.
            (studyPrefMean(data.quant[String(b.i)]?.[1], data.refs) ?? -999) -
              (studyPrefMean(data.quant[String(a.i)]?.[1], data.refs) ?? -999) ||
            (b.arm.year ?? 0) - (a.arm.year ?? 0),
        )
      : sortRows(filtered, {
          study: (r) => shortCitation(r.arm),
          found: (r) => Number(r.hit),
          // Missing values sort last in either direction.
          bg: (r) =>
            studyPrefMean(data.quant[String(r.i)]?.[1], data.refs) ??
            (sortDir === "asc" ? Infinity : -Infinity),
          amount: (r) => data.quant[String(r.i)]?.[1] ?? (sortDir === "asc" ? Infinity : -Infinity),
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
      <PreferenceBox pref={data.pref} meta={data.index.surface_preference} />

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
                      <span className={`${styles.famLabel} ${styles[`famText_${fam.replace(/-/g, "_")}`] ?? ""}`}>
                        {FAMILY_SHORT[fam] ?? inFam[0].arm.family_label}
                      </span>
                      <span className={styles.famDots}>
                        {inFam.map(({ arm, hit, i }) => (
                          <Dot key={arm.id} arm={arm} hit={hit} q={data.quant[String(i)]} />
                        ))}
                      </span>
                    </span>
                  );
                })}
              </span>
            </div>
          );
        })}
      </div>
      <p className={styles.legend}>
        <span className={styles.legendItem}>
          Filled = detected; <span className={styles.dot} /> hollow = not detected; faded = not
          counted. Hover a dot for the study.
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
            <col style={{ width: "11.5rem" }} />
            <col style={{ width: "6.75rem" }} />
            <col style={{ width: "8.5rem" }} />
            <col style={{ width: "9.5rem" }} />
            <col style={{ width: "8.5rem" }} />
            <col style={{ width: "13.75rem" }} />
            <col />
            <col style={{ width: "10rem" }} />
          </colgroup>
          <thead>
            <tr>
              {th("study", "Study")}
              {th("found", "Detected")}
              {th("bg", "Vs background")}
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
                  <td>
                    {hit && data.quant[String(i)] ? (
                      <StudyPref pct={data.quant[String(i)][1]} refs={data.refs} />
                    ) : (
                      <span className={styles.muted}>—</span>
                    )}
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
            ? `, ${Math.round(arm.reference_overlap * 100)}% Canonical or Likely`
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
