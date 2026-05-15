import type { SurfaceomeRecord } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import { TopologyBar, TopologyLegend } from "./TopologyBar";
import styles from "./IsoformsCard.module.css";

function presentStates(topologies: string[]): string[] {
  const seen = new Set<string>();
  for (const t of topologies) {
    for (const ch of t) seen.add(ch);
  }
  return ["M", "O", "I", "S", "B"].filter((s) => seen.has(s));
}

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
              <th scope="col">TM</th>
              <th scope="col">N-term</th>
              <th scope="col">Signal pep</th>
              <th scope="col">ECD len</th>
              <th scope="col">ICD len</th>
              <th scope="col" className={styles.topoCol}>
                Topology
              </th>
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
              <td className={styles.topoCell}>
                <TopologyBar
                  topology={ct.per_residue_topology}
                  ariaLabel={`${rec.gene.hgnc_symbol} canonical isoform topology`}
                />
              </td>
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
                <td className={styles.topoCell}>
                  <TopologyBar
                    topology={iso.per_residue_topology}
                    ariaLabel={`${rec.gene.hgnc_symbol} ${iso.isoform_id} topology`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <TopologyLegend
        presentStates={presentStates([
          ct.per_residue_topology,
          ...df.isoform_topologies.map((iso) => iso.per_residue_topology),
        ])}
      />

      {/* canonical_isoform_caveat was dropped in PR23 round 8 —
          a lone LLM-emitted field inside the deterministic block
          violated the orchestrator-only boundary. Any biological
          note about isoform implications now lives in
          executive_summary.one_paragraph. */}

      {df.isoform_topologies.length === 0 ? (
        <p className={styles.empty}>
          UniProt records no alternative isoforms for {rec.gene.hgnc_symbol}.
        </p>
      ) : null}
    </SectionCard>
  );
}
