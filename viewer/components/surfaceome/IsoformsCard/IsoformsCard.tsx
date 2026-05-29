import type {
  OrthologEntry,
  SurfaceomeRecord,
} from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { InfoTip } from "../../InfoTip/InfoTip";
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

/** Format a nullable percent as "x.x%" or an em-dash. */
function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(1)}%`;
}

/**
 * One ortholog row in the unified sequence-variants table. Rendered for
 * each mouse / cynomolgus entry. Orthologs carry real alignment numbers
 * (full-length %identity, ECD %identity, ECD %similarity) against the
 * human canonical — those populate the comparison columns directly.
 */
function orthologRow(e: OrthologEntry, key: string, species: string) {
  const ecdMissing = e.ecd_pct_identity_to_human_canonical == null;
  return (
    <tr key={key}>
      <td>
        <div className={styles.variantCell}>
          <StatusPill tone="lavender" size="sm">
            {species}
          </StatusPill>
          <a
            className={styles.link}
            href={`https://www.uniprot.org/uniprotkb/${e.ortholog_uniprot_acc}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className={styles.mono}>
              {e.ortholog_symbol} · {e.ortholog_uniprot_acc}
            </span>
          </a>
          <span className={styles.variantSub}>
            {prettyEnum(e.type)}
            {e.is_canonical ? "" : " · alt isoform"}
          </span>
        </div>
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
}

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

/**
 * Evolutionary context — combined isoforms + orthologs + paralogs.
 *
 * Was previously three separate section cards (§Isoforms, §Orthologs,
 * §Paralogs), then one card with three stacked tables. Per user
 * feedback the isoform-topology table and the per-species ortholog
 * tables are now merged into ONE "sequence variants" table:
 *
 * - Every variant of the protein — the human canonical, its alternative
 *   isoforms, and the mouse / cynomolgus orthologs — is a row in a
 *   single table, so the reader compares "how similar is each version
 *   to the canonical, and what does its topology look like" at a glance.
 * - The shared, comparison-focused columns are: identifier, %identity
 *   (full-length vs the human canonical), ECD %identity, ECD
 *   %similarity, ECD length, TM-helix count, and the DeepTMHMM topology
 *   bar. N-/C-terminal orientation and signal-peptide length (which
 *   only the isoform rows carried) are dropped from the table because
 *   the topology bar already encodes them visually — keeping the merged
 *   table narrow enough to never need horizontal scrolling.
 * - Orthologs carry real alignment numbers; the canonical row is the
 *   reference ("ref"); alternative-isoform identity cells are pending a
 *   full-length alignment (shown as "—" until that lands).
 * - Paralogs stay a compact chip strip below the table — the reader
 *   rarely needs more than "which paralogs and how similar"; the chip's
 *   ECD %id is the load-bearing signal for antibody-cross-reactivity
 *   risk.
 */
export function IsoformsCard({ rec, n }: Props) {
  const df = rec.deterministic_features;
  const ct = df.canonical_topology;
  const orthologs = df.orthologs;
  const paralogs = df.paralogs;

  // Topology-bar union over every row that has a topology (canonical +
  // isoforms + orthologs) so the single TopologyLegend below the table
  // only lists colors that actually appear on this gene.
  const allTopologies = [
    ct.per_residue_topology,
    ...df.isoform_topologies.map((iso) => iso.per_residue_topology),
    ...orthologs.mouse.map((e) => e.per_residue_topology),
    ...orthologs.cynomolgus.map((e) => e.per_residue_topology),
  ].filter((t): t is string => !!t);

  // Compara version label comes from the first entry that has one (the
  // builder fills the same value across all rows in a release).
  const comparaVersion =
    orthologs.mouse[0]?.compara_version
    ?? orthologs.cynomolgus[0]?.compara_version
    ?? paralogs[0]?.compara_version
    ?? "—";

  const noOrthologs =
    orthologs.mouse.length === 0 && orthologs.cynomolgus.length === 0;

  return (
    <SectionCard
      n={n}
      eyebrow="Evolutionary context"
      title="Isoforms, orthologs & paralogs"
      meta={`Deterministic · UniProt + DeepTMHMM ${ct.tool_version} · Ensembl Compara ${comparaVersion}`}
    >
      {/* ---- Unified sequence-variants table ----------------------- */}
      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>
          Sequence variants · canonical, isoforms &amp; cross-species orthologs
        </p>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col">
                  %identity
                  <InfoTip label="About percent identity">
                    Percent identity — the fraction of aligned positions
                    holding the exact same amino acid. Shown full-length,
                    against the human canonical sequence.
                  </InfoTip>
                </th>
                <th scope="col">
                  ECD %id
                  <InfoTip label="About ECD percent identity">
                    Percent identity restricted to extracellular-domain
                    residues — the antibody-accessible surface — rather than
                    the whole protein.
                  </InfoTip>
                </th>
                <th scope="col">
                  ECD %sim
                  <InfoTip label="About percent similarity" align="end">
                    Percent similarity — like identity, but also counts
                    conservative substitutions (residue pairs scoring
                    positive in BLOSUM62, e.g. Leu↔Ile). Always ≥ percent
                    identity. Scoped to the extracellular domain.
                  </InfoTip>
                </th>
                <th scope="col">ECD len</th>
                <th scope="col">TM</th>
                <th scope="col" className={styles.topoCol}>
                  Topology
                </th>
              </tr>
            </thead>
            <tbody>
              {/* Canonical — the reference everything else compares to. */}
              <tr className={styles.canonicalRow}>
                <td>
                  <div className={styles.variantCell}>
                    <StatusPill tone="teal" size="sm">
                      Canonical
                    </StatusPill>
                    <span className={styles.mono}>{rec.gene.uniprot_acc}</span>
                  </div>
                </td>
                <td className={styles.refCell}>ref</td>
                <td className={styles.refCell}>ref</td>
                <td className={styles.refCell}>ref</td>
                <td>{ct.ecd_length_residues} aa</td>
                <td>{ct.tm_helix_count}</td>
                <td className={styles.topoCell}>
                  <TopologyBar
                    topology={ct.per_residue_topology}
                    ariaLabel={`${rec.gene.hgnc_symbol} canonical isoform topology`}
                  />
                </td>
              </tr>

              {/* Alternative isoforms — full-length %identity to the
                  canonical is pending a sequence alignment, so the
                  identity columns show "—" for now. */}
              {df.isoform_topologies.map((iso, i) => (
                <tr key={`iso-${i}`}>
                  <td>
                    <div className={styles.variantCell}>
                      <StatusPill tone="neutral" size="sm">
                        Isoform
                      </StatusPill>
                      <span className={styles.mono}>{iso.isoform_id}</span>
                    </div>
                  </td>
                  <td
                    className={styles.muted}
                    title="Full-length alignment to the canonical sequence pending"
                  >
                    —
                  </td>
                  <td className={styles.muted}>—</td>
                  <td className={styles.muted}>—</td>
                  <td>{iso.ecd_length_residues} aa</td>
                  <td>{iso.tm_helix_count}</td>
                  <td className={styles.topoCell}>
                    <TopologyBar
                      topology={iso.per_residue_topology}
                      ariaLabel={`${rec.gene.hgnc_symbol} ${iso.isoform_id} topology`}
                    />
                  </td>
                </tr>
              ))}

              {/* Orthologs — mouse then cynomolgus, with real alignment
                  numbers against the human canonical. */}
              {orthologs.mouse.map((e, i) =>
                orthologRow(e, `mouse-${i}`, "Mouse"),
              )}
              {orthologs.cynomolgus.map((e, i) =>
                orthologRow(e, `cyno-${i}`, "Cyno"),
              )}
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

        {noOrthologs ? (
          <p className={styles.empty}>
            No mouse or cynomolgus ortholog found in Ensembl Compara.
          </p>
        ) : null}
      </div>

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
              <li key={i} className={styles.paralogChip}>
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
              </li>
            ))}
          </ul>
        )}
      </div>
    </SectionCard>
  );
}
