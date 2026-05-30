import type { Metadata } from "next";
import { Shell } from "../../components/Shell/Shell";
import { CompareTool } from "../../components/CompareTool/CompareTool";
import {
  loadCatalog,
  loadSurfaceomeRecord,
  type CatalogRow,
  type DeepDiveFilters,
} from "../../lib/surfaceome";
import { pickDeepDiveFilters } from "../../lib/deep-dive-fields";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Compare a protein list — Surfaceome",
  description:
    "Paste or upload a list of gene symbols / UniProt accessions and " +
    "compare each against the five source databases, the triage call, and " +
    "the deep-dive filters — with set-level enrichment.",
};

/**
 * /compare/ — bring-your-own-list tool. Bakes the same genome-wide
 * catalog the index page uses (`loadCatalog()` is memoized, so the
 * second SSG call is free) and hands the rows to a client component
 * that resolves a pasted / uploaded protein list against them entirely
 * in-browser. Nothing about the user's list is sent to a server.
 */
export default async function ComparePage() {
  const catalog = await loadCatalog();

  // The deployed public Worker doesn't ship the catalog `ddf` field, so
  // catalog rows arrive without deep_dive_filters and the deep-dive
  // enrichment would never render. Rebuild it here at build time: every
  // deep-dived gene has a D1 record whose `filters` block carries the
  // same field names. (n_with_deep_dive is small — 6 today — so these
  // reads are cheap; loadSurfaceomeRecord fetches each from the Worker,
  // deduped within the build via `cache: "force-cache"`.)
  const ddSymbols = catalog.rows
    .filter((r) => r.deep_dive)
    .map((r) => r.symbol);
  const ddRecords = await Promise.all(
    ddSymbols.map((s) => loadSurfaceomeRecord(s)),
  );
  const ddfBySymbol = new Map<string, DeepDiveFilters>();
  ddSymbols.forEach((sym, i) => {
    const ddf = pickDeepDiveFilters(
      ddRecords[i]?.filters as Record<string, unknown> | undefined,
    );
    // The projection is a partial DeepDiveFilters (older records omit some
    // fields); the enrichment reads every field via optional access, so a
    // partial is safe. Route the cast through `unknown`.
    if (ddf) ddfBySymbol.set(sym, ddf as unknown as DeepDiveFilters);
  });
  const rows: CatalogRow[] = ddfBySymbol.size
    ? catalog.rows.map((r) =>
        r.deep_dive && ddfBySymbol.has(r.symbol)
          ? { ...r, deep_dive_filters: ddfBySymbol.get(r.symbol) }
          : r,
      )
    : catalog.rows;

  return (
    <Shell>
      <section className={`${styles.page} page-width`}>
        <header className={styles.head}>
          <h1 className={`h-data ${styles.title}`}>Compare a protein list</h1>
          <p className={styles.lede}>
            Paste or upload a list of gene symbols or UniProt accessions to
            see how each scores across the five source databases (UniProt,
            GO, SURFY, CSPA, HPA), the triage agent&rsquo;s surface call, and
            — where a deep-dive record exists — the full filter set. A summary
            panel reports which signals are enriched in your list relative to
            the whole catalog. The list is matched in your browser; nothing is
            uploaded.
          </p>
        </header>

        <CompareTool
          rows={rows}
          nRows={catalog.n_rows}
          nWithDeepDive={catalog.n_with_deep_dive}
        />
      </section>
    </Shell>
  );
}
