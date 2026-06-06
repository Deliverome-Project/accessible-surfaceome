"use client";

import {
  type KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
// Type-only import → erased at compile, so the client bundle never pulls
// in lib/surfaceome.ts (which imports node:fs).
import type { GeneEntry } from "../../../lib/surfaceome";
import styles from "./GeneJump.module.css";

interface GeneJumpProps {
  /** Deep-dive genes — the same set `generateStaticParams` emits
   *  (`listSurfaceomeGeneEntries()`), each carrying a `stale` flag.
   *  Restricting the typeahead to this set means every pick lands on a real
   *  statically-generated page; under `output: export` a non-deep-dive symbol
   *  would 404. */
  genes: readonly GeneEntry[];
  /** Current gene symbol — excluded from its own suggestions. */
  current?: string;
  /** When true, each suggestion shows a schema-freshness dot (green = record
   *  validates against the current schema, amber = out of date / needs
   *  re-running). A temporary migration aid — off restores plain symbols. */
  showSchemaDots?: boolean;
}

/**
 * GeneJump — typeahead "jump to another gene's deep dive" box for the
 * deep-dive page toolbar, so the reader can hop between gene records
 * without bouncing back to the catalog table.
 *
 * Pure client component (needs `useRouter` + local input state). The
 * gene universe is passed in from the server component rather than
 * fetched, so the searchable set is guaranteed to match the built page
 * set (no runtime list that could drift ahead of the static export).
 *
 * When `showSchemaDots` is set, each suggestion carries a freshness dot
 * driven by the precomputed `stale` flag (green = current schema, amber =
 * out of date). The status is also a `title` tooltip + visually-hidden
 * text, so it never relies on color alone.
 */
export function GeneJump({ genes, current, showSchemaDots = false }: GeneJumpProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const baseId = useId();
  const blurTimer = useRef<number | null>(null);

  const universe = useMemo(() => {
    const cur = (current ?? "").toUpperCase();
    return [...genes]
      .filter((g) => g.symbol && g.symbol.toUpperCase() !== cur)
      .sort((a, b) => a.symbol.localeCompare(b.symbol));
  }, [genes, current]);

  const matches = useMemo(() => {
    const q = query.trim().toUpperCase();
    return q
      ? universe.filter((g) => g.symbol.toUpperCase().includes(q))
      : universe;
  }, [universe, query]);

  useEffect(
    () => () => {
      if (blurTimer.current != null) window.clearTimeout(blurTimer.current);
    },
    [],
  );

  // Offline stub build (SURFACEOME_API_BASE=local) lists no genes — render
  // nothing rather than a dead search box.
  if (universe.length === 0) return null;

  function go(symbol: string) {
    setOpen(false);
    setQuery("");
    router.push(`/${symbol}`);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActiveIdx((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      const pick = matches[activeIdx] ?? matches[0];
      if (pick) {
        e.preventDefault();
        go(pick.symbol);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  }

  const activeId =
    open && matches.length ? `${baseId}-opt-${activeIdx}` : undefined;

  return (
    <div className={styles.wrap}>
      <label htmlFor={`${baseId}-input`} className="sr-only">
        Jump to another gene&apos;s deep dive
      </label>
      <input
        id={`${baseId}-input`}
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={`${baseId}-list`}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        autoComplete="off"
        spellCheck={false}
        className={styles.input}
        placeholder="Jump to gene…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIdx(0);
        }}
        onFocus={() => {
          if (blurTimer.current != null) window.clearTimeout(blurTimer.current);
          setOpen(true);
        }}
        onBlur={() => {
          // Delay close so a mousedown on an option still registers.
          blurTimer.current = window.setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
      />
      {open ? (
        <ul className={styles.list} id={`${baseId}-list`} role="listbox">
          {matches.length === 0 ? (
            <li className={styles.empty}>No deep dive for “{query.trim()}”</li>
          ) : (
            matches.map((g, i) => (
              <li
                key={g.symbol}
                id={`${baseId}-opt-${i}`}
                role="option"
                aria-selected={i === activeIdx}
              >
                <button
                  type="button"
                  tabIndex={-1}
                  className={`${styles.option} ${
                    i === activeIdx ? styles.optionActive : ""
                  }`}
                  title={
                    showSchemaDots
                      ? g.stale
                        ? "Deep-dive record is out of date with the current schema — needs re-running"
                        : "Deep-dive record is up to date with the current schema"
                      : undefined
                  }
                  onMouseDown={(e) => {
                    // mousedown fires before the input's blur; preventDefault
                    // keeps focus so onBlur doesn't race the navigation.
                    e.preventDefault();
                    go(g.symbol);
                  }}
                  onMouseEnter={() => setActiveIdx(i)}
                >
                  {showSchemaDots ? (
                    <>
                      <span
                        className={`${styles.dot} ${
                          g.stale ? styles.dotStale : styles.dotCurrent
                        }`}
                        aria-hidden="true"
                      />
                      <span className="sr-only">
                        {g.stale ? "out of date — " : "up to date — "}
                      </span>
                    </>
                  ) : null}
                  <span className={styles.optionSymbol}>{g.symbol}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
