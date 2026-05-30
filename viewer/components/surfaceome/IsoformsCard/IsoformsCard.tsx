import type {
  IsoformTopology,
  Orientation,
  OrthologEntry,
  ParalogEntry,
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

/** Terminal-orientation pill — teal when the terminus faces the
 *  extracellular space, neutral when it sits cytoplasmic. */
function orientationPill(o: Orientation) {
  return (
    <StatusPill tone={o === "extracellular" ? "teal" : "neutral"} size="sm">
      {prettyEnum(o)}
    </StatusPill>
  );
}

/**
 * The six DeepTMHMM topology-detail cells shared by the canonical and
 * alternative-isoform rows: ECD length · ICD length · TM-helix count ·
 * N-terminal orientation · C-terminal orientation · signal-peptide
 * length. Both `canonical_topology` (CanonicalTopology) and each
 * `isoform_topologies[]` entry (IsoformTopology) structurally carry
 * these fields, so the Pick below type-checks for either. Orthologs
 * only carry ECD length + TM count from Compara directly, so
 * `orthologRow` renders its own cells — deriving ICD length, the two
 * terminal orientations, and signal-peptide length from the ortholog's
 * DeepTMHMM topology string (see `deriveOrthologDetail`).
 */
type TopologyDetail = Pick<
  IsoformTopology,
  | "ecd_length_residues"
  | "icd_length_residues"
  | "tm_helix_count"
  | "n_terminal_orientation"
  | "c_terminal_orientation"
  | "signal_peptide_length"
>;

function topologyDetailCells(t: TopologyDetail) {
  return (
    <>
      <td>{t.ecd_length_residues} aa</td>
      <td>{t.icd_length_residues} aa</td>
      <td>{t.tm_helix_count}</td>
      <td>{orientationPill(t.n_terminal_orientation)}</td>
      <td>{orientationPill(t.c_terminal_orientation)}</td>
      <td>{t.signal_peptide_length} aa</td>
    </>
  );
}

/** Map a DeepTMHMM terminal-side character to the viewer's two-member
 *  Orientation union. O (outside) / B (beta-strand, periplasm-facing) →
 *  extracellular; I (inside) → cytoplasmic. Anything else (a membrane
 *  residue at the terminus, or an empty string) is "indeterminate" in
 *  the backend enum, which the viewer's Orientation type can't express —
 *  return null so the caller renders an em-dash for that one cell. */
function terminalOrientation(side: string): Orientation | null {
  if (side === "O" || side === "B") return "extracellular";
  if (side === "I") return "cytoplasmic";
  return null;
}

/**
 * Derive the topology-detail scalars Ensembl Compara doesn't store on an
 * `OrthologEntry` — signal-peptide length, ICD length, and the two
 * terminal orientations — straight from the per-residue DeepTMHMM
 * topology string the ortholog now carries. Mirrors the backend parse in
 * `sources/deeptmhmm.py` exactly: the leading run of "S" is the signal
 * peptide; ICD length is the count of "I" (cytoplasmic) residues; the
 * terminal orientation is the first / last non-"S" character. Lets the
 * ortholog rows read with the same topology detail as the canonical /
 * isoform rows instead of four em-dashes. (ECD length + TM count come
 * from the stored Compara fields, so they aren't re-derived here.)
 */
function deriveOrthologDetail(topology: string): {
  signal_peptide_length: number;
  icd_length_residues: number;
  n_terminal_orientation: Orientation | null;
  c_terminal_orientation: Orientation | null;
} {
  const topo = topology.toUpperCase();
  let sp = 0;
  for (const ch of topo) {
    if (ch === "S") sp += 1;
    else break;
  }
  let firstNonS = "";
  let lastNonS = "";
  let icd = 0;
  for (const ch of topo) {
    if (ch !== "S") {
      if (firstNonS === "") firstNonS = ch;
      lastNonS = ch;
    }
    if (ch === "I") icd += 1;
  }
  return {
    signal_peptide_length: sp,
    icd_length_residues: icd,
    n_terminal_orientation: terminalOrientation(firstNonS),
    c_terminal_orientation: terminalOrientation(lastNonS),
  };
}

/**
 * Paralog antibody-cross-reactivity risk tier from a percent identity.
 * The bands are our heuristic; that cross-reactive binding tracks
 * sequence identity follows antibody-validation practice (Bordeaux
 * et al. 2010, PMID 20359301; Edfors et al. 2018, PMID 30297845):
 *   ≥ 70% → cross-reactivity likely    ("high")
 *   ≥ 50% → cross-reactivity plausible ("med")
 *   < 50% → low
 * `null` only when the paralog carries no identity number at all
 * (pre-population records) — the chip then stays neutral.
 */
function paralogRiskTier(pct: number | null): "high" | "med" | "low" | null {
  if (pct == null) return null;
  if (pct >= 70) return "high";
  if (pct >= 50) return "med";
  return "low";
}

/**
 * The percent identity a paralog chip is colored + floored by: ECD
 * identity when the protein has an extracellular domain, else the
 * whole-protein (full-length) identity so ECD-less proteins (SRC-family
 * kinases, soluble / cytoplasmic enzymes) still get a homology-based
 * cross-reactivity tier rather than a neutral "no ECD" chip. Null only on
 * pre-population records that carry neither number.
 */
function paralogRiskValue(p: ParalogEntry): number | null {
  return p.ecd_pct_identity ?? p.full_length_pct_identity ?? null;
}

/**
 * One ortholog row in the unified sequence-variants table. Rendered for
 * each mouse / cynomolgus entry. Orthologs carry real alignment numbers
 * (full-length %identity, ECD %identity, ECD %similarity) against the
 * human canonical — those populate the comparison columns directly.
 */
function orthologRow(e: OrthologEntry, key: string, species: string) {
  const ecdMissing = e.ecd_pct_identity_to_human_canonical == null;
  // ICD length / terminal orientations / signal-peptide length aren't in
  // the Compara record, but they're derivable from the ortholog's own
  // DeepTMHMM topology string (same parse the backend runs for the
  // canonical + isoforms). Null when the ortholog has no topology yet.
  const detail = e.per_residue_topology
    ? deriveOrthologDetail(e.per_residue_topology)
    : null;
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
            {/* Bare UniProt accession only — matches the isoform rows'
                identifier treatment (which show just the isoform_id). The
                lavender species pill above already labels mouse / cyno, so
                the ortholog symbol would be redundant; the ortholog type
                (one-to-one etc.) sits in the variantSub below. */}
            <span className={styles.mono}>{e.ortholog_uniprot_acc}</span>
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
      {/* ICD length / terminal orientations / signal-peptide length —
          derived from the ortholog's DeepTMHMM topology (see `detail`).
          Em-dash only when the ortholog has no topology string yet. */}
      <td className={detail ? undefined : styles.muted}>
        {detail ? `${detail.icd_length_residues} aa` : "—"}
      </td>
      <td>{e.tm_helix_count}</td>
      <td className={detail?.n_terminal_orientation ? undefined : styles.muted}>
        {detail?.n_terminal_orientation
          ? orientationPill(detail.n_terminal_orientation)
          : "—"}
      </td>
      <td className={detail?.c_terminal_orientation ? undefined : styles.muted}>
        {detail?.c_terminal_orientation
          ? orientationPill(detail.c_terminal_orientation)
          : "—"}
      </td>
      <td className={detail ? undefined : styles.muted}>
        {detail ? `${detail.signal_peptide_length} aa` : "—"}
      </td>
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
 * - The columns are: identifier, %identity (full-length vs the human
 *   canonical), ECD %identity, ECD %similarity, ECD length, ICD length,
 *   TM-helix count, N-terminal orientation, C-terminal orientation,
 *   signal-peptide length, and the DeepTMHMM topology bar. The
 *   per-terminus / ICD-length / signal-peptide columns come from
 *   DeepTMHMM: stored directly on the canonical + isoform rows, and
 *   derived from the ortholog's own topology string for ortholog rows
 *   (an ortholog only shows em-dashes there if its topology hasn't been
 *   computed yet). The table is wide enough that the wrapper scrolls
 *   horizontally on narrow viewports.
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

  // Three framings for the paralog strip:
  //  • coloredByEcd     — protein has an ECD; chips colored by ECD %id.
  //  • coloredByFullLen — ECD-less protein (SRC and other intracellular /
  //    soluble / GPI-anchored proteins) where every paralog is "no ECD",
  //    but whole-protein (full-length) identities exist, so chips fall
  //    back to that homology number with the same risk tiers.
  //  • neither          — pre-population records with no identity at all;
  //    the strip lists the family with no risk coloring.
  const anyParalogEcd = paralogs.some((p) => p.ecd_pct_identity != null);
  const anyParalogFullLen = paralogs.some(
    (p) => p.full_length_pct_identity != null,
  );
  const coloredByEcd = anyParalogEcd;
  const coloredByFullLen = !anyParalogEcd && anyParalogFullLen;
  const anyParalogRisk = coloredByEcd || coloredByFullLen;

  // Visibility floor: when there's an identity to threshold on (ECD, or
  // full-length for ECD-less proteins), only paralogs above 40% are worth
  // surfacing — below that the cross-reactivity signal is negligible and
  // the strip just gets noisy (kinome / Ig-superfamily proteins have
  // dozens of distant paralogs). Anything at or below 40% is hidden
  // entirely. Records with no identity at all (pre-population) show the
  // whole family with the neutral "sequence family" framing.
  const PARALOG_MIN_PCT = 40;
  const visibleParalogs = anyParalogRisk
    ? paralogs.filter((p) => {
        const v = paralogRiskValue(p);
        return v != null && v > PARALOG_MIN_PCT;
      })
    : paralogs;

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
                <th scope="col">ICD len</th>
                <th scope="col">TM count</th>
                <th scope="col">N-term</th>
                <th scope="col">C-term</th>
                <th scope="col">Signal pep</th>
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
                    <a
                      className={styles.link}
                      href={`https://www.uniprot.org/uniprotkb/${rec.gene.uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className={styles.mono}>{rec.gene.uniprot_acc}</span>
                    </a>
                  </div>
                </td>
                <td className={styles.refCell}>ref</td>
                <td className={styles.refCell}>ref</td>
                <td className={styles.refCell}>ref</td>
                {topologyDetailCells(ct)}
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
                      <a
                        className={styles.link}
                        href={`https://www.uniprot.org/uniprotkb/${iso.isoform_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <span className={styles.mono}>{iso.isoform_id}</span>
                      </a>
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
                  {topologyDetailCells(iso)}
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
          {coloredByEcd
            ? "Paralogs · within-species, ECD percent identity"
            : coloredByFullLen
              ? "Paralogs · within-species, full-length identity"
              : "Paralogs · within-species sequence family"}
          <InfoTip label="About paralog cross-reactivity">
            {coloredByEcd ? (
              <>
                Percent identity over the extracellular domain — the
                antibody-accessible region — between {rec.gene.hgnc_symbol} and
                each within-species paralog. Antibody cross-reactivity tracks
                ECD identity, so the chips are colored by risk:{" "}
                <strong>≥70% likely</strong>, 50–70% plausible, &lt;50% low.
                The bands are our heuristic; the principle that
                cross-reactivity tracks identity follows antibody-validation
                practice (Bordeaux 2010, PMID 20359301; Edfors 2018,
                PMID 30297845). Paralogs at or below 40% ECD identity are hidden
                — their cross-reactivity signal is negligible.
              </>
            ) : coloredByFullLen ? (
              <>
                {rec.gene.hgnc_symbol} has no extracellular domain (it&rsquo;s
                intracellular / soluble), so there&rsquo;s no ECD to align.
                Cross-reactivity risk here is keyed to{" "}
                <strong>whole-protein</strong> sequence identity instead, with
                the same tiers: <strong>≥70% likely</strong>, 50–70% plausible,
                &lt;50% low. The bands are our heuristic; the principle that
                cross-reactivity tracks identity follows antibody-validation
                practice (Bordeaux 2010, PMID 20359301; Edfors 2018,
                PMID 30297845). Paralogs at or below 40% identity are hidden —
                their cross-reactivity signal is negligible.
              </>
            ) : (
              <>
                {rec.gene.hgnc_symbol} has no extracellular domain (it&rsquo;s
                intracellular / soluble), so there&rsquo;s no ECD sequence to
                align against its paralogs. The cross-reactivity cutoffs
                (≥50% plausible, ≥70% likely) don&rsquo;t apply here; the family
                is listed for completeness.
              </>
            )}
          </InfoTip>
        </p>
        {paralogs.length === 0 ? (
          <p className={styles.empty}>No paralogs in Compara.</p>
        ) : visibleParalogs.length === 0 ? (
          // Protein whose paralogs are all at or below the 40% floor —
          // nothing crosses the threshold worth surfacing.
          <p className={styles.empty}>
            No paralogs above 40% identity in Compara.
          </p>
        ) : (
          <>
            <ul className={styles.paralogChips} aria-label="Paralog list">
              {visibleParalogs.map((p, i) => {
                // Color + label by ECD identity, falling back to the
                // whole-protein (full-length) identity for ECD-less
                // proteins so SRC-family paralogs still get a risk tier.
                const riskVal = paralogRiskValue(p);
                const tier = paralogRiskTier(riskVal);
                const tierClass =
                  tier === "high"
                    ? styles.riskHigh
                    : tier === "med"
                      ? styles.riskMed
                      : tier === "low"
                        ? styles.riskLow
                        : "";
                return (
                  <li key={i} className={styles.paralogChip}>
                    <a
                      className={`${styles.paralogChipLink}${tierClass ? ` ${tierClass}` : ""}`}
                      href={`https://www.uniprot.org/uniprotkb/${p.paralog_uniprot_acc}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`${p.paralog_symbol} · ${p.paralog_uniprot_acc} · family ${p.family_id}`}
                    >
                      <span className={styles.paralogChipSym}>
                        {p.paralog_symbol}
                      </span>
                      <span className={styles.paralogChipPct}>
                        {/* riskVal is null only on pre-population records
                         *  that carry neither an ECD nor a full-length
                         *  identity — show "no ECD" rather than crash on
                         *  .toFixed(). */}
                        {riskVal != null
                          ? `${riskVal.toFixed(0)}%`
                          : "no ECD"}
                      </span>
                    </a>
                  </li>
                );
              })}
            </ul>
            {/* Risk legend — only when there's an identity to color by
                (ECD, or full-length for ECD-less proteins). Pre-population
                records with no identity skip it; the subhead InfoTip
                explains why the cutoffs don't apply. */}
            {anyParalogRisk ? (
              <p className={styles.paralogLegend} aria-hidden="true">
                <span className={styles.paralogLegendItem}>
                  <span
                    className={`${styles.paralogLegendDot} ${styles.riskHigh}`}
                  />
                  ≥70% likely
                </span>
                <span className={styles.paralogLegendItem}>
                  <span
                    className={`${styles.paralogLegendDot} ${styles.riskMed}`}
                  />
                  50–70% plausible
                </span>
                <span className={styles.paralogLegendItem}>
                  <span
                    className={`${styles.paralogLegendDot} ${styles.riskLow}`}
                  />
                  &lt;50% low
                </span>
              </p>
            ) : null}
          </>
        )}
      </div>
    </SectionCard>
  );
}
