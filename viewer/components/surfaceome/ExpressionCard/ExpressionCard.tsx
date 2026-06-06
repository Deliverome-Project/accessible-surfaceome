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
  const norm = (s: string) => s.trim().toLowerCase();
  const UNSPEC = "(tissue unspecified)";

  // Normalize to the unified ExpressionRow shape. New records carry
  // `bc.expression`; pre-unify records carry the split `tissues` +
  // `cell_types`, which we fold into the same shape so both render the same.
  type ERow = {
    tissue: string | null;
    cell_type: string | null;
    present: TissueLevel;
    disease_context: string;
    disease_label?: string | null;
    cited_evidence_ids: string[];
  };
  const rows: ERow[] = bc.expression?.length
    ? bc.expression.map((r) => ({
        tissue: r.tissue,
        cell_type: r.cell_type,
        present: r.present,
        disease_context: r.disease_context,
        disease_label: r.disease_label,
        cited_evidence_ids: r.cited_evidence_ids,
      }))
    : [
        ...(bc.tissues ?? []).map(
          (t): ERow => ({
            tissue: t.tissue,
            cell_type: null,
            present: t.present,
            disease_context: t.disease_context,
            disease_label: t.disease_label,
            cited_evidence_ids: t.cited_evidence_ids,
          }),
        ),
        ...(bc.cell_types ?? []).flatMap((c): ERow[] =>
          (c.present_in_tissues.length ? c.present_in_tissues : [null]).map(
            (tn): ERow => ({
              tissue: tn,
              cell_type: c.cell_type,
              present: c.present ?? "unknown",
              disease_context: c.disease_context ?? "unknown",
              disease_label: c.disease_label,
              cited_evidence_ids: c.cited_evidence_ids,
            }),
          ),
        ),
      ];

  // Group by tissue of origin. A row with a `cell_type` is a cell-of-origin
  // row; a row without one is a tissue-level read (the tissue's "independent"
  // evidence shown on the header). Each row carries its own dx / level /
  // disease label, so no merging or inheritance is needed.
  type CellLike = {
    name: string;
    dx: string | null;
    level: TissueLevel | null;
    label: string | null;
    cites: string[];
  };
  const groups = new Map<
    string,
    { name: string; order: number; reads: ERow[]; cells: CellLike[] }
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
  for (const r of rows) {
    const g = ensure(r.tissue ?? UNSPEC);
    if (r.cell_type) {
      g.cells.push({
        name: r.cell_type,
        dx: r.disease_context,
        level: r.present,
        label: r.disease_label ?? null,
        cites: r.cited_evidence_ids,
      });
    } else {
      g.reads.push(r);
    }
  }

  // Tissue-level reads (cell_type null) are the tissue's independent evidence.
  const independentReads = (g: { reads: ERow[] }) => g.reads;

  // Group order: tissues with a `normal`-context row first, then others;
  // "(tissue unspecified)" last.
  const groupRank = (g: { name: string; reads: ERow[]; cells: CellLike[] }) => {
    if (norm(g.name) === norm(UNSPEC)) return 4;
    const hasNormal =
      g.reads.some((r) => r.disease_context === "normal") ||
      g.cells.some((c) => c.dx === "normal");
    return hasNormal ? 0 : 2;
  };
  const ordered = [...groups.values()].sort(
    (a, b) => groupRank(a) - groupRank(b) || a.order - b.order,
  );

  return (
    <SectionCard
      n={n}
      eyebrow="Expression"
      title="Expression level & tissue distribution"
      meta="Baseline level · breadth · overexpression precedent · by tissue of origin; disease context + level + evidence sit on each cell of origin"
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
                <th scope="col">Tissue / cell of origin</th>
                <th scope="col">Disease context</th>
                <th scope="col">Level (protein)</th>
                <th scope="col">Cites</th>
              </tr>
            </thead>
            <tbody>
              {ordered.flatMap((g) => {
                const indep = independentReads(g);
                const head = indep[0];
                const cells = [...g.cells].sort(
                  (a, b) =>
                    (DISEASE_CONTEXT_RANK[a.dx ?? ""] ?? 9) -
                    (DISEASE_CONTEXT_RANK[b.dx ?? ""] ?? 9),
                );

                // Tissue header: bare unless the tissue has independent
                // (no-cell-breakdown) evidence — then it carries that read.
                const headerRow = (
                  <tr key={`${g.name}-head`} className={styles.tissueHead}>
                    <td>
                      <strong>{g.name}</strong>
                    </td>
                    {head ? (
                      <>
                        <td>
                          <span className={styles.mono}>
                            {head.disease_label ?? prettyEnum(head.disease_context)}
                          </span>
                        </td>
                        <td>
                          <StatusPill tone={tissueLevelTone(head.present)} size="sm">
                            {prettyEnum(head.present)}
                          </StatusPill>
                        </td>
                        <td>
                          <EvidenceChipList
                            ids={head.cited_evidence_ids}
                            label="Cites"
                          />
                        </td>
                      </>
                    ) : (
                      <>
                        <td />
                        <td />
                        <td />
                      </>
                    )}
                  </tr>
                );
                // Any further independent reads as their own tissue-level rows.
                const extraIndep = indep.slice(1).map((r, ri) => (
                  <tr key={`${g.name}-i${ri}`}>
                    <td className={styles.cellRow}>tissue-level</td>
                    <td>
                      <span className={styles.mono}>
                        {r.disease_label ?? prettyEnum(r.disease_context)}
                      </span>
                    </td>
                    <td>
                      <StatusPill tone={tissueLevelTone(r.present)} size="sm">
                        {prettyEnum(r.present)}
                      </StatusPill>
                    </td>
                    <td>
                      <EvidenceChipList ids={r.cited_evidence_ids} label="Cites" />
                    </td>
                  </tr>
                ));
                const cellRows = cells.map((c, ci) => (
                  <tr key={`${g.name}-c${ci}`}>
                    <td className={styles.cellRow}>↳ {c.name}</td>
                    <td>
                      {c.label ? (
                        <span className={styles.mono}>{c.label}</span>
                      ) : c.dx ? (
                        <span className={styles.mono}>{prettyEnum(c.dx)}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {c.level ? (
                        <StatusPill tone={tissueLevelTone(c.level)} size="sm">
                          {prettyEnum(c.level)}
                        </StatusPill>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <EvidenceChipList ids={c.cites} label="Cites" />
                    </td>
                  </tr>
                ));
                return [headerRow, ...extraIndep, ...cellRows];
              })}
            </tbody>
          </table>
        )}
      </div>
    </SectionCard>
  );
}
