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
import styles from "./GeneJump.module.css";

interface GeneJumpProps {
  /** Deep-dive gene symbols — the same set `generateStaticParams` emits
   *  (`listSurfaceomeGenes()`). Restricting the typeahead to this set
   *  means every pick lands on a real statically-generated page; under
   *  `output: export` a non-deep-dive symbol would 404. */
  genes: readonly string[];
  /** Current gene symbol — excluded from its own suggestions. */
  current?: string;
}

const MAX_SHOWN = 8;

/**
 * GeneJump — typeahead "jump to another gene's deep dive" box for the
 * deep-dive page toolbar, so the reader can hop between gene records
 * without bouncing back to the catalog table.
 *
 * Pure client component (needs `useRouter` + local input state). The
 * gene universe is passed in from the server component rather than
 * fetched, so the searchable set is guaranteed to match the built page
 * set (no runtime list that could drift ahead of the static export).
 */
export function GeneJump({ genes, current }: GeneJumpProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const baseId = useId();
  const blurTimer = useRef<number | null>(null);

  const universe = useMemo(() => {
    const cur = (current ?? "").toUpperCase();
    return [...genes]
      .filter((g) => g && g.toUpperCase() !== cur)
      .sort((a, b) => a.localeCompare(b));
  }, [genes, current]);

  const matches = useMemo(() => {
    const q = query.trim().toUpperCase();
    const pool = q
      ? universe.filter((g) => g.toUpperCase().includes(q))
      : universe;
    return pool.slice(0, MAX_SHOWN);
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
        go(pick);
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
                key={g}
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
                  onMouseDown={(e) => {
                    // mousedown fires before the input's blur; preventDefault
                    // keeps focus so onBlur doesn't race the navigation.
                    e.preventDefault();
                    go(g);
                  }}
                  onMouseEnter={() => setActiveIdx(i)}
                >
                  {g}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
