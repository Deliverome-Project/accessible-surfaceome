import type {
  OrthologEntry,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
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

/**
 * Evolutionary context — combined isoforms + orthologs + paralogs.
 *
 * Was previously three separate section cards (§Isoforms, §Orthologs,
 * §Paralogs). Per user feedback, combined into ONE section because:
 *
 * - Isoforms, orthologs, and paralogs are all variants of "what other
 *   things look like this protein"; collapsing them into one card
 *   matches the reader's mental model and trims three tabs from the
 *   AnchorNav strip.
 * - Orthologs no longer need their own header — the per-species rows
 *   sit directly under the isoform-topology table for a one-glance
 *   comparison of canonical / isoform / cross-species sequence.
 * - Paralogs condense to a chip strip — the reader rarely needs more
 *   than "which paralogs and how similar"; the full family-id column
 *   was noise. The chip's ECD %id is the load-bearing signal for
 *   antibody-cross-reactivity risk.
 *
 * Topology bars render for canonical + alternative isoforms AND for
 * paralogs / orthologs — every variant whose ``per_residue_topology``
 * is populated gets its own slim DeepTMHMM strip so the reader can
 * eyeball cross-reactivity surface conservation at a glance. The
 * paralog / ortholog topology fields are nullable; when absent the
 * row renders a "no topology" placeholder so the table layout
 * stays stable.
 */
export function IsoformsCard({ rec, n }: Props) {
  const df = rec.deterministic_features;
  const ct = df.canonical_topology;
  const orthologs = df.orthologs;
  const paralogs = df.paralogs;

  // Compute the topology-bar union over canonical + all isoforms so
  // the single TopologyLegend at the bottom only lists colors that
  // actually appear on this gene.
  const allTopologies = [
    ct.per_residue_topology,
    ...df.isoform_topologies.map((iso) => iso.per_residue_topology),
  ];

  // Orthologs list is canonical-first per species. The Compara
  // version label comes from the first entry that has one (the
  // builder fills the same value across all rows in a release).
  const comparaVersion =
    orthologs.mouse[0]?.compara_version
    ?? orthologs.cynomolgus[0]?.compara_version
    ?? paralogs[0]?.compara_version
    ?? "—";

  return (
    <SectionCard
      n={n}
      eyebrow="Evolutionary context"
      title="Isoforms, orthologs & paralogs"
      meta={`Deterministic · UniProt + DeepTMHMM ${ct.tool_version} · Ensembl Compara ${comparaVersion}`}
      lede="Same protein across alternative isoforms, orthologs (mouse + cyno), and within-species paralogs. Topology bars are shown for every variant whose DeepTMHMM topology is in the record."
    >
      {/* ---- Isoforms (topology) ------------------------------------- */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          Isoforms · per-isoform topology
        </p>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Isoform</th>
                <th scope="col">UniProt</th>
                <th scope="col">TM</th>
                <th scope="col">N-term</th>
                <th scope="col">C-term</th>
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
                <td>
                  <StatusPill
                    tone={ct.c_terminal_orientation === "extracellular" ? "teal" : "neutral"}
                    size="sm"
                  >
                    {prettyEnum(ct.c_terminal_orientation)}
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
                  <td>
                    <StatusPill
                      tone={
                        iso.c_terminal_orientation === "extracellular" ? "teal" : "neutral"
                      }
                      size="sm"
                    >
                      {prettyEnum(iso.c_terminal_orientation)}
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
          presentStates={presentStates(allTopologies)}
          showMembrane={false}
        />

        {df.isoform_topologies.length === 0 ? (
          <p className={styles.empty}>
            No alternative isoforms in our DeepTMHMM coverage for{" "}
            {rec.gene.hgnc_symbol}. (UniProt may list additional isoforms whose
            topology hasn&rsquo;t been computed yet — see the canonical entry at{" "}
            <a
              href={`https://www.uniprot.org/uniprotkb/${rec.gene.uniprot_acc}/entry#sequences`}
              target="_blank"
              rel="noopener noreferrer"
            >
              uniprot.org/{rec.gene.uniprot_acc}
            </a>
            .)
          </p>
        ) : null}
      </div>

      {/* ---- Orthologs (mouse + cyno) ----------------------------- */}
      <OrthologsSubsection
        label="Mouse"
        entries={orthologs.mouse}
        geneSymbol={rec.gene.hgnc_symbol}
      />
      <OrthologsSubsection
        label="Cynomolgus"
        entries={orthologs.cynomolgus}
        geneSymbol={rec.gene.hgnc_symbol}
      />

      {/* ---- Paralogs (compact chip strip) ------------------------ */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          Paralogs · within-species, ECD percent identity
        </p>
        {paralogs.length === 0 ? (
          <p className={styles.empty}>No paralogs in Compara.</p>
        ) : (
          <ul className={styles.paralogChips} aria-label="Paralog list">
            {paralogs.map((p, i) => (
              <li key={i} className={styles.paralogChipCell}>
                <a
                  className={styles.paralogChipLink}
                  href={`https://www.uniprot.org/uniprotkb/${p.paralog_uniprot_acc}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${p.paralog_symbol} · ${p.paralog_uniprot_acc} · family ${p.family_id}`}
                >
                  <span className={styles.paralogChipSym}>{p.paralog_symbol}</span>
                  <span className={styles.paralogChipPct}>
                    {/* ecd_pct_identity is null for ECD-less proteins
                     *  (SRC, soluble kinases, GPI-anchored, cytoplasmic
                     *  enzymes) — no ECD to compute identity against.
                     *  Show "no ECD" instead of crashing on .toFixed(). */}
                    {p.ecd_pct_identity != null
                      ? `${p.ecd_pct_identity.toFixed(0)}%`
                      : "no ECD"}
                  </span>
                </a>
                {/* Per-residue DeepTMHMM strip beneath the chip — only
                 *  when the paralog's canonical topology is in our
                 *  cohort. Same component the isoform table uses so the
                 *  colors and proportional layout match. */}
                {p.per_residue_topology ? (
                  <div className={styles.paralogChipBar}>
                    <TopologyBar
                      topology={p.per_residue_topology}
                      ariaLabel={`${p.paralog_symbol} canonical topology`}
                    />
                  </div>
                ) : (
                  <div className={`${styles.paralogChipBar} ${styles.paralogChipBarEmpty}`}>
                    no topology
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </SectionCard>
  );
}

/** One-species ortholog subsection — compact table. */
function OrthologsSubsection({
  label,
  entries,
  geneSymbol,
}: {
  label: string;
  entries: OrthologEntry[];
  geneSymbol: string;
}) {
  const _gene = geneSymbol; // currently unused — kept for future per-row ariaLabel
  void _gene;
  return (
    <div className={styles.subsection}>
      <p className={`label-mono ${styles.subhead}`}>
        {label} orthologs · Compara
      </p>
      {entries.length === 0 ? (
        <p className={styles.empty}>No ortholog found in Compara.</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Canonical</th>
                <th scope="col">Isoform</th>
                <th scope="col">Symbol</th>
                <th scope="col">UniProt</th>
                <th scope="col">Type</th>
                <th scope="col">Full %id</th>
                <th scope="col">ECD %id</th>
                <th scope="col">ECD %sim</th>
                <th scope="col">ECD len</th>
                <th scope="col">TM count</th>
                <th scope="col" className={styles.topoCol}>
                  Topology
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => {
                const ecdMissing = e.ecd_pct_identity_to_human_canonical == null;
                const fmtPct = (v: number | null | undefined) =>
                  v == null ? "—" : `${v.toFixed(1)}%`;
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
                      title={
                        ecdMissing
                          ? "Human protein has no ECD to compare (e.g. inner-leaflet, soluble, GPI-anchored)"
                          : undefined
                      }
                    >
                      {fmtPct(e.ecd_pct_identity_to_human_canonical)}
                    </td>
                    <td className={ecdMissing ? styles.muted : undefined}>
                      {fmtPct(e.ecd_pct_similarity_to_human_canonical)}
                    </td>
                    <td>{e.ecd_length_residues} aa</td>
                    <td>{e.tm_helix_count}</td>
                    <td className={styles.topoCell}>
                      {e.per_residue_topology ? (
                        <TopologyBar
                          topology={e.per_residue_topology}
                          ariaLabel={`${e.ortholog_symbol} ortholog topology`}
                        />
                      ) : (
                        <span className={styles.muted}>no topology</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
