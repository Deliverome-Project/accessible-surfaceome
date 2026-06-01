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
 */
export function DataSourcesFooter({ rec }: Props) {
  const df = rec.deterministic_features;
  const comparaVersion =
    df.orthologs.mouse[0]?.compara_version ?? df.paralogs[0]?.compara_version ?? null;
  const deeptmhmm = df.canonical_topology.tool_version;
  return (
    <aside className={styles.footer} aria-label="Data sources">
      <p className={`label-mono ${styles.label}`}>Data sources</p>
      <ul className={styles.list}>
        <li>
          AlphaFold DB structures — {df.structure.license} ({df.structure.attribution})
        </li>
        <li>
          DeepTMHMM topology — {deeptmhmm} · DTU Health Tech (Hallgren et al. 2022)
        </li>
        <li>
          Ensembl Compara orthologs &amp; paralogs
          {comparaVersion ? ` — ${comparaVersion} ` : " — "}
          open data with citation (EMBL-EBI; Howe et al. 2024 + Vilella et al. 2009)
        </li>
        <li>
          SURFACE-Bind binding-site scoring — MaSIF-based surface patch
          scoring on the AlphaFold model ({CITATIONS.surfaceBind.authorYear},{" "}
          <a
            href={pubmedUrl(CITATIONS.surfaceBind.pmid)}
            target="_blank"
            rel="noopener noreferrer"
          >
            PMID {CITATIONS.surfaceBind.pmid}
          </a>
          , PNAS) ·{" "}
          <a
            href="https://surface-bind.inria.fr/"
            target="_blank"
            rel="noopener noreferrer"
          >
            surface-bind.inria.fr
          </a>
        </li>
        <li>UniProt — CC BY 4.0 (UniProt Consortium)</li>
      </ul>
    </aside>
  );
}
