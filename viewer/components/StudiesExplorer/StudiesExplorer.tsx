"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  isCounted,
  loadAllPresence,
  METHOD_CLASS_LABEL,
  paperUrl,
  shortCitation,
  STATUS_HELP,
  STATUS_LABEL,
  type ArmStatus,
  type MethodClass,
  type PresenceShard,
  type StudyArm,
  type StudyIndex,
} from "../../lib/surface-proteomics";
import { statusTone } from "../surfaceome/ExpressionCard/StudyPresence";
import { SortableHeader } from "../surfaceome/_shared/SortableHeader";
import { SortResetButton } from "../surfaceome/_shared/SortResetButton";
import { useTableSort, type SortValue } from "../surfaceome/_shared/useTableSort";
import { StatusPill } from "../surfaceome/StatusPill/StatusPill";
import styles from "./StudiesExplorer.module.css";

interface Props {
  index: StudyIndex;
}

type SortKey = "study" | "year" | "method" | "intact" | "sample" | "n" | "status";

const STATUS_ORDER: ArmStatus[] = ["core", "provisional", "held", "below_screen", "comparator"];
const CLASS_ORDER: MethodClass[] = ["intact_cell", "fractionation", "lysate"];
const PAGE = 200;

interface Protein {
  acc: string;
  symbol: string;
  deep: boolean;
  arms: Set<number>;
}

function readSelection(): string[] {
  if (typeof window === "undefined") return [];
  const v = new URLSearchParams(window.location.search).get("arm");
  return v ? v.split(",").filter(Boolean) : [];
}

export function StudiesExplorer({ index }: Props) {
  const arms = index.arms;
  const idxById = useMemo(() => new Map(arms.map((a, i) => [a.id, i])), [arms]);
  const [query, setQuery] = useState("");
  const [statuses, setStatuses] = useState<Set<ArmStatus>>(new Set(STATUS_ORDER));
  const [classes, setClasses] = useState<Set<MethodClass>>(new Set(CLASS_ORDER));
  const [selected, setSelected] = useState<number[]>([]);
  const { sortKey, sortDir, onSort, reset, ariaSort, sortRows } = useTableSort<SortKey>();

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
  const comparators: Record<SortKey, (r: { arm: StudyArm }) => SortValue> = {
    study: (r) => shortCitation(r.arm),
    year: (r) => r.arm.year ?? 0,
    method: (r) => `${r.arm.method_class} ${r.arm.family_label}`,
    intact: (r) => r.arm.intact_cell_labeling,
    sample: (r) => r.arm.sample ?? "",
    n: (r) => r.arm.n_proteins,
    status: (r) => STATUS_ORDER.indexOf(r.arm.status),
  };
  const rows = sortRows(visible, comparators);

  const header = (k: SortKey, label: string) => (
    <th aria-sort={ariaSort(k)}>
      <SortableHeader k={k} active={sortKey === k} direction={sortDir} onSort={onSort}>
        {label}
      </SortableHeader>
    </th>
  );

  return (
    <div className={styles.wrap}>
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
              <th>Paper</th>
              {header("method", "Method")}
              {header("intact", "Intact cells")}
              {header("sample", "Cell type / sample")}
              {header("n", "Proteins")}
              {header("status", "Status")}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ arm, i }) => {
              const sel = selected.includes(i);
              return (
                <tr key={arm.id} className={`${sel ? styles.selectedRow : ""} ${isCounted(arm) ? "" : styles.notCounted}`}>
                  <td>
                    <input
                      type="checkbox"
                      checked={sel}
                      onChange={() => toggle(i)}
                      aria-label={`Select ${arm.name}`}
                    />
                  </td>
                  <td>
                    <button type="button" className={styles.studyButton} onClick={() => toggle(i)}>
                      {shortCitation(arm)}
                    </button>
                    <div className={styles.sub}>{arm.name}</div>
                  </td>
                  <td>{arm.year ?? "—"}</td>
                  <td className={styles.links}>
                    {arm.pmid ? (
                      <a href={`https://pubmed.ncbi.nlm.nih.gov/${arm.pmid}/`} target="_blank" rel="noreferrer">
                        PMID {arm.pmid}
                      </a>
                    ) : null}
                    {arm.doi ? (
                      <a href={`https://doi.org/${arm.doi}`} target="_blank" rel="noreferrer" className={styles.sub}>
                        DOI
                      </a>
                    ) : null}
                  </td>
                  <td>
                    {METHOD_CLASS_LABEL[arm.method_class]}
                    <div className={styles.sub}>{arm.family_label}</div>
                  </td>
                  <td>{arm.intact_cell_labeling === "yes" ? "Yes" : "No"}</td>
                  <td className={styles.sample}>{arm.sample}</td>
                  <td className={styles.num}>{arm.n_proteins.toLocaleString("en-US")}</td>
                  <td>
                    <StatusPill size="sm" tone={statusTone(arm.status)} title={STATUS_HELP[arm.status]} nativeTooltip>
                      {STATUS_LABEL[arm.status]}
                    </StatusPill>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected.length > 0 ? <SelectionPanel arms={arms} selected={selected} /> : null}
    </div>
  );
}

function ChipGroup<T extends string>({
  label,
  options,
  labelOf,
  countOf,
  value,
  onChange,
}: {
  label: string;
  options: T[];
  labelOf: (v: T) => string;
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

function SelectionPanel({ arms, selected }: { arms: StudyArm[]; selected: number[] }) {
  const [presence, setPresence] = useState<PresenceShard | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("");
  const [mode, setMode] = useState<"all" | "any" | number>("all");
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    loadAllPresence().then(setPresence, () => setError(true));
  }, []);
  // A per-study "only in" mode stops making sense once that study is deselected.
  useEffect(() => {
    if (typeof mode === "number" && !selected.includes(mode)) setMode("all");
  }, [mode, selected]);

  const proteins = useMemo<Protein[]>(() => {
    if (!presence) return [];
    const sel = new Set(selected);
    const out: Protein[] = [];
    for (const [acc, e] of Object.entries(presence)) {
      const hit = e.a.filter((i) => sel.has(i));
      if (hit.length) out.push({ acc, symbol: e.s, deep: e.d === 1, arms: new Set(hit) });
    }
    return out.sort(
      (a, b) => Number(!a.symbol) - Number(!b.symbol) || (a.symbol || a.acc).localeCompare(b.symbol || b.acc),
    );
  }, [presence, selected]);

  if (error) return <p className={styles.empty}>Protein lists could not be loaded.</p>;
  if (!presence) return <p className={styles.empty}>Loading protein lists…</p>;

  const single = selected.length === 1;
  const inAll = proteins.filter((p) => p.arms.size === selected.length);
  const shown = proteins.filter((p) => {
    if (!single) {
      if (mode === "all" && p.arms.size !== selected.length) return false;
      if (typeof mode === "number" && !(p.arms.size === 1 && p.arms.has(mode))) return false;
    }
    const f = filter.trim().toUpperCase();
    return !f || p.acc.includes(f) || p.symbol.toUpperCase().includes(f);
  });

  return (
    <section className={styles.panel} aria-label="Selected studies">
      {single ? (
        <h2 className={`h-section ${styles.panelTitle}`}>
          Proteins in {shortCitation(arms[selected[0]])}: {proteins.length.toLocaleString("en-US")}
        </h2>
      ) : (
        <>
          <h2 className={`h-section ${styles.panelTitle}`}>
            Comparing {selected.length} studies: {inAll.length.toLocaleString("en-US")} proteins in all,{" "}
            {proteins.length.toLocaleString("en-US")} in any
          </h2>
          <OverlapMatrix arms={arms} selected={selected} proteins={proteins} />
        </>
      )}
      {!isCounted(arms[selected[0]]) && single ? (
        <p className={styles.caveat}>{STATUS_HELP[arms[selected[0]].status]}</p>
      ) : null}
      {!single && selected.some((i) => !isCounted(arms[i])) ? (
        <p className={styles.caveat}>
          The selection includes arms that are not counted as surface detections
          (held, below screen or comparators).
        </p>
      ) : null}

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
              value={String(mode)}
              onChange={(e) => {
                const v = e.target.value;
                setMode(v === "all" || v === "any" ? v : Number(v));
                setLimit(PAGE);
              }}
            >
              <option value="all">in all selected</option>
              <option value="any">in any selected</option>
              {selected.map((i) => (
                <option key={i} value={i}>
                  only in {shortCitation(arms[i])} ({arms[i].id})
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <span className={styles.count}>{shown.length.toLocaleString("en-US")} proteins</span>
      </div>

      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Protein</th>
              <th>UniProt</th>
              {!single ? selected.map((i) => <th key={i} className={styles.num}>{shortCitation(arms[i])}</th>) : null}
            </tr>
          </thead>
          <tbody>
            {shown.slice(0, limit).map((p) => (
              <tr key={p.acc}>
                <td>
                  {p.deep && p.symbol ? (
                    <Link href={`/${p.symbol}/`}>{p.symbol}</Link>
                  ) : (
                    <span title="No deep-dive page for this protein">{p.symbol || "—"}</span>
                  )}
                </td>
                <td>
                  <a href={`https://www.uniprot.org/uniprotkb/${p.acc}/entry`} target="_blank" rel="noreferrer" className={styles.mono}>
                    {p.acc}
                  </a>
                </td>
                {!single
                  ? selected.map((i) => (
                      <td key={i} className={styles.num}>
                        {p.arms.has(i) ? "●" : ""}
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

function OverlapMatrix({ arms, selected, proteins }: { arms: StudyArm[]; selected: number[]; proteins: Protein[] }) {
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
          Shared proteins per pair (Jaccard in brackets). The diagonal is each study&apos;s total.
        </caption>
        <thead>
          <tr>
            <th />
            {selected.map((i) => (
              <th key={i} className={styles.num} title={arms[i].name}>
                {shortCitation(arms[i])}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {selected.map((i, a) => (
            <tr key={i}>
              <th scope="row" title={arms[i].name}>
                {shortCitation(arms[i])}
                <div className={styles.sub}>{arms[i].id}</div>
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
