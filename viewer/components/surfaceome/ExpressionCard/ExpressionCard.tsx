import type { SurfaceomeRecord, TissueLevel } from "../../../lib/surfaceome-types";
import { prettyEnum } from "../../../lib/surfaceome";
import { EvidenceChipList } from "../EvidenceChip/EvidenceChip";
import { FeatureRationales } from "../FeatureChips/FeatureChips";
import { SectionCard } from "../SectionCard/SectionCard";
import { StatusPill } from "../StatusPill/StatusPill";
import styles from "./ExpressionCard.module.css";

interface Props {
  rec: SurfaceomeRecord;
  n: number;
}

function tissueLevelTone(v: TissueLevel) {
  if (v === "high") return "success" as const;
  if (v === "moderate") return "teal" as const;
  if (v === "low") return "amber" as const;
  if (v === "absent") return "neutral" as const;
  if (v === "mixed") return "lavender" as const;
  return "neutral" as const;
}

/**
 * Expression tab — the LLM expression summary chips (level / breadth /
 * overexpression precedent) sitting above the per-tissue expression
 * evidence table that used to live in BiologicalContextCard. Splitting
 * the tissue-level expression rows out of "Biological context" lets the
 * Expression tab map cleanly to its chip category, while the Biology
 * tab keeps localization / anatomical-accessibility / modulation.
 */
// Disease-context display order: normal first (the on-target / off-tumor
// toxicity baseline), then the disease reads. Lets the reader see each
// organ's normal-tissue level above its tumor level.
const DISEASE_CONTEXT_RANK: Record<string, number> = {
  normal: 0,
  tumor_adjacent: 1,
  tumor: 2,
  other_disease: 3,
  mixed: 4,
  unknown: 5,
};

export function ExpressionCard({ rec, n }: Props) {
  const bc = rec.biological_context;

  // Combine tissues + cell types into ONE view organized by tissue of origin.
  // Each tissue group carries its disease-context reads (normal first — the
  // off-tumor toxicity baseline) plus the cell types whose `present_in_tissues`
  // names that tissue. Cell types also name tissues the tissue table missed
  // (e.g. brain / colon / pancreas tox organs), so those surface as their own
  // groups; cell types with no tissue fall under "(tissue unspecified)".
  type Tissue = (typeof bc.tissues)[number];
  type Cell = (typeof bc.cell_types)[number];
  const norm = (s: string) => s.trim().toLowerCase();
  const UNSPEC = "(tissue unspecified)";

  const groups = new Map<
    string,
    { name: string; order: number; reads: Tissue[]; cells: Cell[] }
  >();
  const ensure = (name: string) => {
    const k = norm(name);
    let g = groups.get(k);
    if (!g) {
      g = { name, order: groups.size, reads: [], cells: [] };
      groups.set(k, g);
    }
    return g;
  };
  bc.tissues.forEach((t) => ensure(t.tissue).reads.push(t));
  bc.cell_types.forEach((c) => {
    const where = c.present_in_tissues.length ? c.present_in_tissues : [UNSPEC];
    where.forEach((tn) => ensure(tn).cells.push(c));
  });

  // Group order: tissues with a `normal` read first, then tissues with any
  // read, then cell-type-only tissues; "(tissue unspecified)" last. Stable on
  // first-appearance order within a rank.
  const groupRank = (g: { name: string; reads: Tissue[] }) => {
    if (norm(g.name) === norm(UNSPEC)) return 4;
    if (g.reads.length === 0) return 3;
    return g.reads.some((t) => t.disease_context === "normal") ? 0 : 2;
  };
  const ordered = [...groups.values()].sort(
    (a, b) => groupRank(a) - groupRank(b) || a.order - b.order,
  );

  return (
    <SectionCard
      n={n}
      eyebrow="Expression"
      title="Expression level & tissue distribution"
      meta="Baseline level · breadth · overexpression precedent · by tissue of origin (normal first), cell types nested"
    >
      <FeatureRationales category="expression" rec={rec} />

      <div className={styles.subsection}>
        <p className={`label-mono ${styles.subhead}`}>Expression by tissue of origin</p>
        {ordered.length === 0 ? (
          <p className={styles.empty}>No tissue or cell-type rows recorded.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tissue / cell type</th>
                <th scope="col">Disease context</th>
                <th scope="col">Level (protein)</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {ordered.flatMap((g) => {
                const reads = [...g.reads].sort(
                  (a, b) =>
                    (DISEASE_CONTEXT_RANK[a.disease_context] ?? 9) -
                    (DISEASE_CONTEXT_RANK[b.disease_context] ?? 9),
                );
                // free-text cell types named on the tissue reads that aren't
                // already covered by a structured cell-type row in this group
                const covered = new Set(g.cells.map((c) => norm(c.cell_type)));
                const freeText = [
                  ...new Set(reads.flatMap((t) => t.cell_types)),
                ].filter((nm) => !covered.has(norm(nm)));

                const headRows =
                  reads.length === 0
                    ? [
                        <tr key={`${g.name}-h`} className={styles.tissueHead}>
                          <td>
                            <strong>{g.name}</strong>
                          </td>
                          <td className={styles.mono}>—</td>
                          <td>—</td>
                          <td>—</td>
                        </tr>,
                      ]
                    : reads.map((t, ri) => (
                        <tr
                          key={`${g.name}-r${ri}`}
                          className={ri === 0 ? styles.tissueHead : undefined}
                        >
                          <td>{ri === 0 ? <strong>{g.name}</strong> : ""}</td>
                          <td>
                            <span className={styles.mono}>
                              {prettyEnum(t.disease_context)}
                            </span>
                          </td>
                          <td>
                            <StatusPill tone={tissueLevelTone(t.present)} size="sm">
                              {prettyEnum(t.present)}
                            </StatusPill>
                            {t.cell_states.length ? (
                              <span className={styles.states}>
                                {" · "}
                                {t.cell_states.join(", ")}
                              </span>
                            ) : null}
                          </td>
                          <td>
                            <EvidenceChipList
                              ids={t.cited_evidence_ids}
                              label="Cites"
                            />
                          </td>
                        </tr>
                      ));

                const cellRows = g.cells.map((c, ci) => (
                  <tr key={`${g.name}-c${ci}`}>
                    <td className={styles.cellRow}>↳ {c.cell_type}</td>
                    <td className={styles.mono}>cell type</td>
                    <td>—</td>
                    <td>
                      <EvidenceChipList ids={c.cited_evidence_ids} label="Cites" />
                    </td>
                  </tr>
                ));

                const freeRows = freeText.map((nm, fi) => (
                  <tr key={`${g.name}-f${fi}`}>
                    <td className={styles.cellRow}>↳ {nm}</td>
                    <td className={styles.mono}>cell type</td>
                    <td>—</td>
                    <td>—</td>
                  </tr>
                ));

                return [...headRows, ...cellRows, ...freeRows];
              })}
            </tbody>
          </table>
        )}
      </div>
    </SectionCard>
  );
}
