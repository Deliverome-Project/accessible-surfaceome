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
  canonicalTmCount,
}: {
  label: string;
  entries: OrthologEntry[];
  canonicalTmCount: number;
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
              // "Same topology" = the ortholog keeps the human canonical's
              // transmembrane-helix count (the reliable stored Compara field
              // and the dominant topology axis for a surface protein). A
              // mismatch means a membrane pass was gained / lost between
              // species — the human-targeting epitope may not translate.
              // Topology dot state vs the human canonical:
              //   absent   → a human TM helix fell into a gap in this
              //              (truncated) ortholog model; conserved by homology
              //              but not physically in the model → gray, NOT a
              //              divergence (e.g. cyno EGFR's 704/1210-aa model).
              //   same     → same TM-helix count → green.
              //   distinct → genuinely different count → amber.
              const topoState: "absent" | "same" | "distinct" =
                e.tm_absent_from_model
                  ? "absent"
                  : e.tm_helix_count === canonicalTmCount
                    ? "same"
                    : "distinct";
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
                  <td>
                    <span className={styles.topoCell}>
                      <span
                        className={`${styles.topoDot} ${
                          topoState === "same"
                            ? styles.topoSame
                            : topoState === "distinct"
                              ? styles.topoDistinct
                              : styles.topoAbsent
                        }`}
                        aria-label={
                          topoState === "same"
                            ? "Same membrane topology as the human canonical"
                            : topoState === "distinct"
                              ? "Distinct membrane topology from the human canonical"
                              : "Topology conserved by homology; a TM region is absent from this truncated ortholog model"
                        }
                        title={
                          topoState === "same"
                            ? `Same transmembrane-helix count as the human canonical (${canonicalTmCount} TM) — conserved membrane architecture`
                            : topoState === "distinct"
                              ? `Different transmembrane-helix count from the human canonical (${e.tm_helix_count} vs ${canonicalTmCount} TM) — membrane architecture diverged between species`
                              : `Partial ortholog model — ${e.n_tm_regions_absent ?? 1} transmembrane region(s) absent from this truncated sequence. Topology is conserved by homology (human has ${canonicalTmCount} TM); the model just doesn't cover it.`
                        }
                      />
                      {e.tm_helix_count}
                    </span>
                  </td>
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
  const canonicalTopology = rec.deterministic_features.canonical_topology;
  const toolVersion = canonicalTopology.tool_version;

  return (
    <SectionCard
      n={n}
      eyebrow="Orthologs"
      title="Cross-species orthologs"
      meta={`Deterministic · Ensembl Compara ${comparaVersion} + DeepTMHMM ${toolVersion}`}
      lede="Per-species canonical (and alternative) isoforms with ECD percent identity / similarity to the human canonical. Topology is projected from the human canonical by alignment (robust to truncated / padded ortholog models). The dot on TM count flags whether the ortholog keeps the human membrane-pass count (green), differs (amber), or has a TM region absent from a truncated model (gray)."
    >
      {SPECIES.map((s) => (
        <SpeciesTable
          key={s.key}
          label={s.label}
          entries={orthologs[s.key]}
          canonicalTmCount={canonicalTopology.tm_helix_count}
        />
      ))}
    </SectionCard>
  );
}
