import type { DBComparison } from "../../../lib/surfaceome-types";
import styles from "./DBVotes.module.css";

const SOURCES: { key: keyof DBComparison; label: string }[] = [
  { key: "surfy", label: "SURFY" },
  { key: "cspa", label: "CSPA" },
  { key: "uniprot_query", label: "UniProt" },
  { key: "go", label: "GO" },
  { key: "hpa", label: "HPA" },
  { key: "deeptmhmm", label: "DeepTMHMM" },
  { key: "compartments", label: "COMPARTMENTS" },
  { key: "patent_handle", label: "Patent handle" },
];

interface DBVotesProps {
  db: DBComparison;
}

/**
 * DBVotes — eight-source vote panel. Each cell flags whether that
 * source called the protein a surface protein; the bottom strip
 * summarizes the tally as `N / 8`.
 */
export function DBVotes({ db }: DBVotesProps) {
  return (
    <div className={styles.wrap}>
      <ul className={styles.grid} aria-label="Source votes">
        {SOURCES.map((s) => {
          const yes = Boolean(db[s.key]);
          return (
            <li
              key={s.key}
              className={`${styles.cell} ${yes ? styles.yes : styles.no}`}
              aria-label={`${s.label}: ${yes ? "surface" : "non-surface"}`}
            >
              <span className={styles.src}>{s.label}</span>
              <span className={styles.vote}>{yes ? "Surface" : "—"}</span>
            </li>
          );
        })}
      </ul>
      <p className={styles.tally}>
        <span className={styles.tallyNum}>{db.n_sources_voting_surface}</span>
        <span className={styles.tallyOf}>of</span>
        <span className={styles.tallyTotal}>{SOURCES.length}</span>
        <span className={styles.tallyLabel}>sources called surface</span>
      </p>
    </div>
  );
}
