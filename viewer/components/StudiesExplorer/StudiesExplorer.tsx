"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  isCounted,
  letter,
  loadAllPresence,
  METHOD_CLASS_LABEL,
  OVERLAP_SCREEN,
  shortCitation,
  STATUS_HELP,
  STATUS_LABEL,
  TIER_LABEL,
  TIER_ORDER,
  type ArmStatus,
  type MethodClass,
  type PresenceShard,
  type StudyArm,
  type StudyIndex,
  type TierCode,
  type TierMap,
} from "../../lib/surface-proteomics";
import { statusTone } from "../surfaceome/ExpressionCard/StudyPresence";
import { SortableHeader } from "../surfaceome/_shared/SortableHeader";
import { SortResetButton } from "../surfaceome/_shared/SortResetButton";
import { useTableSort, type SortValue } from "../surfaceome/_shared/useTableSort";
import { StatusPill } from "../surfaceome/StatusPill/StatusPill";
import { TierPill } from "./TierPill";
import styles from "./StudiesExplorer.module.css";

interface Props {
  index: StudyIndex;
  tiers: TierMap;
}

type Tier = TierCode | "none";
type StudySort = "study" | "year" | "method" | "sample" | "n" | "overlap" | "status";
type ProteinSort = "protein" | "tier" | "counted";

const STATUS_ORDER: ArmStatus[] = ["core", "provisional", "held", "below_screen", "comparator"];
const CLASS_ORDER: MethodClass[] = ["intact_cell", "fractionation", "lysate"];
const PAGE = 200;
/** Above this many selected studies the exact-intersection list stops being readable. */
const MAX_UPSET = 10;
const UPSET_ROWS = 15;

interface Protein {
  acc: string;
  symbol: string;
  deep: boolean;
  tier: Tier;
  /** Indices of the selected arms that list it. */
  arms: Set<number>;
  /** Counted arms (anywhere in the compendium) that detect it. */
  nCounted: number;
}

function readSelection(): string[] {
  if (typeof window === "undefined") return [];
  const v = new URLSearchParams(window.location.search).get("arm");
  return v ? v.split(",").filter(Boolean) : [];
}

const pct = (x: number | null) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export function StudiesExplorer({ index, tiers }: Props) {
  const arms = index.arms;
  const idxById = useMemo(() => new Map(arms.map((a, i) => [a.id, i])), [arms]);
  const countedIdx = useMemo(() => arms.flatMap((a, i) => (isCounted(a) ? [i] : [])), [arms]);
  const [query, setQuery] = useState("");
  const [statuses, setStatuses] = useState<Set<ArmStatus>>(new Set(STATUS_ORDER));
  const [classes, setClasses] = useState<Set<MethodClass>>(new Set(CLASS_ORDER));
  const [selected, setSelected] = useState<number[]>([]);
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<StudySort>();

  // Selection lives in ?arm=a,b so a gene page's dots can deep-link to a study.
  useEffect(() => {
    const ids = readSelection();
    setSelected(ids.map((id) => idxById.get(id)).filter((i): i is number => i !== undefined));
  }, [idxById]);
  const updateSelected = useCallback(
    (next: number[]) => {
      setSelected(next);
      const url = new URL(window.location.href);
      if (next.length) url.searchParams.set("arm", next.map((i) => arms[i].id).join(","));
      else url.searchParams.delete("arm");
      window.history.replaceState(null, "", url.toString());
    },
    [arms],
  );
  const toggle = (i: number) =>
    updateSelected(selected.includes(i) ? selected.filter((x) => x !== i) : [...selected, i]);

  const q = query.trim().toLowerCase();
  const visible = arms
    .map((arm, i) => ({ arm, i }))
    .filter(
      ({ arm }) =>
        statuses.has(arm.status) &&
        classes.has(arm.method_class) &&
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
    method: (r) => `${r.arm.method_class} ${r.arm.family_label}`,
    sample: (r) => r.arm.sample ?? "",
    n: (r) => r.arm.n_proteins,
    overlap: (r) => r.arm.reference_overlap ?? -1,
    status: (r) => STATUS_ORDER.indexOf(r.arm.status),
  };
  const rows = sortRows(visible, comparators);
  const maxN = Math.max(...arms.map((a) => a.n_proteins));
  const letterOf = new Map(selected.map((i, k) => [i, letter(k)]));

  const header = (k: StudySort, label: string, num = false) => (
    <th aria-sort={ariaSort(k)} className={num ? styles.num : undefined}>
      <SortableHeader k={k} active={sortKey === k} direction={sortDir} onSort={onSort}>
        {label}
      </SortableHeader>
    </th>
  );

  return (
    <div className={styles.wrap}>
      <h2 className={`h-section ${styles.sectionTitle}`}>1 · Pick studies</h2>
      <div className={styles.controls}>
        <input
          type="search"
          className={styles.search}
          placeholder="Search author, cell type, method, PMID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search studies"
        />
        <ChipGroup
          label="Status"
          options={STATUS_ORDER}
          labelOf={(s) => STATUS_LABEL[s]}
          titleOf={(s) => STATUS_HELP[s]}
          countOf={(s) => arms.filter((a) => a.status === s).length}
          value={statuses}
          onChange={setStatuses}
        />
        <ChipGroup
          label="Method"
          options={CLASS_ORDER}
          labelOf={(c) => METHOD_CLASS_LABEL[c]}
          countOf={(c) => arms.filter((a) => a.method_class === c).length}
          value={classes}
          onChange={setClasses}
        />
      </div>

      <div className={styles.count}>
        {rows.length} of {arms.length} arms shown
        {selected.length > 0 ? ` · ${selected.length} selected` : ""}
        <button type="button" className={styles.linkButton} onClick={() => updateSelected(countedIdx)}>
          select all {countedIdx.length} counted arms
        </button>
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
              {header("sample", "Cell type / sample")}
              {header("n", "Proteins", true)}
              {header("overlap", "Surface overlap")}
              {header("status", "Status")}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ arm, i }) => {
              const sel = selected.includes(i);
              const counted = isCounted(arm);
              return (
                <tr
                  key={arm.id}
                  className={`${sel ? styles.selectedRow : ""} ${counted ? "" : styles.notCounted}`}
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
                      {shortCitation(arm)}
                    </button>
                    <div className={styles.sub}>{arm.name}</div>
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
                      {arm.repository_ids.length ? (
                        <span className={styles.sub}>
                          {arm.repository ? `${arm.repository} ` : ""}
                          {arm.repository_ids.join(", ")}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td>{arm.year ?? "—"}</td>
                  <td>
                    <span className={styles.method}>
                      <span className={`${styles.swatch} ${styles[`sw_${arm.method_class}`]}`} aria-hidden="true" />
                      {METHOD_CLASS_LABEL[arm.method_class]}
                    </span>
                    <div className={styles.sub}>{arm.family_label}</div>
                  </td>
                  <td className={styles.sample}>{arm.sample}</td>
                  <td className={styles.num}>
                    {arm.n_proteins.toLocaleString("en-US")}
                    <Bar value={arm.n_proteins / maxN} />
                  </td>
                  <td>
                    <OverlapBar value={arm.reference_overlap} intact={arm.method_class === "intact_cell"} />
                  </td>
                  <td>
                    <StatusPill size="sm" tone={statusTone(arm.status)} title={STATUS_HELP[arm.status]} nativeTooltip>
                      {STATUS_LABEL[arm.status]}
                    </StatusPill>
                    <div className={counted ? styles.countedYes : styles.countedNo}>
                      {counted ? "counted" : "not counted"}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected.length > 0 ? (
        <SelectionPanel arms={arms} selected={selected} tiers={tiers} countedIdx={countedIdx} />
      ) : (
        <p className={styles.hint}>
          Tick one or more studies above (or select all counted arms) to see their proteins and
          where the lists intersect.
        </p>
      )}
    </div>
  );
}

function Bar({ value }: { value: number }) {
  return (
    <span className={styles.bar} aria-hidden="true">
      <span style={{ width: `${Math.max(2, value * 100)}%` }} />
    </span>
  );
}

/** Surface overlap with a tick at the screen an intact-cell arm must reach. */
function OverlapBar({ value, intact }: { value: number | null; intact: boolean }) {
  if (value == null) return <span className={styles.sub}>—</span>;
  const pass = value >= OVERLAP_SCREEN;
  return (
    <span
      className={styles.overlap}
      title={`${pct(value)} of this study's proteins are established surface proteins${
        intact ? ` (counted arms need ≥${pct(OVERLAP_SCREEN)})` : ""
      }`}
    >
      <span className={styles.overlapTrack}>
        <span
          className={`${styles.overlapFill} ${intact ? (pass ? styles.pass : styles.fail) : styles.na}`}
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
        <span className={styles.overlapTick} style={{ left: `${OVERLAP_SCREEN * 100}%` }} />
      </span>
      <span className={styles.overlapNum}>{pct(value)}</span>
    </span>
  );
}

function ChipGroup<T extends string>({
  label,
  options,
  labelOf,
  titleOf,
  countOf,
  value,
  onChange,
}: {
  label: string;
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
      {options.map((o) => {
        const on = value.has(o);
        return (
          <button
            key={o}
            type="button"
            className={styles.chip}
            data-on={on ? "true" : "false"}
            aria-pressed={on}
            title={titleOf?.(o)}
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
      })}
    </fieldset>
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
  tiers,
  countedIdx,
}: {
  arms: StudyArm[];
  selected: number[];
  tiers: TierMap;
  countedIdx: number[];
}) {
  const [presence, setPresence] = useState<PresenceShard | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("");
  const [mode, setMode] = useState<Mode>("any");
  const [tierSel, setTierSel] = useState<Set<Tier>>(new Set(TIER_ORDER));
  const [limit, setLimit] = useState(PAGE);
  const [showAllCombos, setShowAllCombos] = useState(false);
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<ProteinSort>();

  useEffect(() => {
    loadAllPresence().then(setPresence, () => setError(true));
  }, []);
  // An intersection stops making sense once the selection changes under it.
  const selKey = selected.join(",");
  useEffect(() => {
    setMode(selKey.includes(",") && selKey.split(",").length <= MAX_UPSET ? "all" : "any");
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
        tier: tiers[acc] ?? "none",
        arms: new Set(hit),
        nCounted: e.a.filter((i) => counted.has(i)).length,
      });
    }
    return out;
  }, [presence, selected, tiers, counted]);

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

  if (error) return <p className={styles.empty}>Protein lists could not be loaded.</p>;
  if (!presence) return <p className={styles.empty}>Loading protein lists…</p>;

  const single = selected.length === 1;
  const label = (i: number) => letter(selected.indexOf(i));
  const inAll = proteins.filter((p) => p.arms.size === selected.length).length;
  const f = filter.trim().toUpperCase();
  const inMode = proteins.filter((p) => {
    if (mode === "all") return p.arms.size === selected.length;
    if (mode.startsWith("c:")) return comboKey(p.arms, selected) === mode.slice(2);
    return true;
  });
  const filtered = inMode.filter(
    (p) => tierSel.has(p.tier) && (!f || p.acc.includes(f) || p.symbol.toUpperCase().includes(f)),
  );
  // Default order: most-detected first, so the strongest surface evidence leads.
  const shown =
    sortKey === null
      ? [...filtered].sort(
          (a, b) =>
            b.arms.size - a.arms.size ||
            b.nCounted - a.nCounted ||
            Number(!a.symbol) - Number(!b.symbol) ||
            (a.symbol || a.acc).localeCompare(b.symbol || b.acc),
        )
      : sortRows(filtered, {
          protein: (p) => p.symbol || `~${p.acc}`,
          tier: (p) => TIER_ORDER.indexOf(p.tier),
          counted: (p) => p.nCounted,
        });
  const tierCount = (t: Tier) => inMode.filter((p) => p.tier === t).length;
  const modeLabel =
    mode === "all"
      ? `in all ${selected.length} selected studies`
      : mode === "any"
        ? "in any selected study"
        : `in exactly ${mode
            .slice(2)
            .split(",")
            .map((i) => label(Number(i)))
            .join(" + ")}`;

  const downloadCsv = () => {
    const head = ["symbol", "uniprot_acc", "surfaceome_tier", "n_counted_arms_detected", ...selected.map((i) => arms[i].id)];
    const lines = [head.join(",")];
    for (const p of shown) {
      lines.push(
        [
          p.symbol,
          p.acc,
          p.tier === "none" ? "not_deep_dived" : p.tier,
          p.nCounted,
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

  const pHeader = (k: ProteinSort, text: string, num = false) => (
    <th aria-sort={ariaSort(k)} className={num ? styles.num : undefined}>
      <SortableHeader k={k} active={sortKey === k} direction={sortDir} onSort={onSort}>
        {text}
      </SortableHeader>
    </th>
  );
  const maxCombo = combos[0]?.n ?? 1;
  const visibleCombos = showAllCombos ? combos : combos.slice(0, UPSET_ROWS);
  const nCanonical = proteins.filter((p) => p.tier === "canonical").length;
  const nLikely = proteins.filter((p) => p.tier === "likely").length;

  return (
    <section className={styles.panel} aria-label="Selected studies">
      <h2 className={`h-section ${styles.sectionTitle}`}>
        2 · {single ? `Proteins in ${shortCitation(arms[selected[0]])}` : `Compare ${selected.length} studies`}
      </h2>
      <p className={styles.summary}>
        {single ? (
          <>
            <strong>{proteins.length.toLocaleString("en-US")}</strong> proteins.
          </>
        ) : (
          <>
            <strong>{inAll.toLocaleString("en-US")}</strong> proteins in all {selected.length},{" "}
            <strong>{proteins.length.toLocaleString("en-US")}</strong> in at least one.
          </>
        )}{" "}
        Of these, {nCanonical.toLocaleString("en-US")} are Canonical and {nLikely.toLocaleString("en-US")}{" "}
        Likely Surfaceome proteins.
      </p>

      {!single ? (
        <ol className={styles.legend}>
          {selected.map((i) => (
            <li key={i}>
              <span className={styles.letter}>{label(i)}</span>
              <span>
                <strong>{shortCitation(arms[i])}</strong> · {arms[i].sample}{" "}
                <span className={styles.sub}>
                  ({arms[i].n_proteins.toLocaleString("en-US")} proteins
                  {isCounted(arms[i]) ? "" : `; ${STATUS_LABEL[arms[i].status].toLowerCase()}, not counted`})
                </span>
              </span>
            </li>
          ))}
        </ol>
      ) : null}

      {single && !isCounted(arms[selected[0]]) ? (
        <p className={styles.caveat}>{STATUS_HELP[arms[selected[0]].status]}</p>
      ) : null}
      {!single && selected.some((i) => !isCounted(arms[i])) ? (
        <p className={styles.caveat}>
          The selection includes arms that are not counted as surface detections (held, below screen
          or comparators).
        </p>
      ) : null}

      {combos.length > 0 ? (
        <div className={styles.upset}>
          <h3 className={styles.subTitle}>Intersections</h3>
          <p className={styles.sub}>
            Each row is one exact combination of the selected studies: proteins found in the filled
            studies and in none of the others. Click a row to list those proteins.
          </p>
          <div className={styles.tableScroll}>
            <table className={`${styles.table} ${styles.upsetTable}`}>
              <thead>
                <tr>
                  {selected.map((i) => (
                    <th key={i} className={styles.center} title={arms[i].name}>
                      {label(i)}
                    </th>
                  ))}
                  <th>Proteins</th>
                  <th className={styles.num} title="Canonical or Likely Surfaceome proteins in this intersection">
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
          Select {MAX_UPSET} or fewer studies to see their exact intersections; the protein list
          below works for any selection.
        </p>
      ) : null}

      <h3 className={styles.subTitle}>Proteins {single ? "" : modeLabel}</h3>
      <div className={styles.controls}>
        <input
          type="search"
          className={styles.search}
          placeholder="Filter by symbol or accession…"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setLimit(PAGE);
          }}
          aria-label="Filter proteins"
        />
        {!single ? (
          <label className={styles.modeLabel}>
            Show{" "}
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value as Mode);
                setLimit(PAGE);
              }}
            >
              <option value="all">in all selected</option>
              <option value="any">in any selected</option>
              {mode.startsWith("c:") ? <option value={mode}>{modeLabel}</option> : null}
            </select>
          </label>
        ) : null}
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
      </div>
      <div className={styles.count}>
        {shown.length.toLocaleString("en-US")} proteins
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
              {pHeader("tier", "Surfaceome tier")}
              {pHeader("counted", `Counted arms (of ${countedIdx.length})`)}
              <th>UniProt</th>
              {!single
                ? selected.map((i) => (
                    <th key={i} className={styles.center} title={arms[i].name}>
                      {label(i)}
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
                    <Link href={`/${p.symbol}/`} className={styles.protein}>
                      {p.symbol}
                    </Link>
                  ) : (
                    <span className={styles.noPage} title="No Surfaceome page for this protein">
                      {p.symbol || "—"}
                    </span>
                  )}
                </td>
                <td>
                  <TierPill tier={p.tier} />
                </td>
                <td className={styles.countedCell}>
                  <span className={styles.countedNum}>{p.nCounted}</span>
                  <Bar value={p.nCounted / Math.max(1, countedIdx.length)} />
                </td>
                <td>
                  <a
                    href={`https://www.uniprot.org/uniprotkb/${p.acc}/entry`}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.mono}
                  >
                    {p.acc}
                  </a>
                </td>
                {!single
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
              <th key={i} className={styles.num} title={arms[i].name}>
                {label(i)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {selected.map((i, a) => (
            <tr key={i}>
              <th scope="row" title={arms[i].name}>
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
