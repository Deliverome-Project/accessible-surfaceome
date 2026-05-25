import type { CatalogRow } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import styles from "./DatabasePresenceCard.module.css";

interface Props {
  /** Catalog row for this gene from the universe build; carries the
   *  5 source-DB surface flags + the aggregate `n_sources` count. */
  row: CatalogRow;
  n: number;
}

/** Display order + presentation labels for the five gating
 *  databases. Mirrors the column order in the catalog and
 *  SurfaceBench tables so a reader who came from either lands on
 *  the same set in the same order. */
const DB_LABELS: { key: keyof CatalogRow["db"]; short: string; long: string; href: string }[] = [
  {
    key: "uniprot",
    short: "UniProt",
    long: "UniProt — keyword KW-1003 (cell membrane) or KW-0732 (signal peptide).",
    href: "https://www.uniprot.org/keywords/",
  },
  {
    key: "go",
    short: "GO",
    long: "Gene Ontology — Cellular Component term GO:0005886 (plasma membrane) or descendant.",
    href: "https://amigo.geneontology.org/amigo/term/GO:0005886",
  },
  {
    key: "surfy",
    short: "SURFY",
    long: "SURFY — random-forest surfaceome predictor (Bausch-Fluck et al. 2018).",
    href: "https://wlab.ethz.ch/surfaceome/",
  },
  {
    key: "cspa",
    short: "CSPA",
    long: "Cell Surface Protein Atlas — mass-spec capture of surface-exposed glycoproteins.",
    href: "https://wlab.ethz.ch/cspa/",
  },
  {
    key: "hpa",
    short: "HPA",
    long: "Human Protein Atlas — antibody-based plasma-membrane subcellular annotation.",
    href: "https://www.proteinatlas.org/",
  },
];

/**
 * DatabasePresenceCard — surfaces which of the five public source
 * databases flag this gene as cell-surface. Same five-DB vote vector
 * the catalog (/) and SurfaceBench (/benchmark) tables show as dots
 * in their rows; this card spells it out on the per-gene page so a
 * reader looking at one gene gets the same "consensus picture"
 * without bouncing back to the index.
 *
 * Source: `candidate_universe_public.{uniprot,go,surfy,cspa,hpa}` in
 * the public D1 mirror, threaded through `loadCatalogRow(symbol)` at
 * build time.
 */
export function DatabasePresenceCard({ row, n }: Props) {
  const total = DB_LABELS.length;
  const yes = DB_LABELS.filter((d) => row.db[d.key] === 1).length;
  return (
    <SectionCard
      n={n}
      eyebrow="Source databases"
      title="Database membership"
      meta={`${yes} of ${total} sources · candidate-universe build`}
      lede={
        yes === 0
          ? "No source database flags this gene as cell-surface. The triage call below is the agent's read of the surrounding evidence."
          : `${yes} of ${total} public surfaceome resources catalog this gene as cell-surface — the same vote vector shown as dots in the catalog and SurfaceBench tables.`
      }
    >
      <ul className={styles.row} aria-label="Source database votes">
        {DB_LABELS.map((d) => {
          const present = row.db[d.key] === 1;
          return (
            <li
              key={d.key}
              className={`${styles.cell} ${present ? styles.cellYes : styles.cellNo}`}
            >
              <a
                href={d.href}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
                title={d.long}
              >
                <span
                  className={`${styles.swatch} ${present ? styles.swatchYes : styles.swatchNo}`}
                  aria-hidden="true"
                />
                <span className={styles.name}>{d.short}</span>
                <span className={`label-mono ${styles.state}`}>
                  {present ? "yes" : "—"}
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
}
