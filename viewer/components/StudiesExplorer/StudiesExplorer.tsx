"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  armStatusLabel,
  countableOtherConditions,
  countingRule,
  INCLUDE_OTHER_LABEL,
  INCLUDE_OTHER_PARAM,
  includeOtherHelp,
  letter,
  loadAllPresence,
  METHOD_CLASS_LABEL,
  OVERLAP_ALLOWANCE_PTS,
  OVERLAP_SCREEN,
  screenScore,
  shortCitation,
  STATUS_HELP,
  STATUS_LABEL,
  statusShortLabel,
  statusPillLabel,
  STATUS_ORDER,
  TIER_LABEL,
  TIER_ORDER,
  type ArmStatus,
  type MethodClass,
  type PresenceShard,
  type StudyArm,
  type StudyIndex,
  type TierCode,
  FAMILY_ORDER,
  tierOf,
  CELL_GROUP_LABEL,
  CELL_GROUP_ORDER,
  formatQuant,
  ordinalPct,
  type CellGroup,
  PREF_LABEL,
  surfacePreference,
  type PresenceEntry,
  loadPresence,
  RAW_FLAG_LABEL,
  repositoryUrl,
} from "../../lib/surface-proteomics";
import { ProteinLookup } from "./ProteinLookup";
import { HoverTip } from "../surfaceome/_shared/HoverTip";
import { InfoTip } from "../InfoTip/InfoTip";
import { tooltips } from "../../lib/tooltips";
import { statusTone } from "../surfaceome/ExpressionCard/StudyPresence";
import { SortableHeader } from "../surfaceome/_shared/SortableHeader";
import { SortResetButton } from "../surfaceome/_shared/SortResetButton";
import { useTableSort, type SortValue } from "../surfaceome/_shared/useTableSort";
import { StatusPill } from "../surfaceome/StatusPill/StatusPill";
import { FamilyChip } from "./FamilyChip";
import { MethodsPanel } from "./MethodsPanel";
import { TierPill } from "./TierPill";
import styles from "./StudiesExplorer.module.css";

interface Props {
  index: StudyIndex;
}

type Tier = TierCode | "none";
type StudySort = "study" | "year" | "method" | "family" | "sample" | "n" | "overlap" | "status";
type ProteinSort = "protein" | "name" | "votes" | "tier" | "counted" | "amount" | "pref";

const ALL_CLASSES: MethodClass[] = ["intact_cell", "fractionation"];
const PAGE = 200;
/** Above this many selected studies the exact-intersection list stops being readable. */
const MAX_UPSET = 10;
const UPSET_ROWS = 15;

interface Protein {
  acc: string;
  symbol: string;
  deep: boolean;
  name: string;
  /** Source databases (of five) listing it as surface; null when not in the catalog. */
  votes: number | null;
  tier: Tier;
  /** Indices of the selected arms that list it. */
  arms: Set<number>;
  /** Counted arms (anywhere in the compendium) that detect it. */
  nCounted: number;
  /** [value, within-dataset percentile] when exactly one dataset is selected. */
  q: [number, number] | null;
  /** Surface preference (see surfacePreference). */
  pref: ReturnType<typeof surfacePreference>;
  prefRaw: PresenceEntry["p"];
}

/** Preset views over all counted datasets; each has a short link (?view=…). */
export type View = "consensus" | "novel" | "review";
const VIEWS: View[] = ["consensus", "novel", "review"];
/** Detection floor the two discovery presets start from. */
const DISCOVERY_MIN = 3;
/** New-candidate defaults: at most this many DB votes, and at least this surface preference. */
const NOVEL_MAX_DB = 1;
const NOVEL_MIN_PREF = 10;

/** Arm ids in ?arm=, with split-study aliases (e.g. a parent paper id) expanded. */
function readSelection(aliases: Record<string, string[]>): string[] {
  if (typeof window === "undefined") return [];
  const v = new URLSearchParams(window.location.search).get("arm");
  const ids = v ? v.split(",").filter(Boolean) : [];
  return [...new Set(ids.flatMap((id) => aliases[id] ?? [id]))];
}

type Choice = View | "compare" | "lookup";

/** The starting options, shortest label first; the one-line description shows
 *  for whichever is chosen. */
const CHOICES: { key: Choice; label: string; desc: (nCounted: number) => string }[] = [
  {
    key: "consensus",
    label: "Consensus list",
    desc: (n) =>
      `Every protein any of the ${n} counted datasets detected, ranked by how many found it.`,
  },
  {
    key: "novel",
    label: "New candidates",
    desc: () =>
      `Detected on intact cells by at least ${DISCOVERY_MIN} counted datasets, listed by at most one of the five surfaceome databases, and enriched over background (surface preference +10 or more). All three are adjustable.`,
  },
  {
    key: "review",
    label: "Possible misses",
    desc: () =>
      `Detected by at least ${DISCOVERY_MIN} counted datasets and enriched over background (surface preference +10 or more), but our deep dive rates them Low confidence, Uncertain or Not surface: a review list for our own calls.`,
  },
  {
    key: "compare",
    label: "Compare studies",
    desc: () =>
      "Every dataset, one row per paper (expand a paper for its datasets), counted ones first. Tick one dataset to see its proteins, or several to see which proteins they share.",
  },
  {
    key: "lookup",
    label: "Look up a protein",
    desc: () => "Type a symbol, name or accession to see every dataset that detected it.",
  },
];

/** Bring a table row into view once it has rendered (retries for about a
 *  second: the row appears after the selection and its paper are set). */
function scrollToRow(id: string, tries = 20) {
  // The browser restores the scroll position when the page finishes
  // loading, which would undo an earlier scroll; wait for that first.
  if (document.readyState !== "complete") {
    window.addEventListener("load", () => setTimeout(() => scrollToRow(id, tries), 0), {
      once: true,
    });
    return;
  }
  const el = document.getElementById(id);
  if (!el) {
    if (tries > 0) setTimeout(() => scrollToRow(id, tries - 1), 50);
    return;
  }
  const top = el.getBoundingClientRect().top + window.scrollY - window.innerHeight / 3;
  window.scrollTo({ top: Math.max(0, top), behavior: "instant" });
}

/** One query parameter, or null (server render / absent). */
function param(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

/** Write (or clear) query parameters without adding a history entry, so the
 *  page's filters survive clicking through to a protein and coming back. */
function setParams(values: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [k, v] of Object.entries(values)) {
    if (v) url.searchParams.set(k, v);
    else url.searchParams.delete(k);
  }
  window.history.replaceState(window.history.state, "", url.toString());
}

function readView(): View | null {
  if (typeof window === "undefined") return null;
  const v = new URLSearchParams(window.location.search).get("view");
  return VIEWS.includes(v as View) ? (v as View) : null;
}

const pct = (x: number | null) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export function StudiesExplorer({ index }: Props) {
  const arms = index.arms;
  const idxById = useMemo(() => new Map(arms.map((a, i) => [a.id, i])), [arms]);
  const aliases = index.aliases;
  const CLASS_ORDER = useMemo(
    () => ALL_CLASSES.filter((c) => arms.some((a) => a.method_class === c)),
    [arms],
  );
  // Opt-in (?oc=1): also count other conditions whose baseline arm counts.
  // Off by default, so each study counts only its baseline samples.
  const [includeOther, setIncludeOther] = useState(false);
  const counts = useMemo(() => countingRule(arms, includeOther), [arms, includeOther]);
  const nOther = useMemo(() => arms.filter((a) => a.status === "perturbed").length, [arms]);
  const nCountableOther = useMemo(() => countableOtherConditions(arms).length, [arms]);
  const countedIdx = useMemo(() => arms.flatMap((a, i) => (counts(a) ? [i] : [])), [arms, counts]);
  const [query, setQuery] = useState("");
  // Catalog-style chips: nothing checked = no filter; checked values OR together.
  const [statuses, setStatuses] = useState<Set<ArmStatus>>(() => new Set());
  const [classes, setClasses] = useState<Set<MethodClass>>(() => new Set());
  const [cellGroups, setCellGroups] = useState<Set<CellGroup>>(() => new Set());
  const [families, setFamilies] = useState<Set<string>>(() => new Set());
  // The page is prerendered without query parameters, so these have to START at the
  // prerendered defaults and take the URL only after mount — the same shape as the
  // ?arm= effect below. Reading the URL in a useState initializer instead makes the
  // first client render disagree with the HTML it is hydrating (?oc=1 rendered "129
  // counted datasets" over a prerendered "92"), and React answers a text mismatch by
  // throwing the whole prerendered page away and rebuilding it in the browser.
  useEffect(() => {
    const csv = <T,>(name: string): Set<T> =>
      new Set((param(name)?.split(",").filter(Boolean) ?? []) as T[]);
    if (param(INCLUDE_OTHER_PARAM) === "1") setIncludeOther(true);
    const q = param("dq");
    if (q) setQuery(q);
    const st = csv<ArmStatus>("st");
    if (st.size) setStatuses(st);
    const mc = csv<MethodClass>("mc");
    if (mc.size) setClasses(mc);
    const cg = csv<CellGroup>("cg");
    if (cg.size) setCellGroups(cg);
    const fam = csv<string>("fam");
    if (fam.size) setFamilies(fam);
  }, []);
  const FAMILIES = useMemo(
    () => FAMILY_ORDER.filter((f) => arms.some((a) => a.family === f)),
    [arms],
  );
  const familyLabel = useMemo(
    () => new Map(arms.map((a) => [a.family, a.family_label])),
    [arms],
  );
  // ?det=ACC (from a gene page): only the datasets that detected that protein.
  // Read after mount: the static HTML has no query string, so reading it
  // during the first render would not match the server markup.
  const [det, setDet] = useState<string | null>(null);
  useEffect(() => setDet(param("det")), []);
  const [detHits, setDetHits] = useState<{ set: Set<number>; symbol: string } | null>(null);
  useEffect(() => {
    if (!det) {
      setDetHits(null);
      return;
    }
    let live = true;
    loadPresence(det).then(
      ({ entry }) => live && setDetHits({ set: new Set(entry?.a ?? []), symbol: entry?.s || det }),
      () => live && setDetHits({ set: new Set(), symbol: det }),
    );
    return () => {
      live = false;
    };
  }, [det]);
  useEffect(() => {
    setParams({
      dq: query.trim() || null,
      st: [...statuses].join(",") || null,
      mc: [...classes].join(",") || null,
      cg: [...cellGroups].join(",") || null,
      fam: [...families].join(",") || null,
      det,
      [INCLUDE_OTHER_PARAM]: includeOther ? "1" : null,
    });
  }, [query, statuses, classes, cellGroups, families, det, includeOther]);
  // Papers opened to show their datasets.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggleExpanded = (pub: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(pub)) next.delete(pub);
      else next.add(pub);
      return next;
    });
  const [selected, setSelected] = useState<number[]>([]);
  const [view, setView] = useState<View | null>(null);
  // Hand-picked modes; a preset view takes precedence when set.
  // The study table is the landing state; a preset view replaces it.
  const [mode, setMode] = useState<"compare" | "lookup" | null>("compare");
  const [pickOpen, setPickOpen] = useState(true);
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<StudySort>();
  const showResults = () => {
    setPickOpen(false);
    requestAnimationFrame(() =>
      document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  };

  // Selection lives in ?arm=a,b so a gene page's dots can deep-link to a study.
  useEffect(() => {
    const v = readView();
    const ids = v ? [] : readSelection(aliases ?? {});
    const sel = v
      ? countedIdx
      : ids.map((id) => idxById.get(id)).filter((i): i is number => i !== undefined);
    setView(v);
    setSelected(sel);
    if (!v && sel.length) {
      // Arriving from a link (a gene page dot, an email): open each linked
      // dataset's paper in the table and bring the first one into view.
      setMode("compare");
      setExpanded(new Set(sel.map((i) => arms[i].publication)));
      if (sel.length > 1 && param("pf")) {
        // A link that also names a protein (?pf=DPP4) is a comparison to read, not a
        // selection to make: open on the results with the picker folded away.
        setPickOpen(false);
        requestAnimationFrame(() =>
          document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
      } else {
        scrollToRow(`arm-${arms[sel[0]].id}`);
      }
    }
    // Read the URL once; a later change of counting rule is handled below.
  }, [idxById, aliases, arms]);
  const updateSelected = useCallback(
    (next: number[], nextView: View | null = null) => {
      setSelected(next);
      setView(nextView);
      const url = new URL(window.location.href);
      url.searchParams.delete("arm");
      url.searchParams.delete("view");
      if (nextView) url.searchParams.set("view", nextView);
      else if (next.length) url.searchParams.set("arm", next.map((i) => arms[i].id).join(","));
      window.history.replaceState(null, "", url.toString());
    },
    [arms],
  );
  // A preset view runs over every counted dataset, so it follows the toggle.
  const viewRef = useRef(view);
  viewRef.current = view;
  useEffect(() => {
    if (viewRef.current) setSelected(countedIdx);
  }, [countedIdx]);
  const openView = (v: View) => {
    setMode(null);
    updateSelected(countedIdx, v);
    showResults();
  };
  const choose = (c: Choice) => {
    if (c === "compare" || c === "lookup") {
      setMode(c);
      updateSelected([]);
      setPickOpen(true);
      requestAnimationFrame(() =>
        document.getElementById(c === "compare" ? "dataset-search" : "protein-lookup")?.focus(),
      );
    } else openView(c);
  };
  const active: Choice | null = view ?? mode;
  const toggle = (i: number) =>
    updateSelected(selected.includes(i) ? selected.filter((x) => x !== i) : [...selected, i]);

  const q = query.trim().toLowerCase();
  const visible = arms
    .map((arm, i) => ({ arm, i }))
    .filter(
      ({ arm, i }) =>
        (!det || (detHits !== null && detHits.set.has(i))) &&
        (statuses.size === 0 || statuses.has(arm.status)) &&
        (classes.size === 0 || classes.has(arm.method_class)) &&
        (cellGroups.size === 0 || (arm.cell_group != null && cellGroups.has(arm.cell_group))) &&
        (families.size === 0 || families.has(arm.family)) &&
        (!q ||
          [arm.name, arm.first_author, arm.sample, arm.family_label, arm.journal, arm.pmid, String(arm.year)]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(q)),
    );
  const comparators: Record<StudySort, (r: { arm: StudyArm }) => SortValue> = {
    study: (r) => shortCitation(r.arm),
    year: (r) => r.arm.year ?? 0,
    method: (r) => r.arm.method_class,
    family: (r) => FAMILY_ORDER.indexOf(r.arm.family as (typeof FAMILY_ORDER)[number]),
    sample: (r) => r.arm.sample ?? "",
    n: (r) => r.arm.n_proteins,
    overlap: (r) => screenScore(r.arm).value ?? -1,
    status: (r) => STATUS_ORDER.indexOf(r.arm.status),
  };
  const rows = sortRows(visible, comparators);
  const maxN = Math.max(...arms.map((a) => a.n_proteins));
  const letterOf = new Map(selected.map((i, k) => [i, letter(k)]));

  // Default order (no column sorted): counted datasets first, then by
  // status, newest first.
  const ordered =
    sortKey === null
      ? [...visible].sort(
          (a, b) =>
            Number(counts(b.arm)) - Number(counts(a.arm)) ||
            STATUS_ORDER.indexOf(a.arm.status) - STATUS_ORDER.indexOf(b.arm.status) ||
            (b.arm.year ?? 0) - (a.arm.year ?? 0) ||
            shortCitation(a.arm).localeCompare(shortCitation(b.arm)),
        )
      : rows;
  // One row per paper, placed where its first dataset falls in that order.
  type Item = { arm: StudyArm; i: number };
  const groups: { pub: string; items: Item[] }[] = [];
  {
    const at = new Map<string, number>();
    for (const r of ordered) {
      const k = at.get(r.arm.publication);
      if (k === undefined) {
        at.set(r.arm.publication, groups.length);
        groups.push({ pub: r.arm.publication, items: [r] });
      } else groups[k].items.push(r);
    }
  }
  // A search or a gene filter opens every matching paper.
  const autoOpen = q.length > 0 || det !== null;
  const nPapersShown = groups.length;

  const armRow = ({ arm, i }: Item, nested: boolean) => {
              const sel = selected.includes(i);
              const counted = counts(arm);
              return (
                <tr
                  key={arm.id}
                  id={`arm-${arm.id}`}
                  className={`${sel ? styles.selectedRow : ""} ${counted ? "" : styles.notCounted} ${nested ? styles.armRow : ""}`}
                >
                  <td>
                    <label className={styles.pick}>
                      <input
                        type="checkbox"
                        checked={sel}
                        onChange={() => toggle(i)}
                        aria-label={`Select ${arm.name}`}
                      />
                      {sel ? <span className={styles.letter}>{letterOf.get(i)}</span> : null}
                    </label>
                  </td>
                  <td className={styles.studyCell}>
                    <button type="button" className={styles.studyButton} onClick={() => toggle(i)}>
                      {nested ? arm.name : shortCitation(arm)}
                    </button>
                    {nested ? null : <div className={styles.sub}>{arm.name}</div>}
                    {nested ? null : <PaperLinks arm={arm} />}
                    <ArmSources arm={arm} studyList={index.study_list} />
                  </td>
                  <td>{arm.year ?? "—"}</td>
                  <td>
                    <span className={styles.method}>
                      <span className={`${styles.swatch} ${styles[`sw_${arm.method_class}`]}`} aria-hidden="true" />
                      {METHOD_CLASS_LABEL[arm.method_class]}
                    </span>
                  </td>
                  <td className={styles.chemCell}>
                    <FamilyChip arm={arm} />
                  </td>
                  <td className={styles.sample}>
                    {arm.sample}
                    {arm.cell_group ? (
                      <div className={styles.sub}>{CELL_GROUP_LABEL[arm.cell_group]}</div>
                    ) : null}
                  </td>
                  <td className={styles.countCell}>
                    {/* Bar inline with the number, like Surface overlap, so the
                        two bars sit on the same line in every row — and, like it,
                        left-aligned, so the header sits over the start of the bar
                        instead of floating in the middle of the bar-plus-number pair. */}
                    <span className={styles.countInline}>
                      <Bar value={arm.n_proteins / maxN} inline />
                      <span className={styles.countInlineNum}>{arm.n_proteins.toLocaleString("en-US")}</span>
                    </span>
                  </td>
                  <td>
                    <OverlapBar arm={arm} />
                  </td>
                  <td>
                    <StatusPill size="sm" tone={statusTone(arm.status)} title={STATUS_HELP[arm.status]}>
                      {armStatusLabel(arm, "pill")}
                    </StatusPill>
                    <div className={counted ? styles.countedYes : styles.countedNo}>
                      {counted ? "counted" : "not counted"}
                    </div>
                    {arm.status_reason ? (
                      <div className={styles.statusReason}>{arm.status_reason}</div>
                    ) : null}
                  </td>
                </tr>
              );
  };

  const paperRows = (g: { pub: string; items: Item[] }) => {
    if (g.items.length === 1) return [armRow(g.items[0], false)];
    const all = arms.filter((a) => a.publication === g.pub);
    const first = g.items[0].arm;
    const open = autoOpen || expanded.has(g.pub);
    const nCounted = all.filter(counts).length;
    const anySelected = g.items.some(({ i }) => selected.includes(i));
    // Select or clear all of a paper's datasets at once (Kim et al. 2017's four, say).
    const paperIdx = arms.flatMap((a, i) => (a.publication === g.pub ? [i] : []));
    const allSelected = paperIdx.every((i) => selected.includes(i));
    const togglePaper = () => {
      if (allSelected) {
        updateSelected(selected.filter((i) => !paperIdx.includes(i)));
      } else {
        updateSelected([...selected, ...paperIdx.filter((i) => !selected.includes(i))]);
        if (!expanded.has(g.pub)) toggleExpanded(g.pub);
      }
    };
    const head = (
      <tr
        key={`paper-${g.pub}`}
        className={`${styles.paperRow} ${anySelected ? styles.selectedRow : ""} ${nCounted ? "" : styles.notCounted}`}
      >
        <td className={styles.paperPick}>
          <input
            type="checkbox"
            checked={allSelected}
            ref={(el) => {
              if (el) el.indeterminate = anySelected && !allSelected;
            }}
            onChange={togglePaper}
            aria-label={`Select all ${all.length} datasets of ${shortCitation(first)}`}
            title={`Select all ${all.length} datasets of this paper`}
          />
          <button
            type="button"
            className={styles.expandButton}
            aria-expanded={open}
            aria-label={`${open ? "Hide" : "Show"} the ${all.length} datasets of ${shortCitation(first)}`}
            onClick={() => toggleExpanded(g.pub)}
          >
            {open ? "▾" : "▸"}
          </button>
        </td>
        <td className={styles.studyCell}>
          <button type="button" className={styles.studyButton} onClick={() => toggleExpanded(g.pub)}>
            {shortCitation(first)}
          </button>
          {first.title ? <div className={styles.sub}>{first.title}</div> : null}
          <PaperLinks arm={first} />
        </td>
        <td>{first.year ?? "—"}</td>
        <td colSpan={6} className={styles.paperSummary}>
          {all.length} datasets: {nCounted} counted
          {all.length - nCounted ? `, ${all.length - nCounted} not counted` : ""}
          {g.items.length < all.length ? ` · ${g.items.length} match the filters` : ""}
          {!open ? (
            <button type="button" className={styles.linkButton} onClick={() => toggleExpanded(g.pub)}>
              show datasets
            </button>
          ) : null}
        </td>
      </tr>
    );
    return open ? [head, ...g.items.map((it) => armRow(it, true))] : [head];
  };

  const header = (k: StudySort, label: string, num = false, info?: ReactNode) => (
    <th aria-sort={ariaSort(k)} className={num ? styles.num : undefined}>
      <span className={styles.headWithTip}>
        <SortableHeader k={k} active={sortKey === k} direction={sortDir} onSort={onSort}>
          {label}
        </SortableHeader>
        {info ? (
          <InfoTip wide align="end" label={`About ${label}`}>
            {info}
          </InfoTip>
        ) : null}
      </span>
    </th>
  );

  return (
    <div className={styles.wrap}>
      <section className={styles.start} aria-label="Where to start">
        <div className={styles.startRow} role="group" aria-label="Where to start">
          <span className={`label-mono ${styles.startLabel}`}>Start with</span>
          <InfoTip wide align="start" label="About the starting views">
            The three preset views, each over every counted dataset:
            <ul className={styles.tipList}>
              {CHOICES.filter((c) => VIEWS.includes(c.key as View)).map((c) => (
                <li key={c.key}>
                  <strong>{c.label}:</strong> {c.desc(countedIdx.length)}
                </li>
              ))}
            </ul>
          </InfoTip>
          {CHOICES.map((c) => (
            <button
              key={c.key}
              type="button"
              className={styles.startOption}
              data-on={active === c.key ? "true" : "false"}
              aria-pressed={active === c.key}
              onClick={() => choose(c.key)}
            >
              {c.label}
            </button>
          ))}
        </div>
        <p className={styles.startDesc}>
          {CHOICES.find((c) => c.key === (active ?? "compare"))?.desc(countedIdx.length)}
        </p>
        {nOther > 0 ? (
          <p className={styles.otherNote} data-on={includeOther ? "true" : "false"}>
            {includeOther
              ? `Counting other conditions (not the default): ${nCountableOther} senescent, infected, knockout, treated or diseased datasets count alongside their studies' baselines.`
              : `Each study counts only its baseline samples. The same studies' ${nOther} other-condition datasets (senescent, infected, knockout, treated or diseased samples) are listed but not counted.`}{" "}
            <label className={styles.otherToggle}>
              <input
                type="checkbox"
                checked={includeOther}
                onChange={(e) => setIncludeOther(e.target.checked)}
              />{" "}
              {INCLUDE_OTHER_LABEL}
            </label>
            <InfoTip wide align="start" label={`About ${INCLUDE_OTHER_LABEL.toLowerCase()}`}>
              {includeOtherHelp(nCountableOther, nOther)}
            </InfoTip>
          </p>
        ) : null}
        {active === "lookup" ? <ProteinLookup /> : null}
      </section>

      {active === "compare" ? (
      <details
        className={styles.pickBox}
        open={pickOpen}
        onToggle={(e) => setPickOpen((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary className={styles.pickSummary}>
          <span className={`h-section ${styles.sectionTitle}`}>Choose datasets</span>
          <span className={styles.pickMeta}>
            {selected.length
              ? `${selected.length} selected · click to ${pickOpen ? "hide" : "change"} the list`
              : `${arms.length} datasets from ${index.n_publications} papers · click to ${pickOpen ? "hide" : "show"}`}
          </span>
        </summary>
        <p className={styles.sub}>
          A paper can contribute several datasets, for example one per cell line or labeling
          method. Faded rows are listed for completeness but not counted as surface evidence.
        </p>
      <div className={styles.controls}>
        <input
          id="dataset-search"
          type="search"
          className={styles.search}
          placeholder="Search author, cell type, method, PMID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search datasets"
        />
        <ChipGroup
          label="Status"
          info={tooltips.arm_status}
          options={STATUS_ORDER}
          labelOf={(s) => STATUS_LABEL[s]}
          titleOf={(s) => STATUS_HELP[s]}
          countOf={(s) => arms.filter((a) => a.status === s).length}
          value={statuses}
          onChange={setStatuses}
        />
        <ChipGroup
          label="Cell type"
          options={CELL_GROUP_ORDER}
          labelOf={(g) => CELL_GROUP_LABEL[g]}
          countOf={(g) => arms.filter((a) => a.cell_group === g).length}
          value={cellGroups}
          onChange={setCellGroups}
        />
        <ChipGroup
          label="Method"
          options={CLASS_ORDER}
          labelOf={(c) => METHOD_CLASS_LABEL[c]}
          countOf={(c) => arms.filter((a) => a.method_class === c).length}
          value={classes}
          onChange={setClasses}
        />
        <ChipGroup
          label="Chemistry"
          options={FAMILIES as unknown as string[]}
          labelOf={(f) => familyLabel.get(f) ?? f}
          countOf={(f) => arms.filter((a) => a.family === f).length}
          value={families}
          onChange={setFamilies}
        />
      </div>

      {det ? (
        <div className={styles.detBanner} role="status">
          {detHits === null
            ? "Loading the datasets that detected this protein…"
            : `Showing the ${detHits.set.size} dataset${detHits.set.size === 1 ? "" : "s"} that detected ${detHits.symbol} (${det}).`}
          <button type="button" className={styles.linkButton} onClick={() => setDet(null)}>
            show all datasets
          </button>
        </div>
      ) : null}

      <div className={styles.count}>
        {rows.length} of {arms.length} datasets shown, from {nPapersShown} paper{nPapersShown === 1 ? "" : "s"}
        {selected.length > 0 ? ` · ${selected.length} selected` : ""}
        {selected.length > 0 ? (
          <button type="button" className={styles.linkButton} onClick={() => updateSelected([])}>
            clear selection
          </button>
        ) : null}
        <SortResetButton visible={sortKey !== null} onReset={reset} />
      </div>

      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th aria-label="Select" />
              {header("study", "Study")}
              {header("year", "Year")}
              {header("method", "Method")}
              {header("family", "Chemistry")}
              {header("sample", "Cell type / sample")}
              {header("n", "Proteins")}
              {header("overlap", "Surface overlap", false, tooltips.surface_overlap)}
              {header("status", "Status", false, tooltips.arm_status)}
            </tr>
          </thead>
          <tbody>
            {groups.flatMap((g) => paperRows(g))}
          </tbody>
        </table>
      </div>

      </details>
      ) : null}

      {active === "compare" && selected.length > 0 && pickOpen ? (
        <div className={styles.stickyBar} role="region" aria-label="Selection">
          <span>
            <strong>{selected.length}</strong> dataset{selected.length === 1 ? "" : "s"} selected
          </span>
          <button type="button" className={styles.primaryButton} onClick={showResults}>
            Show results ↓
          </button>
          <button type="button" className={styles.linkButton} onClick={() => updateSelected([])}>
            clear
          </button>
        </div>
      ) : null}

      {selected.length > 0 && (view || active === "compare") ? (
        <div id="results" className={styles.results}>
          <SelectionPanel
            arms={arms}
            selected={selected}
            countedIdx={countedIdx}
            counts={counts}
            view={
              view ??
              (selected.length === countedIdx.length && countedIdx.every((i) => selected.includes(i))
                ? "consensus"
                : null)
            }
          />
        </div>
      ) : null}
    </div>
  );
}

function Bar({ value, inline = false }: { value: number; inline?: boolean }) {
  return (
    <span className={inline ? `${styles.bar} ${styles.barInline}` : styles.bar} aria-hidden="true">
      <span style={{ width: `${Math.max(2, value * 100)}%` }} />
    </span>
  );
}

/** The screen score (share of the amount, or of the list) with a tick at the bar
 *  an intact-cell arm must reach. */
function OverlapBar({ arm }: { arm: StudyArm }) {
  const { value, cutoff, basis } = screenScore(arm);
  const intact = arm.method_class === "intact_cell";
  const status = arm.status;
  if (value == null) return <span className={styles.sub}>—</span>;
  const byAmount = basis === "abundance";
  // Color follows the review outcome, not the raw number: a provisional
  // arm inside the 2-point allowance is counted (light teal), and a
  // pre-filtered list below its raised bar is high background (amber).
  const counted = status === "core" || status === "provisional";
  // A table pre-filtered by surface annotation has an inflated overlap by
  // construction, so it is drawn neutral rather than as a pass.
  const tone = !intact || status === "annotation_selected" || status === "perturbed"
    ? styles.na
    : status === "below_screen"
      ? styles.fail
      : counted && value < cutoff
        ? styles.near
        : value >= cutoff
          ? styles.pass
          : styles.fail;
  return (
    <HoverTip
      tip={
        byAmount
          ? `${pct(value)} of this dataset's length-corrected protein amount is Canonical or Likely in our Surfaceome (${pct(arm.reference_overlap)} of its proteins). Datasets whose table reports amounts need at least ${pct(cutoff)} of their amount (the tick)${
              arm.auroc_rescued && arm.abundance_auroc != null
                ? `, or amounts that rank Canonical or Likely proteins first. This one ${status === "perturbed" ? "would count" : "counts"} that way: AUROC ${arm.abundance_auroc.toFixed(2)}, at or above ${(arm.auroc_rescue_cutoff ?? 0.58).toFixed(2)}`
                : ""
            }.${status === "perturbed" ? " As another condition of its study, it is shown with the same score but never counted." : ""}`
          : `${pct(value)} of this dataset's proteins are Canonical or Likely in our Surfaceome${
              intact
                ? `; datasets without published amounts need at least ${pct(OVERLAP_SCREEN)} of their proteins (the tick), or are Provisional within ${OVERLAP_ALLOWANCE_PTS} points below it`
                : ""
            }.`
      }
    >
    <span className={styles.overlap}>
      <span className={styles.overlapTrack}>
        <span
          className={`${styles.overlapFill} ${tone}`}
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
        <span className={styles.overlapTick} style={{ left: `${cutoff * 100}%` }} />
      </span>
      <span className={styles.overlapNum}>{pct(value)}</span>
      {byAmount ? <span className={styles.overlapBasis}>amount</span> : null}
    </span>
    </HoverTip>
  );
}

function ChipGroup<T extends string>({
  label,
  info,
  options,
  labelOf,
  titleOf,
  countOf,
  value,
  onChange,
}: {
  label: string;
  info?: ReactNode;
  options: T[];
  labelOf: (v: T) => string;
  titleOf?: (v: T) => string;
  countOf: (v: T) => number;
  value: Set<T>;
  onChange: (v: Set<T>) => void;
}) {
  return (
    <fieldset className={styles.chips}>
      <legend className="label-mono">{label}</legend>
      {info ? (
        <InfoTip wide align="start" label={`About ${label}`}>
          {info}
        </InfoTip>
      ) : null}
      {options.map((o) => {
        const on = value.has(o);
        const chip = (
          <button
            key={o}
            type="button"
            className={styles.chip}
            data-on={on ? "true" : "false"}
            aria-pressed={on}
            onClick={() => {
              const next = new Set(value);
              if (on) next.delete(o);
              else next.add(o);
              onChange(next);
            }}
          >
            {labelOf(o)} <span className={styles.chipCount}>{countOf(o)}</span>
          </button>
        );
        const help = titleOf?.(o);
        return help ? (
          <HoverTip key={o} tip={help}>
            {chip}
          </HoverTip>
        ) : (
          chip
        );
      })}
    </fieldset>
  );
}

/** When a filter finds nothing in "In all" (or an intersection) but the protein is in
 *  some of the selected datasets, say so, so an empty table doesn't read as "not detected". */
function OutsideModeHint({
  matches,
  total,
  onAny,
}: {
  matches: { symbol: string; acc: string; arms: Set<number> }[];
  total: number;
  onAny: () => void;
}) {
  if (!matches.length) return null;
  const first = matches[0];
  const name = first.symbol || first.acc;
  return (
    <p className={styles.filterHint}>
      {matches.length === 1
        ? `${name} is in ${first.arms.size} of the ${total} selected datasets, so it is not listed here.`
        : `${matches.length} matching proteins are in some of the selected datasets but not this set.`}{" "}
      <button type="button" className={styles.linkButton} onClick={onAny}>
        Show proteins in any selected dataset
      </button>
    </p>
  );
}

/** Mode: "all" / "any" selected studies, or one exact intersection (sorted arm indices). */
type Mode = "all" | "any" | `c:${string}`;

function comboKey(arms: Set<number>, selected: number[]): string {
  return selected.filter((i) => arms.has(i)).join(",");
}

function SelectionPanel({
  arms,
  selected,
  countedIdx,
  counts,
  view,
}: {
  arms: StudyArm[];
  selected: number[];
  countedIdx: number[];
  /** The page's counting rule (baseline only, or with other conditions). */
  counts: (arm: StudyArm) => boolean;
  /** A preset over all counted datasets, or null for a hand-picked selection. */
  view: View | null;
}) {
  const consensus = view !== null;
  const [presence, setPresence] = useState<PresenceShard | null>(null);
  const [error, setError] = useState(false);
  // Bumped by the retry button, to re-run the load effect after a failure.
  const [attempt, setAttempt] = useState(0);
  // Filters start from the URL (pf, tiers, min, mode, ps) so Back restores them.
  const restored = useRef(param("pf") != null || param("tiers") != null || param("min") != null || param("mode") != null);
  // These may read the URL during render, unlike the page's own parameters above: this
  // panel renders nothing but "Loading protein lists…" until the shards arrive on the
  // client, so none of it reaches the prerendered HTML and none of it can mismatch on
  // hydration. Anything moved above that early return has to move into an effect.
  const [filter, setFilter] = useState(() => param("pf") ?? "");
  const [mode, setMode] = useState<Mode>(() => (param("mode") as Mode | null) ?? "any");
  // Same as the catalog's tier filter: nothing checked = every tier; checked tiers OR together.
  const [tierSel, setTierSel] = useState<Set<Tier>>(
    () => new Set((param("tiers")?.split(",").filter(Boolean) ?? []) as Tier[]),
  );
  const [limit, setLimit] = useState(PAGE);
  const [minCounted, setMinCounted] = useState(() => Number(param("min")) || 1);
  const [maxDb, setMaxDb] = useState(() => (param("maxdb") != null ? Number(param("maxdb")) : NOVEL_MAX_DB));
  // null = no surface-preference requirement.
  // Discovery views default to +10; the consensus list and comparisons to no filter.
  const prefDefault = view === "novel" || view === "review" ? NOVEL_MIN_PREF : null;
  const [minPref, setMinPref] = useState<number | null>(() =>
    param("minpref") === "any"
      ? null
      : param("minpref") != null
        ? Number(param("minpref"))
        : prefDefault,
  );
  useEffect(() => {
    // Keep filters restored from the URL on first mount; reset them on a later view change.
    if (restored.current) return;
    setMinCounted(view === "novel" || view === "review" ? DISCOVERY_MIN : 1);
    // Database-absent detections are dominated by abundant ER / cytosolic
    // background; start from the ones our deep dive also calls surface.
    setTierSel(new Set());
    setMaxDb(NOVEL_MAX_DB);
    setMinPref(view === "novel" || view === "review" ? NOVEL_MIN_PREF : null);
  }, [view]);
  const [showAllCombos, setShowAllCombos] = useState(false);
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<ProteinSort>(
    (() => {
      const [k, d] = (param("ps") ?? "").split(":");
      return k ? { key: k as ProteinSort, dir: d === "desc" ? "desc" : "asc" } : undefined;
    })(),
  );
  useEffect(() => {
    setParams({
      pf: filter.trim() || null,
      tiers: [...tierSel].join(",") || null,
      min: minCounted > 1 ? String(minCounted) : null,
      mode: mode !== "any" ? mode : null,
      ps: sortKey ? `${sortKey}:${sortDir}` : null,
      maxdb: view === "novel" && maxDb !== NOVEL_MAX_DB ? String(maxDb) : null,
      minpref: minPref !== prefDefault ? (minPref == null ? "any" : String(minPref)) : null,
    });
  }, [filter, tierSel, minCounted, mode, sortKey, sortDir, maxDb, minPref, view]);

  useEffect(() => {
    let live = true;
    setError(false);
    loadAllPresence().then(
      (p) => live && setPresence(p),
      () => live && setError(true),
    );
    return () => {
      live = false;
    };
  }, [attempt]);
  // An intersection stops making sense once the selection changes under it.
  const selKey = selected.join(",");
  useEffect(() => {
    if (restored.current) {
      // Restored from the URL: keep it this once, then behave normally.
      restored.current = false;
      return;
    }
    // Every protein any selected dataset detected; "In all" narrows to the shared ones.
    setMode("any");
    setLimit(PAGE);
  }, [selKey]);

  const counted = useMemo(() => new Set(countedIdx), [countedIdx]);
  const proteins = useMemo<Protein[]>(() => {
    if (!presence) return [];
    const sel = new Set(selected);
    const out: Protein[] = [];
    for (const [acc, e] of Object.entries(presence)) {
      const hit = e.a.filter((i) => sel.has(i));
      if (!hit.length) continue;
      out.push({
        acc,
        symbol: e.s,
        deep: e.d === 1,
        name: e.n ?? "",
        votes: e.v ?? null,
        tier: tierOf(e),
        arms: new Set(hit),
        nCounted: e.a.filter((i) => counted.has(i)).length,
        q: selected.length === 1 ? (e.q?.[String(selected[0])] ?? null) : null,
        pref: surfacePreference(e.p),
        prefRaw: e.p,
      });
    }
    return out;
  }, [presence, selected, counted]);

  const combos = useMemo(() => {
    if (selected.length < 2 || selected.length > MAX_UPSET) return [];
    const m = new Map<string, { key: string; members: Set<number>; n: number; nShort: number }>();
    for (const p of proteins) {
      const key = comboKey(p.arms, selected);
      let c = m.get(key);
      if (!c) {
        c = { key, members: new Set(p.arms), n: 0, nShort: 0 };
        m.set(key, c);
      }
      c.n += 1;
      if (p.tier === "canonical" || p.tier === "likely") c.nShort += 1;
    }
    return [...m.values()].sort((a, b) => b.n - a.n || b.members.size - a.members.size);
  }, [proteins, selected]);

  if (error)
    return (
      <p className={styles.empty} role="alert">
        Protein lists could not be loaded.{" "}
        <button type="button" className={styles.linkButton} onClick={() => setAttempt((n) => n + 1)}>
          Try again
        </button>
      </p>
    );
  if (!presence) return <p className={styles.empty}>Loading protein lists…</p>;

  const single = selected.length === 1;
  // Past MAX_UPSET a per-dataset legend and dot columns are noise; the counts carry it.
  const wide = selected.length > MAX_UPSET;
  const label = (i: number) => letter(selected.indexOf(i));
  const inAll = proteins.filter((p) => p.arms.size === selected.length).length;
  const f = filter.trim().toUpperCase();
  const inMode = proteins.filter((p) => {
    if (mode === "all") return p.arms.size === selected.length;
    if (mode.startsWith("c:")) return comboKey(p.arms, selected) === mode.slice(2);
    return true;
  });
  // Everything but the tier chips, so each chip's count is what checking it adds.
  const preTier = inMode.filter(
    (p) =>
      p.nCounted >= minCounted &&
      (view !== "novel" || (p.votes ?? 0) <= maxDb) &&
      (minPref == null || (p.pref.mean ?? -Infinity) >= minPref) &&
      (view !== "review" || p.tier === "low" || p.tier === "uncertain" || p.tier === "no"),
  );
  const filtered = preTier.filter(
    (p) =>
      (tierSel.size === 0 || tierSel.has(p.tier)) && (!f ||
        p.acc.includes(f) ||
        p.symbol.toUpperCase().includes(f) ||
        p.name.toUpperCase().includes(f)),
  );
  // Default order: most-detected first, so the strongest surface evidence leads.
  const shown =
    sortKey === null
      ? [...filtered].sort(
          (a, b) =>
            // New candidates lead with enrichment over background.
            (view === "novel" || view === "review"
              ? (b.pref.mean ?? -999) - (a.pref.mean ?? -999)
              : 0) ||
            b.arms.size - a.arms.size ||
            b.nCounted - a.nCounted ||
            Number(!a.symbol) - Number(!b.symbol) ||
            (a.symbol || a.acc).localeCompare(b.symbol || b.acc),
        )
      : sortRows(filtered, {
          protein: (p) => p.symbol || `~${p.acc}`,
          name: (p) => p.name || "~",
          votes: (p) => p.votes ?? -1,
          tier: (p) => TIER_ORDER.indexOf(p.tier),
          counted: (p) => p.nCounted,
          // Missing values sort last in either direction.
          amount: (p) => p.q?.[1] ?? (sortDir === "asc" ? Infinity : -Infinity),
          pref: (p) => p.pref.mean ?? (sortDir === "asc" ? Infinity : -Infinity),
        });
  const tierCount = (t: Tier) => preTier.filter((p) => p.tier === t).length;
  const modeLabel =
    mode === "all"
      ? selected.length === 2
        ? "in both selected datasets"
        : `in all ${selected.length} selected datasets`
      : mode === "any"
        ? "in any selected dataset"
        : `in exactly ${mode
            .slice(2)
            .split(",")
            .map((i) => label(Number(i)))
            .join(" + ")}`;

  const downloadCsv = () => {
    const head = [
      "symbol",
      "name",
      "uniprot_acc",
      "db_votes_of_5",
      "surfaceome_tier",
      "n_counted_datasets_detected",
      "surface_pref_vs_procan",
      "surface_pref_vs_membrane",
      ...(single && arms[selected[0]].quant_unit
        ? [`amount_${(arms[selected[0]].quant_unit ?? "").replace(/\W+/g, "_")}`, "percentile_in_dataset"]
        : []),
      ...selected.map((i) => arms[i].id),
    ];
    const csv = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const lines = [head.join(",")];
    for (const p of shown) {
      lines.push(
        [
          csv(p.symbol),
          csv(p.name),
          p.acc,
          p.votes ?? "",
          p.tier === "none" ? "not_deep_dived" : p.tier,
          p.nCounted,
          p.pref.vsProcan ?? "",
          p.pref.vsMembrane ?? "",
          ...(single && arms[selected[0]].quant_unit ? [p.q?.[0] ?? "", p.q?.[1] ?? ""] : []),
          ...selected.map((i) => (p.arms.has(i) ? 1 : 0)),
        ].join(","),
      );
    }
    const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `surface-proteomics-${single ? arms[selected[0]].id : `${selected.length}-studies`}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const pHeader = (k: ProteinSort, text: string, num = false, info?: ReactNode) => (
    <th aria-sort={ariaSort(k)} className={num ? styles.num : undefined}>
      <span className={styles.headWithTip}>
        <SortableHeader k={k} active={sortKey === k} direction={sortDir} onSort={onSort}>
          {text}
        </SortableHeader>
        {info ? (
          <InfoTip wide align="end" label={`About ${text}`}>
            {info}
          </InfoTip>
        ) : null}
      </span>
    </th>
  );
  const maxCombo = combos[0]?.n ?? 1;
  const visibleCombos = showAllCombos ? combos : combos.slice(0, UPSET_ROWS);
  const nCanonical = proteins.filter((p) => p.tier === "canonical").length;
  const nLikely = proteins.filter((p) => p.tier === "likely").length;

  return (
    <section className={styles.panel} aria-label="Selected studies">
      <h2 className={`h-section ${styles.sectionTitle}`}>
        {view === "novel"
          ? "New surface candidates"
          : view === "review"
            ? "Possible misses: surface-detected, but not in our Canonical or Likely tiers"
            : consensus
          ? "Consensus surface list"
          : single
            ? `Proteins in ${shortCitation(arms[selected[0]])}`
            : `Comparing ${selected.length} datasets`}
      </h2>
      <p className={styles.summary}>
        {view === "novel" ? (
          <>
            Proteins detected on intact cells by at least {minCounted} counted dataset
            {minCounted === 1 ? "" : "s"}, listed as surface by at most {maxDb} of the five
            surfaceome databases (UniProt, GO, SURFY, CSPA, HPA)
            {minPref == null ? "" : `, and ranking at least ${minPref > 0 ? "+" : ""}${minPref} points higher in surface preps than in the whole proteome and membrane preps`}
            . Sorted by surface preference. The enrichment filter is what keeps out abundant ER
            and cytosolic background; blank it to see every detection. Watch for known
            look-alikes: naturally biotinylated carboxylases (PCCA, ACACA, MCCC1) in biotin
            datasets, skin contaminants (hornerin, filaggrin-2), and serum or matrix proteins that
            stick to cells.
          </>
        ) : view === "review" ? (
          <>
            Proteins detected on intact cells by at least {minCounted} counted dataset
            {minCounted === 1 ? "" : "s"}
            {minPref == null ? "" : ` and ranking at least ${minPref > 0 ? "+" : ""}${minPref} points higher in surface preps than in the whole proteome and membrane preps`}
            , that our deep dive rated Low confidence, Uncertain or Not surface. Sorted by surface
            preference. These are where the data and our calls disagree most: either the deep dive
            missed surface evidence, or the enrichment has another cause (see the look-alikes
            under New candidates). Blank the enrichment filter to see every detection.
          </>
        ) : consensus ? (
          <>
            <strong>{proteins.length.toLocaleString("en-US")}</strong> proteins were detected by at
            least one of the {selected.length} counted datasets, ranked by how many of them
            found each one, so the proteins most experiments agree on come first.
          </>
        ) : single ? (
          <>
            <strong>{proteins.length.toLocaleString("en-US")}</strong> proteins.
          </>
        ) : (
          <>
            <strong>{inAll.toLocaleString("en-US")}</strong> proteins in{" "}
            {selected.length === 2 ? "both" : `all ${selected.length}`},{" "}
            <strong>{proteins.length.toLocaleString("en-US")}</strong> in at least one.
          </>
        )}{" "}
        {view === "novel" || view === "review" ? null : (
          <>
            Of these, {nCanonical.toLocaleString("en-US")} are Canonical and{" "}
            {nLikely.toLocaleString("en-US")} Likely Surfaceome proteins.
          </>
        )}
      </p>

      {!single && wide ? null : !single ? (
        <ol className={styles.legend}>
          {selected.map((i) => (
            <li key={i}>
              <span className={styles.letter}>{label(i)}</span>
              <span>
                <strong>{shortCitation(arms[i])}</strong> · {arms[i].name}{" "}
                <span className={styles.sub}>
                  ({arms[i].n_proteins.toLocaleString("en-US")} proteins
                  {counts(arms[i]) ? "" : `; ${armStatusLabel(arms[i]).toLowerCase()}, not counted`})
                </span>
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      {single && !counts(arms[selected[0]]) ? (
        <p className={styles.caveat}>{STATUS_HELP[arms[selected[0]].status]}</p>
      ) : null}
      {single && !consensus ? <MethodsPanel key={arms[selected[0]].id} arm={arms[selected[0]]} /> : null}
      {!single && selected.some((i) => !counts(arms[i])) ? (
        <p className={styles.caveat}>
          The selection includes datasets that are not counted as surface evidence (held, high background, pre-filtered by surface annotation, membrane fractions, or other conditions of a study's samples).
        </p>
      ) : null}

      {combos.length > 0 ? (
        <div className={styles.upset}>
          <h3 className={styles.subTitle}>Intersections</h3>
          <p className={styles.sub}>
            Each row is one exact combination of the selected datasets: proteins found in the
            filled ones and in none of the others, largest group first. Click a row to list those
            proteins below.
          </p>
          <p className={styles.totals}>
            Totals:{" "}
            {selected.map((i, k) => (
              <span key={i}>
                {k ? " · " : ""}
                <strong>{label(i)}</strong> {arms[i].n_proteins.toLocaleString("en-US")}
              </span>
            ))}
            . Each dataset&apos;s total is the sum of the rows its dot is filled in.
          </p>
          <div className={styles.tableScroll}>
            <table className={`${styles.table} ${styles.upsetTable}`}>
              <thead>
                <tr>
                  {selected.map((i) => (
                    <th key={i} className={styles.center}>
                      <HoverTip tip={`${shortCitation(arms[i])}: ${arms[i].name}`}>{label(i)}</HoverTip>
                    </th>
                  ))}
                  <th>Found in</th>
                  <th>Proteins</th>
                  <th className={styles.num}>
                    Canonical + Likely
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleCombos.map((c) => {
                  const active = mode === `c:${c.key}`;
                  const pick = () => {
                    setMode(active ? "any" : `c:${c.key}`);
                    setLimit(PAGE);
                  };
                  return (
                    <tr key={c.key} className={`${styles.upsetRow} ${active ? styles.selectedRow : ""}`} onClick={pick}>
                      {selected.map((i) => (
                        <td key={i} className={styles.center}>
                          <span className={c.members.has(i) ? styles.memberOn : styles.memberOff} />
                        </td>
                      ))}
                      <td className={styles.comboText}>{describeCombo(c.members, selected, label)}</td>
                      <td className={styles.upsetBarCell}>
                        <button
                          type="button"
                          className={styles.upsetButton}
                          aria-pressed={active}
                          onClick={(e) => {
                            e.stopPropagation();
                            pick();
                          }}
                        >
                          <span className={styles.upsetBar} style={{ width: `${Math.max(1, (c.n / maxCombo) * 100)}%` }} />
                          <span className={styles.upsetNum}>{c.n.toLocaleString("en-US")}</span>
                        </button>
                      </td>
                      <td className={styles.num}>{c.nShort.toLocaleString("en-US")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {combos.length > UPSET_ROWS ? (
            <button type="button" className={styles.linkButton} onClick={() => setShowAllCombos((v) => !v)}>
              {showAllCombos ? "show fewer" : `show all ${combos.length} intersections`}
            </button>
          ) : null}
          <details className={styles.pairwise}>
            <summary>Pairwise overlap</summary>
            <OverlapMatrix arms={arms} selected={selected} proteins={proteins} label={label} />
          </details>
        </div>
      ) : !single ? (
        <p className={styles.sub}>
          {consensus
            ? "Intersections are shown when you compare up to " + MAX_UPSET + " datasets."
            : `Select ${MAX_UPSET} or fewer datasets to see their exact intersections; the protein list below works for any selection.`}
        </p>
      ) : null}

      <h3 className={styles.subTitle}>Proteins {single || consensus ? "" : modeLabel}</h3>
      <div className={styles.controls}>
        <input
          type="search"
          className={styles.search}
          placeholder="Filter by symbol, name or accession…"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setLimit(PAGE);
          }}
          aria-label="Filter proteins"
        />
        {!single && !consensus ? (
          <div className={styles.segmented} role="group" aria-label="Which proteins to list">
            {(
              [
                ["all", selected.length === 2 ? "In both" : `In all ${selected.length}`],
                ["any", "In any"],
              ] as const
            ).map(([m, text]) => (
              <button
                key={m}
                type="button"
                className={styles.chip}
                data-on={mode === m ? "true" : "false"}
                aria-pressed={mode === m}
                onClick={() => {
                  setMode(m);
                  setLimit(PAGE);
                }}
              >
                {text}
              </button>
            ))}
            {mode.startsWith("c:") ? (
              <button
                type="button"
                className={styles.chip}
                data-on="true"
                aria-pressed="true"
                aria-label="Clear this intersection"
                onClick={() => setMode("any")}
              >
                {describeCombo(new Set(mode.slice(2).split(",").map(Number)), selected, label)} ×
              </button>
            ) : null}
          </div>
        ) : null}
        <label className={styles.minCount}>
          Found in at least
          <input
            type="number"
            min={1}
            max={countedIdx.length}
            value={minCounted}
            onChange={(e) => {
              const v = Math.max(1, Math.min(countedIdx.length, Number(e.target.value) || 1));
              setMinCounted(v);
              setLimit(PAGE);
            }}
            aria-label="Minimum number of counted datasets"
          />
          counted dataset{minCounted === 1 ? "" : "s"}
        </label>
        {view === "novel" ? (
          <>
            <label className={styles.minCount}>
              Listed by at most
              <input
                type="number"
                min={0}
                max={5}
                value={maxDb}
                onChange={(e) => {
                  setMaxDb(Math.max(0, Math.min(5, Number(e.target.value) || 0)));
                  setLimit(PAGE);
                }}
                aria-label="Maximum number of surfaceome databases listing it"
              />
              of 5 databases
            </label>
          </>
        ) : null}
        <label className={styles.minCount}>
          Surface pref. at least
          <input
            type="number"
            min={-100}
            max={100}
            step={5}
            value={minPref ?? ""}
            placeholder="any"
            onChange={(e) => {
              const raw = e.target.value.trim();
              setMinPref(raw === "" ? null : Math.max(-100, Math.min(100, Number(raw))));
              setLimit(PAGE);
            }}
            aria-label="Minimum surface preference (blank for any)"
          />
          <span className={styles.sub}>(blank = any)</span>
        </label>
        <ChipGroup
          label="Tier"
          options={TIER_ORDER}
          labelOf={(t) => TIER_LABEL[t]}
          countOf={tierCount}
          value={tierSel}
          onChange={(v) => {
            setTierSel(v);
            setLimit(PAGE);
          }}
        />
        <span className={styles.filterHint}>
          {tierSel.size === 0 ? (
            "All tiers shown; check tiers to narrow (they combine with OR)"
          ) : (
            <button type="button" className={styles.linkButton} onClick={() => setTierSel(new Set())}>
              show all tiers
            </button>
          )}
        </span>
      </div>
      <p className={styles.linkHint}>
        Click a protein name to open its page in the Surfaceome viewer, with the full evidence
        record. Names in gray were not deep-dived, so they link to their UniProt entry instead.
      </p>
      {shown.length === 0 && f && mode !== "any" ? (
        <OutsideModeHint
          matches={proteins.filter(
            (p) =>
              p.acc.includes(f) ||
              p.symbol.toUpperCase().includes(f) ||
              p.name.toUpperCase().includes(f),
          )}
          total={selected.length}
          onAny={() => setMode("any")}
        />
      ) : null}
      <div className={styles.count}>
        {shown.length.toLocaleString("en-US")} protein{shown.length === 1 ? "" : "s"}
        <button type="button" className={styles.linkButton} onClick={downloadCsv}>
          download CSV
        </button>
        <SortResetButton visible={sortKey !== null} onReset={reset} />
      </div>

      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              {pHeader("protein", "Protein")}
              {pHeader("name", "Name")}
              {pHeader("votes", "DB votes", true, tooltips.db_votes)}
              {pHeader("tier", "Surfaceome tier")}
              {pHeader("counted", `Counted datasets (of ${countedIdx.length})`)}
              {pHeader(
                "pref",
                "Surface pref.",
                false,
                <>
                  How much higher the protein ranks in surface preps than in two backgrounds,
                  in percentile points. It averages two comparisons: its median percentile in
                  the counted surface datasets minus (1) its percentile in the ProCan whole
                  proteome (949 cancer cell lines,{" "}
                  <a href="https://pubmed.ncbi.nlm.nih.gov/35839778/" target="_blank" rel="noreferrer">
                    PMID 35839778
                  </a>
                  ) and (2) its median percentile in our membrane-fraction datasets. +10 or more
                  (green) is surface-enriched; −10 or less (yellow) looks like intracellular
                  carryover. Hover a value for both comparisons. Blank: quantified in fewer than
                  5 counted datasets.
                </>,
              )}
              {single && arms[selected[0]].quant_unit
                ? pHeader("amount", `Amount here (${arms[selected[0]].quant_unit})`)
                : null}
              {!single && !wide
                ? selected.map((i) => (
                    <th key={i} className={styles.center}>
                      <HoverTip tip={`${shortCitation(arms[i])}: ${arms[i].name}`}>{label(i)}</HoverTip>
                    </th>
                  ))
                : null}
            </tr>
          </thead>
          <tbody>
            {shown.slice(0, limit).map((p) => (
              <tr key={p.acc}>
                <td>
                  {p.deep && p.symbol ? (
                    <Link
                      href={`/${p.symbol}/`}
                      className={styles.protein}
                    >
                      {p.symbol}
                    </Link>
                  ) : (
                    <a
                      href={`https://www.uniprot.org/uniprotkb/${p.acc}/entry`}
                      target="_blank"
                      rel="noreferrer"
                      className={styles.noPage}
                      aria-label={`${p.symbol || p.acc}: not deep-dived; opens UniProt ${p.acc}`}
                    >
                      {p.symbol || p.acc}
                    </a>
                  )}
                </td>
                <td className={styles.nameCell}>{p.name || "—"}</td>
                <td className={styles.num}>
                  {p.votes ?? "—"}
                </td>
                <td>
                  <TierPill tier={p.tier} />
                </td>
                <td className={styles.countedCell}>
                  <span className={styles.countedNum}>{p.nCounted}</span>
                  <Bar value={p.nCounted / Math.max(1, countedIdx.length)} />
                </td>
                {/* Left-aligned like Proteins: the cell is a widget, not a bare
                    number, so a right-aligned header would sit well left of it. */}
                <td className={styles.countCell}>
                  <PrefCell pref={p.pref} raw={p.prefRaw} />
                </td>
                {single && arms[selected[0]].quant_unit ? (
                  <td className={styles.countedCell}>
                    {p.q ? (
                      <>
                        <span className={styles.amountNum}>{formatQuant(p.q[0])}</span>
                        <span className={styles.sub}> {ordinalPct(p.q[1])}</span>
                      </>
                    ) : (
                      <span className={styles.sub}>—</span>
                    )}
                  </td>
                ) : null}
                {!single && !wide
                  ? selected.map((i) => (
                      <td key={i} className={styles.center}>
                        <span className={p.arms.has(i) ? styles.memberOn : styles.memberOff} />
                      </td>
                    ))
                  : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {shown.length > limit ? (
        <button type="button" className={styles.linkButton} onClick={() => setLimit((l) => l + PAGE * 5)}>
          Show more ({(shown.length - limit).toLocaleString("en-US")} remaining)
        </button>
      ) : null}
    </section>
  );
}

function OverlapMatrix({
  arms,
  selected,
  proteins,
  label,
}: {
  arms: StudyArm[];
  selected: number[];
  proteins: Protein[];
  label: (i: number) => string;
}) {
  const n = selected.length;
  const shared: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
  for (const p of proteins) {
    for (let a = 0; a < n; a++) {
      if (!p.arms.has(selected[a])) continue;
      for (let b = 0; b < n; b++) if (p.arms.has(selected[b])) shared[a][b] += 1;
    }
  }
  return (
    <div className={styles.tableScroll}>
      <table className={`${styles.table} ${styles.matrix}`}>
        <caption className={styles.sub}>
          Proteins shared by each pair, with the Jaccard index (shared ÷ combined) in brackets. The
          diagonal is each study&apos;s total.
        </caption>
        <thead>
          <tr>
            <th />
            {selected.map((i) => (
              <th key={i} className={styles.num}>
                <HoverTip tip={`${shortCitation(arms[i])}: ${arms[i].name}`}>{label(i)}</HoverTip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {selected.map((i, a) => (
            <tr key={i}>
              <th scope="row">
                {label(i)} <span className={styles.sub}>{shortCitation(arms[i])}</span>
              </th>
              {selected.map((j, b) => {
                const union = shared[a][a] + shared[b][b] - shared[a][b];
                return (
                  <td key={j} className={styles.num}>
                    {shared[a][b].toLocaleString("en-US")}
                    {a !== b && union > 0 ? (
                      <span className={styles.sub}> ({(shared[a][b] / union).toFixed(2)})</span>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** "Only A", "A and B, not C", "All three" — an exact intersection in words. */
function describeCombo(members: Set<number>, selected: number[], label: (i: number) => string): string {
  const inn = selected.filter((i) => members.has(i)).map(label);
  const out = selected.filter((i) => !members.has(i)).map(label);
  if (!out.length) return selected.length === 2 ? "Both" : selected.length === 3 ? "All three" : `All ${selected.length}`;
  if (inn.length === 1) return `Only ${inn[0]}`;
  return `${inn.join(" and ")}, not ${out.join(" or ")}`;
}

/** Mean surface preference, colored by verdict; both comparisons on hover. */
function PrefCell({
  pref,
  raw,
}: {
  pref: ReturnType<typeof surfacePreference>;
  raw: PresenceEntry["p"];
}) {
  if (pref.mean == null || !raw) return <span className={styles.sub}>—</span>;
  const cls =
    pref.verdict === "enriched" ? styles.prefPos : pref.verdict === "carryover" ? styles.prefNeg : "";
  const sign = (x: number) => (x > 0 ? `+${x}` : `${x}`);
  return (
    <HoverTip
      tip={
        <>
          {pref.verdict ? <strong>{PREF_LABEL[pref.verdict]}. </strong> : null}
          Median {ordinalPct(raw[0])} in counted surface datasets
          {pref.vsProcan != null && raw[2] != null
            ? `; ${sign(pref.vsProcan)} vs the ProCan whole proteome (${ordinalPct(raw[2])})`
            : ""}
          {pref.vsMembrane != null && raw[1] != null
            ? `; ${sign(pref.vsMembrane)} vs membrane-fraction datasets (${ordinalPct(raw[1])})`
            : "; too few membrane-fraction values to compare"}
          .
        </>
      }
    >
      <span className={`${styles.prefNum} ${cls}`}>{sign(pref.mean)}</span>
    </HoverTip>
  );
}

/** The paper itself: PubMed and DOI links. */
function PaperLinks({ arm }: { arm: StudyArm }) {
  if (!arm.pmid && !arm.doi) return null;
  return (
    <div className={styles.paperLinks}>
      {arm.pmid ? (
        <a href={`https://pubmed.ncbi.nlm.nih.gov/${arm.pmid}/`} target="_blank" rel="noreferrer">
          PMID {arm.pmid}
        </a>
      ) : null}
      {arm.doi ? (
        <a href={`https://doi.org/${arm.doi}`} target="_blank" rel="noreferrer">
          DOI
        </a>
      ) : null}
    </div>
  );
}

/** One dataset's own sources: its tab in the shared study workbook, and
 *  where its raw instrument files are (from the S3E8 raw-data audit). */
export function ArmSources({
  arm,
  studyList,
}: {
  arm: StudyArm;
  studyList?: { name: string; url: string };
}) {
  const raw = arm.raw_data;
  const accs = raw?.accessions ?? arm.repository_ids;
  const rawHref = raw?.url ?? (accs.length ? repositoryUrl(accs[0]) : null);
  return (
    <div className={styles.paperLinks}>
      {studyList && arm.sheet_tab ? (
        <a
          href={studyList.url}
          target="_blank"
          rel="noreferrer"
          title={`Opens ${studyList.name}; this dataset is on the tab named ${arm.sheet_tab}`}
        >
          Study list, tab “{arm.sheet_tab}”
        </a>
      ) : null}
      {raw ? (
        raw.flag === "raw_not_deposited" || raw.flag === "accession_invalid" || !accs.length ? (
          <span className={styles.sub}>{RAW_FLAG_LABEL[raw.flag]}</span>
        ) : (
          <span className={styles.sub}>
            {rawHref ? (
              <a href={rawHref} target="_blank" rel="noreferrer">
                {raw.repository ? `${raw.repository} ` : ""}
                {accs.join(", ")}
              </a>
            ) : (
              `${raw.repository ? `${raw.repository} ` : ""}${accs.join(", ")}`
            )}
            : {RAW_FLAG_LABEL[raw.flag]}
          </span>
        )
      ) : accs.length ? (
        <span className={styles.sub}>
          {arm.repository ? `${arm.repository} ` : ""}
          {accs.join(", ")}
        </span>
      ) : null}
    </div>
  );
}
