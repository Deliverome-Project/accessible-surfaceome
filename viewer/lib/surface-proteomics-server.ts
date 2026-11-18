/**
 * Build-time (Node) reads of the committed surface-proteomics data, for
 * server components that bake a per-protein count into a page.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import {
  baseAccession,
  countingRule,
  isCounted,
  type PresenceShard,
  type StudyIndex,
} from "./surface-proteomics";
import type { CatalogRow } from "./surfaceome";

const DIR = path.join(process.cwd(), "public", "data", "surface-proteomics");

/** Base accession → number of counted datasets detecting it (only > 0). */
export function countedByAccession(): Map<string, number> {
  const out = new Map<string, number>();
  const indexPath = path.join(DIR, "studies.json");
  if (!existsSync(indexPath)) return out;
  const index = JSON.parse(readFileSync(indexPath, "utf8")) as StudyIndex;
  const counted = new Set(index.arms.flatMap((a, i) => (isCounted(a) ? [i] : [])));
  for (let i = 0; i < index.n_shards; i++) {
    const shard = JSON.parse(
      readFileSync(path.join(DIR, "presence", `${String(i).padStart(2, "0")}.json`), "utf8"),
    ) as PresenceShard;
    for (const [acc, e] of Object.entries(shard)) {
      const n = e.a.filter((j) => counted.has(j)).length;
      if (n) out.set(acc, n);
    }
  }
  return out;
}

/**
 * Counted datasets, papers and distinct proteins under one counting rule:
 * baseline only (the default) or with the opt-in other conditions. Read
 * from the committed presence shards so the page's headline agrees with
 * what the study table shows under the same switch.
 */
export function countedTotals(includeOther: boolean): {
  datasets: number;
  papers: number;
  proteins: number;
} {
  const indexPath = path.join(DIR, "studies.json");
  if (!existsSync(indexPath)) return { datasets: 0, papers: 0, proteins: 0 };
  const index = JSON.parse(readFileSync(indexPath, "utf8")) as StudyIndex;
  const counts = countingRule(index.arms, includeOther);
  const counted = new Set(index.arms.flatMap((a, i) => (counts(a) ? [i] : [])));
  let proteins = 0;
  for (let i = 0; i < index.n_shards; i++) {
    const shard = JSON.parse(
      readFileSync(path.join(DIR, "presence", `${String(i).padStart(2, "0")}.json`), "utf8"),
    ) as PresenceShard;
    for (const e of Object.values(shard)) if (e.a.some((j) => counted.has(j))) proteins++;
  }
  return {
    datasets: counted.size,
    papers: new Set([...counted].map((i) => index.arms[i].publication)).size,
    proteins,
  };
}

/** Number of counted datasets, for column headers and tooltips. */
export function nCountedDatasets(): number {
  const indexPath = path.join(DIR, "studies.json");
  if (!existsSync(indexPath)) return 0;
  return (JSON.parse(readFileSync(indexPath, "utf8")) as StudyIndex).n_admitted_arms;
}

/** Attach `sp_counted` to catalog rows, joined on base UniProt accession. */
export function withProteomicsCounts(rows: CatalogRow[]): CatalogRow[] {
  const counts = countedByAccession();
  return rows.map((r) => {
    const n = r.uniprot ? counts.get(baseAccession(r.uniprot)) : undefined;
    return n ? { ...r, sp_counted: n } : r;
  });
}
