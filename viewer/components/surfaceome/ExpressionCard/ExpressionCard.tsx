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

  // ONE view organized by tissue of origin. The CELL-of-origin row is the
  // unit of evidence — it carries the disease context + level (inherited from
  // the tissue read that names it) and the citations. The tissue (header) row
  // is a bare grouping label; it only shows dx / level / cites when the tissue
  // has INDEPENDENT evidence (a read with no cell-type breakdown), so we never
  // replicate the same observation on both the tissue row and its cell row.
  // Cell types also name tissues that carry no tissue-level read (e.g. brain /
  // colon / pancreas tox organs) — those surface as their own groups; cell
  // types with no tissue fall under "(tissue unspecified)".
  type Tissue = (typeof bc.tissues)[number];
  type CellRow = {
    name: string;
    dx: string | null;
    level: TissueLevel | null;
    cites: Set<string>;
  };
  const norm = (s: string) => s.trim().toLowerCase();
  const UNSPEC = "(tissue unspecified)";

  const groups = new Map<
    string,
    { name: string; order: number; reads: Tissue[]; cells: Map<string, CellRow> }
  >();
  const ensure = (name: string) => {
    const k = norm(name);
    let g = groups.get(k);
    if (!g) {
      g = { name, order: groups.size, reads: [], cells: new Map() };
      groups.set(k, g);
    }
    return g;
  };
  const cellIn = (g: { cells: Map<string, CellRow> }, name: string) => {
    const k = norm(name);
    let c = g.cells.get(k);
    if (!c) {
      c = { name, dx: null, level: null, cites: new Set() };
      g.cells.set(k, c);
    }
    return c;
  };

  // Tissue reads push their dx + level + cites down onto the cell they name.
  bc.tissues.forEach((t) => {
    const g = ensure(t.tissue);
    g.reads.push(t);
    t.cell_types.forEach((cn) => {
      const c = cellIn(g, cn);
      c.dx = t.disease_context;
      c.level = t.present;
      t.cited_evidence_ids.forEach((id) => c.cites.add(id));
    });
  });
  // Cell-type records add their citations (and surface tissues with no
  // tissue-level read). They carry no dx / level of their own.
  bc.cell_types.forEach((ct) => {
    const where = ct.present_in_tissues.length ? ct.present_in_tissues : [UNSPEC];
    where.forEach((tn) => {
      const c = cellIn(ensure(tn), ct.cell_type);
      ct.cited_evidence_ids.forEach((id) => c.cites.add(id));
    });
  });

  // A read with NO cell breakdown is the tissue's own independent evidence.
  const independentReads = (g: { reads: Tissue[] }) =>
    g.reads.filter((r) => r.cell_types.length === 0);

  // Group order: tissues with a `normal` read first, then tissues with any
  // read, then cell-type-only tissues; "(tissue unspecified)" last.
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
                const cells = [...g.cells.values()].sort(
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
                            {prettyEnum(head.disease_context)}
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
                        {prettyEnum(r.disease_context)}
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
                      {c.dx ? (
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
                      <EvidenceChipList ids={[...c.cites]} label="Cites" />
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
