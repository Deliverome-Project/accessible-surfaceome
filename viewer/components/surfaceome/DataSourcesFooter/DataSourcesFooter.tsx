import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { CITATIONS, pubmedUrl } from "../../../lib/citations";
import styles from "./DataSourcesFooter.module.css";

interface Props {
  rec: SurfaceomeRecord;
}

/**
 * Per-record Data Sources footer. Lines are built mechanically from
 * the deterministic-features blocks so attribution travels with the
 * record. Adding a new deterministic source means stamping the
 * `source` / `license` / `attribution` fields on its block and then
 * adding a line here.
 *
 * Two columns:
 * - Catalog vote — the 5 databases that decide whether a gene is in
 *   the catalog at all (per `scripts/build/build_candidate_universe_v3.py`).
 * - Deterministic features — per-gene topology, structure, orthologs,
 *   complexes, and binding-site scoring.
 */
export function DataSourcesFooter({ rec }: Props) {
  const df = rec.deterministic_features;
  const comparaVersion =
    df.orthologs.mouse[0]?.compara_version ?? df.paralogs[0]?.compara_version ?? null;
  const deeptmhmm = df.canonical_topology.tool_version;
  return (
    <aside className={styles.footer} aria-label="Data sources and licenses">
      <p className={`label-mono ${styles.label}`}>Data sources &amp; licenses</p>
      <div className={styles.grid}>
        <div>
          <p className={styles.colHeading}>Catalog vote (5 databases)</p>
          <ul className={styles.list}>
            <li>UniProt — CC BY 4.0 (UniProt Consortium)</li>
            <li>Gene Ontology — CC BY 4.0 (The Gene Ontology Consortium)</li>
            <li>
              Human Protein Atlas — CC BY 4.0 ({CITATIONS.hpa.authorYear},{" "}
              <a href={pubmedUrl(CITATIONS.hpa.pmid)} target="_blank" rel="noopener noreferrer">
                PMID {CITATIONS.hpa.pmid}
              </a>
              )
            </li>
            <li>
              SURFY — academic use ({CITATIONS.surfy.authorYear},{" "}
              <a href={pubmedUrl(CITATIONS.surfy.pmid)} target="_blank" rel="noopener noreferrer">
                PMID {CITATIONS.surfy.pmid}
              </a>
              )
            </li>
            <li>
              CSPA — academic use ({CITATIONS.cspa.authorYear},{" "}
              <a href={pubmedUrl(CITATIONS.cspa.pmid)} target="_blank" rel="noopener noreferrer">
                PMID {CITATIONS.cspa.pmid}
              </a>
              )
            </li>
          </ul>
        </div>
        <div>
          <p className={styles.colHeading}>Deterministic features</p>
          <ul className={styles.list}>
            <li>
              AlphaFold DB structures — {df.structure.license} ({df.structure.attribution})
            </li>
            <li>
              DeepTMHMM topology — {deeptmhmm} · DTU Health Tech (
              {CITATIONS.deepTmhmm.authorYear},{" "}
              <a
                href={pubmedUrl(CITATIONS.deepTmhmm.pmid)}
                target="_blank"
                rel="noopener noreferrer"
              >
                PMID {CITATIONS.deepTmhmm.pmid}
              </a>
              )
            </li>
            <li>
              Ensembl Compara orthologs &amp; paralogs
              {comparaVersion ? ` — ${comparaVersion} ` : " — "}
              EMBL-EBI ({CITATIONS.ensemblCompara2024.authorYear},{" "}
              <a
                href={pubmedUrl(CITATIONS.ensemblCompara2024.pmid)}
                target="_blank"
                rel="noopener noreferrer"
              >
                PMID {CITATIONS.ensemblCompara2024.pmid}
              </a>
              {" "}+ {CITATIONS.ensemblCompara2009.authorYear},{" "}
              <a
                href={pubmedUrl(CITATIONS.ensemblCompara2009.pmid)}
                target="_blank"
                rel="noopener noreferrer"
              >
                PMID {CITATIONS.ensemblCompara2009.pmid}
              </a>
              )
            </li>
            <li>
              Schweke homo-oligomer atlas ({CITATIONS.schwekeHomomer.authorYear},{" "}
              <a
                href={pubmedUrl(CITATIONS.schwekeHomomer.pmid)}
                target="_blank"
                rel="noopener noreferrer"
              >
                PMID {CITATIONS.schwekeHomomer.pmid}
              </a>
              , Cell)
            </li>
            <li>
              SURFACE-Bind binding-site scoring ({CITATIONS.surfaceBind.authorYear},{" "}
              <a
                href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
                target="_blank"
                rel="noopener noreferrer"
              >
                PMID {CITATIONS.surfaceBind.pmid}
              </a>
              , PNAS)
            </li>
          </ul>
        </div>
      </div>
    </aside>
  );
}
