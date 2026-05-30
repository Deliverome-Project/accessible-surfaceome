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
              // Membrane-topology dot vs the human canonical. Topology is
              // projected from the human canonical by alignment, so it's
              // conserved by construction; the dot only flags whether the
              // ortholog keeps the canonical transmembrane-helix count.
              //   same     → same TM count, OR conserved-by-homology where a
              //              human TM falls outside a truncated ortholog model
              //              (e.g. an ECD-only cyno TrEMBL fragment like EGFR's
              //              704/1210-aa A0A2K5WKD8) → green.
              //   distinct → genuinely different count on a model that DOES
              //              cover the region → amber.
              // A partial model that simply doesn't reach a human TM is still
              // topologically conserved, so we report the canonical count and
              // treat it as `same`, explaining the inference in the tooltip —
              // not flagging a fake divergence (no gray "absent" state).
              const inferredFromPartialModel = Boolean(e.tm_absent_from_model);
              const displayTmCount = inferredFromPartialModel
                ? canonicalTmCount
                : e.tm_helix_count;
              const topoState: "same" | "distinct" =
                inferredFromPartialModel || displayTmCount === canonicalTmCount
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
                            : styles.topoDistinct
                        }`}
                        aria-label={
                          topoState === "same"
                            ? "Same membrane topology as the human canonical"
                            : "Distinct membrane topology from the human canonical"
                        }
                        title={
                          inferredFromPartialModel
                            ? `Topology conserved by homology. This ortholog model is partial (${e.tm_helix_count} TM physically modelled) and doesn't cover ${e.n_tm_regions_absent ?? 1} human TM region(s); shown at the conserved canonical count (${canonicalTmCount} TM).`
                            : topoState === "same"
                              ? `Same transmembrane-helix count as the human canonical (${canonicalTmCount} TM) — conserved membrane architecture`
                              : `Different transmembrane-helix count from the human canonical (${e.tm_helix_count} vs ${canonicalTmCount} TM) — membrane architecture diverged between species`
                        }
                      />
                      {displayTmCount}
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
      lede="Per-species canonical (and alternative) isoforms with ECD percent identity / similarity to the human canonical. Topology is projected from the human canonical by alignment (robust to truncated / padded ortholog models). The dot on TM count flags whether the ortholog keeps the human membrane-pass count (green) or genuinely differs (amber); a truncated ortholog model that doesn't physically cover a TM is still counted as conserved (green) at the canonical count."
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
