import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./IsoformsCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

export function IsoformsCard({ rec, n }: Props) {
  const df = rec.deterministic_features;
  const ct = df.canonical_topology;
  return (
    <SectionCard
      n={n}
      eyebrow="Isoforms"
      title={
        <>
          The <em>topology</em> table
        </>
      }
      meta={`Deterministic · UniProt + DeepTMHMM ${ct.tool_version}`}
      lede="Per-isoform transmembrane topology, ECD / ICD lengths, signal-peptide length. The canonical row mirrors what the 3D card renders."
    >
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Isoform</th>
              <th scope="col">UniProt</th>
              <th scope="col">TM count</th>
              <th scope="col">N-term</th>
              <th scope="col">Signal pep</th>
              <th scope="col">ECD len</th>
              <th scope="col">ICD len</th>
            </tr>
          </thead>
          <tbody>
            <tr className={styles.canonicalRow}>
              <td>
                <span className={styles.mono}>canonical</span>
              </td>
              <td>
                <span className={styles.mono}>{rec.gene.uniprot_acc}</span>
              </td>
              <td>{ct.tm_helix_count}</td>
              <td>
                <StatusPill
                  tone={ct.n_terminal_orientation === "extracellular" ? "teal" : "neutral"}
                  size="sm"
                >
                  {prettyEnum(ct.n_terminal_orientation)}
                </StatusPill>
              </td>
              <td>{ct.signal_peptide_length} aa</td>
              <td>{ct.ecd_length_residues} aa</td>
              <td>{ct.icd_length_residues} aa</td>
            </tr>
            {df.isoform_topologies.map((iso, i) => (
              <tr key={i}>
                <td>
                  <span className={styles.mono}>{iso.isoform_id}</span>
                </td>
                <td>
                  <span className={styles.mono}>{iso.uniprot_acc}</span>
                </td>
                <td>{iso.tm_helix_count}</td>
                <td>
                  <StatusPill
                    tone={
                      iso.n_terminal_orientation === "extracellular" ? "teal" : "neutral"
                    }
                    size="sm"
                  >
                    {prettyEnum(iso.n_terminal_orientation)}
                  </StatusPill>
                </td>
                <td>{iso.signal_peptide_length} aa</td>
                <td>{iso.ecd_length_residues} aa</td>
                <td>{iso.icd_length_residues} aa</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {ct.canonical_isoform_caveat ? (
        <p className={`lede ${styles.caveat}`}>
          <span className={`label-mono ${styles.caveatLabel}`}>Canonical caveat</span>
          {ct.canonical_isoform_caveat}
        </p>
      ) : null}

      {df.isoform_topologies.length === 0 ? (
        <p className={styles.empty}>
          UniProt records no alternative isoforms for {rec.gene.hgnc_symbol}.
        </p>
      ) : null}
    </SectionCard>
  );
}
