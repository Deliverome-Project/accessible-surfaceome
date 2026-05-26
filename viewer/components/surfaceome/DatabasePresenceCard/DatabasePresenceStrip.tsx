import type { CatalogRow } from "../../../lib/surfaceome";
import styles from "./DatabasePresenceCard.module.css";

interface Props {
  /** Catalog row for this gene from the universe build; carries the
   *  5 source-DB surface flags + the aggregate `n_sources` count. */
  row: CatalogRow;
}

/** Display order + presentation labels — same five-DB vote vector
 *  the catalog (/) and SurfaceBench (/benchmark) tables show as
 *  dots in their rows. Duplicated from `DatabasePresenceCard.tsx`
 *  so each component is independently usable; consolidate when a
 *  third consumer appears. */
const DB_LABELS: {
  key: keyof CatalogRow["db"];
  short: string;
  long: string;
  href: string;
}[] = [
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
 * `<DatabasePresenceStrip>` — slim, header-embedded version of
 * `<DatabasePresenceCard>`. Renders just the per-DB swatch+name strip
 * (no SectionCard wrapper, no preamble), suitable for placement
 * inline in the `<GeneHeader>` above the executive summary text.
 *
 * Shows the same 5-DB vote vector the catalog table displays as dots,
 * with a tooltip per DB explaining what flag it derives from.
 */
export function DatabasePresenceStrip({ row }: Props) {
  const total = DB_LABELS.length;
  const yes = DB_LABELS.filter((d) => row.db[d.key] === 1).length;
  return (
    <div className={styles.stripWrap}>
      <span className={`label-mono ${styles.stripLabel}`}>
        Sources · {yes}/{total}
      </span>
      <ul className={styles.stripRow} aria-label="Source database votes">
        {DB_LABELS.map((d) => {
          const present = row.db[d.key] === 1;
          return (
            <li
              key={d.key}
              className={`${styles.stripCell} ${present ? styles.cellYes : styles.cellNo}`}
            >
              <a
                href={d.href}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.stripLink}
                title={d.long}
              >
                <span
                  className={`${styles.swatch} ${present ? styles.swatchYes : styles.swatchNo}`}
                  aria-hidden="true"
                />
                <span className={styles.name}>{d.short}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
