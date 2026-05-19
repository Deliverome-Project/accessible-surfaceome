import type {
  OrthologEntry,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./OrthologsCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

const SPECIES: { key: "mouse" | "cynomolgus"; label: string }[] = [
  { key: "mouse", label: "Mouse" },
  { key: "cynomolgus", label: "Cynomolgus" },
];

function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(1)}%`;
}

function SpeciesTable({
  label,
  entries,
}: {
  label: string;
  entries: OrthologEntry[];
}) {
  return (
    <div className={styles.subsection}>
      <p className={`label-mono ${styles.subhead}`}>{label}</p>
      {entries.length === 0 ? (
        <p className={styles.empty}>No ortholog found in Compara.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Canonical</th>
              <th scope="col">Isoform</th>
              <th scope="col">Symbol</th>
              <th scope="col">UniProt</th>
              <th scope="col">Type</th>
              <th scope="col">Full-length %id</th>
              <th scope="col">ECD %id</th>
              <th scope="col">ECD %sim</th>
              <th scope="col">ECD len</th>
              <th scope="col">TM count</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => {
              const ecdMissing = e.ecd_pct_identity_to_human_canonical == null;
              return (
                <tr key={i}>
                  <td>
                    <StatusPill tone={e.is_canonical ? "teal" : "neutral"} size="sm">
                      {e.is_canonical ? "✓" : "alt"}
                    </StatusPill>
                  </td>
                  <td>
                    <span className={styles.mono}>{e.isoform_id}</span>
                  </td>
                  <td>{e.ortholog_symbol}</td>
                  <td>
                    <a
                      className={styles.link}
                      href={`https://www.uniprot.org/uniprotkb/${e.ortholog_uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className={styles.mono}>{e.ortholog_uniprot_acc}</span>
                    </a>
                  </td>
                  <td>
                    <StatusPill tone="lavender" size="sm">
                      {prettyEnum(e.type)}
                    </StatusPill>
                  </td>
                  <td>{fmtPct(e.full_length_pct_identity_to_human_canonical)}</td>
                  <td
                    className={ecdMissing ? styles.muted : undefined}
                    title={ecdMissing ? "Human protein has no ECD to compare (e.g. inner-leaflet, soluble, GPI-anchored)" : undefined}
                  >
                    {fmtPct(e.ecd_pct_identity_to_human_canonical)}
                  </td>
                  <td className={ecdMissing ? styles.muted : undefined}>
                    {fmtPct(e.ecd_pct_similarity_to_human_canonical)}
                  </td>
                  <td>{e.ecd_length_residues} aa</td>
                  <td>{e.tm_helix_count}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function OrthologsCard({ rec, n }: Props) {
  const orthologs = rec.deterministic_features.orthologs;
  const allEntries = [
    ...orthologs.mouse,
    ...orthologs.cynomolgus,
  ];
  const comparaVersion = allEntries[0]?.compara_version ?? "—";
  const toolVersion = rec.deterministic_features.canonical_topology.tool_version;

  return (
    <SectionCard
      n={n}
      eyebrow="Orthologs"
      title="Cross-species orthologs"
      meta={`Deterministic · Ensembl Compara ${comparaVersion} + DeepTMHMM ${toolVersion}`}
      lede="Per-species canonical (and alternative) isoforms with ECD percent identity / similarity to the human canonical."
    >
      {SPECIES.map((s) => (
        <SpeciesTable key={s.key} label={s.label} entries={orthologs[s.key]} />
      ))}
    </SectionCard>
  );
}
