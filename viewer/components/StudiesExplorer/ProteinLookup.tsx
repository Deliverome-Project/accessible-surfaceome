"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { loadAllPresence, tierOf, type PresenceShard } from "../../lib/surface-proteomics";
import { StudyPresence } from "../surfaceome/ExpressionCard/StudyPresence";
import { TierPill } from "./TierPill";
import styles from "./StudiesExplorer.module.css";

const MAX_HITS = 8;

/**
 * Look one protein up without leaving the page: type a symbol, name or
 * accession, pick a match, and the same per-dataset view the gene page's
 * Expression tab shows appears inline. The presence table loads on first focus.
 */
export function ProteinLookup() {
  const [presence, setPresence] = useState<PresenceShard | null>(null);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<string | null>(null);

  const load = () => {
    if (presence || loading) return;
    setLoading(true);
    loadAllPresence().then(setPresence, () => setLoading(false));
  };

  const hits = useMemo(() => {
    const t = q.trim().toUpperCase();
    if (!presence || t.length < 2) return [];
    const exact: string[] = [];
    const prefix: string[] = [];
    const other: string[] = [];
    for (const [acc, e] of Object.entries(presence)) {
      const sym = e.s.toUpperCase();
      if (sym === t || acc === t) exact.push(acc);
      else if (sym.startsWith(t)) prefix.push(acc);
      else if ((e.n ?? "").toUpperCase().includes(t) || acc.startsWith(t)) other.push(acc);
    }
    const bySym = (a: string, b: string) => presence[a].s.localeCompare(presence[b].s);
    return [...exact, ...prefix.sort(bySym), ...other.sort(bySym)].slice(0, MAX_HITS);
  }, [presence, q]);

  const entry = picked && presence ? presence[picked] : null;

  return (
    <div className={styles.lookup}>
      <input
        id="protein-lookup"
        type="search"
        className={styles.search}
        placeholder="Look up a protein: symbol, name or UniProt accession…"
        value={q}
        onFocus={load}
        onChange={(e) => {
          load();
          setQ(e.target.value);
          setPicked(null);
        }}
        aria-label="Look up a protein"
      />
      {loading && !presence ? <p className={styles.sub}>Loading protein list…</p> : null}
      {hits.length > 0 && !picked ? (
        <div className={styles.lookupResults}>
          {hits.map((acc) => (
            <button
              key={acc}
              type="button"
              className={styles.chip}
              data-on="false"
              onClick={() => setPicked(acc)}
            >
              {presence?.[acc].s || acc}{" "}
              <span className={styles.chipCount}>{presence?.[acc].n ?? acc}</span>
            </button>
          ))}
        </div>
      ) : null}
      {presence && q.trim().length >= 2 && hits.length === 0 ? (
        <p className={styles.sub}>
          No dataset lists a protein matching &ldquo;{q.trim()}&rdquo;.
        </p>
      ) : null}
      {picked && entry ? (
        <div className={styles.lookupCard}>
          <p className={styles.lookupHead}>
            {entry.d && entry.s ? (
              <Link href={`/${entry.s}/`} className={styles.protein}>
                {entry.s}
              </Link>
            ) : (
              <strong>{entry.s || picked}</strong>
            )}
            <span className={styles.sub}>{entry.n ?? ""}</span>
            <TierPill tier={tierOf(entry)} />
            {entry.d && entry.s ? (
              <Link href={`/${entry.s}/`} className={styles.linkButton}>
                open the {entry.s} page
              </Link>
            ) : null}
            <button type="button" className={styles.linkButton} onClick={() => setPicked(null)}>
              back to matches
            </button>
          </p>
          <StudyPresence uniprotAcc={picked} symbol={entry.s || picked} />
        </div>
      ) : null}
    </div>
  );
}
