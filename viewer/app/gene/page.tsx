"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell } from "../../components/Shell/Shell";
import { NotFoundNotice } from "../../components/NotFoundNotice/NotFoundNotice";
import { GeneDetail } from "../../components/surfaceome/GeneDetail/GeneDetail";
import { renumberEvidenceIds } from "../../lib/evidenceRenumber";
import {
  loadSchwekeHomomer,
  structureViewerDataFromRecord,
  type SchwekeHomomerLoaderRow,
  type StructureViewerData,
} from "../../lib/structure-viewer-types";
import {
  parseTriageHeadline,
  type TriageHeadlinePayload,
  type TriageRunsPayload,
} from "../../lib/triage-headline";
import { fetchTaggedSites } from "../../lib/tag-sites-client";
import type { TaggedSitesFile } from "../../lib/tag-sites-types";
import type { CatalogRow, GeneEntry } from "../../lib/surfaceome";
import {
  buildGeneJumpEntries,
  type SynonymOverlay,
} from "../../lib/gene-jump-entries";
import {
  parseFgLibrary,
  inFgLibrary as symbolInFgLibrary,
  isOversized as symbolIsOversized,
  oversizedOrfKb as symbolOversizedOrfKb,
  type FgLibraryData,
} from "../../lib/fg-library";
import type {
  BenchmarkRow as BenchmarkRowPayload,
  Evidence,
  SurfaceomeRecord,
} from "../../lib/surfaceome-types";
import styles from "./page.module.css";

/**
 * Client shell for the per-gene deep dive.
 *
 * Under `output: "export"` a `[symbol]` dynamic route forces one static
 * file per gene (via `generateStaticParams`) — at ~5.1k genes that blows
 * Cloudflare Pages' 20k-file cap and nothing deploys. This single static
 * route (`out/gene/index.html`) is served for every `/{SYMBOL}/` URL via
 * `public/_redirects` (`/*  /gene/index.html  200`, URL preserved), reads
 * the symbol from the path, and fetches the record from the Worker at
 * runtime. File count is now independent of gene count.
 */

// Public Worker base the browser talks to. Same Worker the JSON download
// link hardcodes (`/v1/genes/{sym}`) and the same one that already serves
// the feedback + catalog endpoints, so we reuse the existing browser-facing
// `NEXT_PUBLIC_FEEDBACK_API_BASE` override (set for staging previews) with
// the production Worker as the hardcoded default.
const API_BASE = (
  process.env.NEXT_PUBLIC_FEEDBACK_API_BASE ??
  "https://api.deliverome.org/surfaceome"
).replace(/\/+$/, "");

/** `/GPR75/` → `GPR75`. Only a single gene-symbol-shaped segment counts;
 *  multi-segment or odd paths return null (→ not-found state). Mirrors the
 *  loose shape check in NotFoundNotice. The Worker matches case-insensitively
 *  (COLLATE NOCASE), so the segment is passed through as typed. */
function symbolFromPath(pathname: string): string | null {
  const segs = pathname.split("/").filter(Boolean);
  if (segs.length !== 1) return null;
  const seg = decodeURIComponent(segs[0]);
  return /^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$/.test(seg) ? seg : null;
}

async function fetchJson(url: string): Promise<unknown | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Adapt the per-gene `/v1/benchmark/{symbol}` payload (truth label +
 *  rationale) into the `BenchmarkRow` shape the <BenchmarkRow> strip reads.
 *  The endpoint 404s for the ~19k non-benchmark genes (→ null here). The
 *  component only reads `truth_verdict`; the per-DB / per-model matrix
 *  fields (`db`, `verdicts`, `n_db_surface`) aren't on this endpoint, so
 *  they're filled with empty defaults. */
function adaptBenchmarkRow(j: unknown): BenchmarkRowPayload | null {
  const r = j as Record<string, unknown> | null;
  if (!r || typeof r.truth_verdict !== "string") return null;
  return {
    gene_symbol: typeof r.gene_symbol === "string" ? r.gene_symbol : "",
    uniprot_acc: typeof r.uniprot_acc === "string" ? r.uniprot_acc : "",
    class: typeof r.class === "string" ? r.class : "",
    truth_verdict: r.truth_verdict,
    truth_signal: typeof r.truth_signal === "string" ? r.truth_signal : "",
    truth_reason: typeof r.truth_reason === "string" ? r.truth_reason : "",
    db: null,
    n_db_surface: 0,
    verdicts: {},
  };
}

/** Adapt the slim `/v1/catalog/{symbol}` row into the CatalogRow shape
 *  <DatabasePresenceStrip> reads — it only looks at `db.{uniprot,go,surfy,
 *  cspa,hpa} === 1`. The endpoint 404s for genes outside the candidate
 *  universe (→ null → strip omitted). `triage_by_model` is unused by the
 *  strip, so it's left empty. */
function adaptCatalogRow(j: unknown): CatalogRow | null {
  const r = j as Record<string, unknown> | null;
  if (!r || typeof r.db !== "object" || r.db === null) return null;
  const db = r.db as Record<string, unknown>;
  const bit = (v: unknown): number => (v === 1 ? 1 : 0);
  return {
    symbol: typeof r.symbol === "string" ? r.symbol : "",
    uniprot: typeof r.uniprot === "string" ? r.uniprot : "",
    n_sources: typeof r.n_sources === "number" ? r.n_sources : 0,
    db: {
      uniprot: bit(db.uniprot),
      go: bit(db.go),
      surfy: bit(db.surfy),
      cspa: bit(db.cspa),
      hpa: bit(db.hpa),
    },
    triage_by_model: [],
    deep_dive: Boolean(r.deep_dive),
    surface_bind_sites:
      typeof r.surface_bind_sites === "number" ? r.surface_bind_sites : undefined,
    // The /v1/catalog/{sym} endpoint doesn't carry the viewer-side FG-library
    // overlay; the badge/nav/pills read the fetched snapshot separately. Kept
    // false here so this row satisfies the (required) CatalogRow field — the
    // DB-presence strip this row feeds never reads it.
    in_fg_library: false,
    // Same rationale — the DB-presence strip never reads tag-site counts.
    tag_site_counts: null,
  };
}

/** Pull the evidence ledger array out of the `/v1/genes/{sym}/evidence`
 *  payload (`{ gene, evidence: [...] }`). Returns [] for any missing or
 *  malformed shape — including the `fetchJson` null returned on a network /
 *  parse / non-2xx miss — so a bad response degrades to an empty ledger: the
 *  EvidenceLedgerCard resolves its skeleton to "No evidence entries recorded"
 *  rather than hanging, and nothing downstream crashes. */
function evidenceArrayFromPayload(j: unknown): Evidence[] {
  const r = j as { evidence?: unknown } | null;
  return Array.isArray(r?.evidence) ? (r.evidence as Evidence[]) : [];
}

interface ReadyData {
  rec: SurfaceomeRecord;
  geneName: { name: string; synonyms: string[] } | null;
  structureData: StructureViewerData | null;
  taggedSites: TaggedSitesFile | null;
  schwekeHomomer: SchwekeHomomerLoaderRow | null;
  catalogRow: CatalogRow | null;
  benchmarkRow: BenchmarkRowPayload | null;
  triageHeadline: TriageHeadlinePayload | null;
  deepDiveGenes: GeneEntry[];
  /** Parsed FG-library membership overlay (fetched from `/data/fg-library.json`),
   *  or null on a fetch/parse miss. Drives the header "In library" badge, the
   *  prev/next library navigation, and the isoform/ortholog in-library pills. */
  fgLibrary: FgLibraryData | null;
  /** Whether THIS gene's symbol is in the FG library (derived from `fgLibrary`).
   *  Threaded to <GeneHeader> for the badge. */
  inFgLibrary: boolean;
  /** Whether THIS gene is an oversized truncation candidate (clears every gate
   *  but the ~5 kb ORF cap). Threaded to <GeneHeader> for the "Oversized" chip. */
  oversized: boolean;
  /** Full-length ORF size (kb) for an oversized gene, for the chip tooltip. */
  oversizedOrfKb: number | null;
  /** Tedman GPCR canonical surface expression (PME); null for non-GPCRs.
   *  Threaded to <GeneHeader> for the "Low surface" chip. */
  tedmanPme: number | null;
}

type State =
  | { kind: "loading" }
  | { kind: "notfound"; symbol: string | null }
  | { kind: "error"; symbol: string }
  | { kind: "ready"; data: ReadyData };

export default function GeneShellPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    const symbol = symbolFromPath(window.location.pathname);
    if (!symbol) {
      setState({ kind: "notfound", symbol: null });
      return;
    }

    (async () => {
      // ── The record is the only hard requirement: render the page as soon
      // as it arrives, then hydrate the secondary strips progressively so a
      // slow/large secondary never blocks first paint. ──────────────────
      let recRes: Response;
      try {
        recRes = await fetch(`${API_BASE}/v1/genes/${symbol}`);
      } catch {
        if (!cancelled) setState({ kind: "error", symbol });
        return;
      }
      if (recRes.status === 404) {
        if (!cancelled) setState({ kind: "notfound", symbol });
        return;
      }
      if (!recRes.ok) {
        if (!cancelled) setState({ kind: "error", symbol });
        return;
      }
      let rawRec: SurfaceomeRecord;
      try {
        rawRec = (await recRes.json()) as SurfaceomeRecord;
      } catch {
        if (!cancelled) setState({ kind: "error", symbol });
        return;
      }

      // Secondary enrichments — fetched in parallel, each null-tolerant so
      // a miss degrades gracefully rather than failing the page.
      const [
        triageJson,
        benchJson,
        genesJson,
        catalogJson,
        synonymsJson,
        fgLibraryJson,
        taggedSitesResult,
        tedmanSurfaceJson,
      ] = await Promise.all([
        fetchJson(`${API_BASE}/v1/triage/${symbol}`),
        fetchJson(`${API_BASE}/v1/benchmark/${symbol}`),
        fetchJson(`${API_BASE}/v1/genes`),
        fetchJson(`${API_BASE}/v1/catalog/${symbol}`),
        // Build-baked synonym overlay (site origin, not the Worker) so the
        // GeneJump dropdown matches alias queries like "Nav1.7" → SCN9A,
        // the same way the homepage catalog search does.
        fetchJson("/data/gene-synonyms.json"),
        // Committed FG-library membership overlay (same site-origin pattern as
        // the synonym overlay). Drives the "In library" badge, the prev/next
        // library nav, and the isoform/ortholog in-library pills. A miss →
        // null → no badge / nav / pills (graceful).
        fetchJson("/data/fg-library.json"),
        // Static tag-sites asset (Worker-first fetch happens client-side; static fallback + pins).
        fetchTaggedSites(symbol),
        // Tedman GPCR surface-expression overlay (site origin). Drives the
        // "Low surface" chip on library GPCRs (PME ≤ 1000). Miss → no chip.
        fetchJson("/data/tedman-surface.json"),
      ]);
      if (cancelled) return;

      const fgLibrary = fgLibraryJson ? parseFgLibrary(fgLibraryJson) : null;

      // Tedman GPCR canonical surface expression (PME) for this gene, or null
      // when Tedman didn't measure it (non-GPCR). Drives the "Low surface" chip.
      const tedmanSurfacePme =
        tedmanSurfaceJson &&
        typeof tedmanSurfaceJson === "object" &&
        (tedmanSurfaceJson as { pme?: Record<string, number> }).pme
          ? ((tedmanSurfaceJson as { pme: Record<string, number> }).pme[
              symbol
            ] ?? null)
          : null;

      // ── Backward-compatible evidence handling ─────────────────────────
      // The Worker is moving the citation ledger (verbatim quotes +
      // provenance — 42–47% of the payload) OUT of this core response and
      // onto a separate `GET /v1/genes/{sym}/evidence`. Two cases:
      //   * Pre-split Worker: the core response still inlines a non-empty
      //     `evidence` array → use it directly, renumber now, skip the
      //     extra fetch.
      //   * Post-split Worker: `evidence` is absent/empty → render the core
      //     record immediately and lazy-load the ledger just below.
      // `renumberEvidenceIds` rewrites the record's inline `aN_evi_NN` chip
      // tokens against the ledger, so it needs the ledger present: it runs
      // now only in the inline case, and is otherwise DEFERRED to the merge
      // (see the lazy fetch below) so first paint never waits on it.
      const coreHasEvidence =
        Array.isArray(rawRec.evidence) && rawRec.evidence.length > 0;
      // On the lazy path force `evidence` to `undefined` (not `[]`) so the
      // ledger card renders its loading skeleton — rather than a premature
      // "No evidence entries recorded" — until the `/evidence` fetch merges
      // in. Covers a post-split Worker that sends `evidence: []` inline as
      // well as one that omits the field entirely.
      const rec = coreHasEvidence
        ? renumberEvidenceIds(rawRec)
        : { ...rawRec, evidence: undefined };

      // Display name from the record (the build-time NCBI/HGNC gene-name TSV
      // is not client-safe). `protein_name` is only populated for
      // SURFACE-Bind proteins; null → GeneHeader shows the bare symbol.
      const proteinName = rec.deterministic_features.surface_bind.protein_name;

      // First paint: the record plus everything derivable from it AND the
      // eagerly-fetched secondary strips (triage / catalog / benchmark /
      // tag-sites / FG-library). Each is null-tolerant, so a miss degrades to
      // a record-derived fallback; only the evidence ledger is deferred below.
      setState({
        kind: "ready",
        data: {
          rec,
          geneName: proteinName ? { name: proteinName, synonyms: [] } : null,
          structureData: structureViewerDataFromRecord(
            rec.gene.uniprot_acc,
            rec.deterministic_features.canonical_topology,
          ),
          // Static tag-sites asset (public/tag-sites/{SYMBOL}.json), fetched
          // client-side alongside the other enrichments. Null-tolerant: a
          // missing asset simply means no overlay.
          taggedSites: taggedSitesResult,
          schwekeHomomer: loadSchwekeHomomer(
            rec.gene.uniprot_acc,
            rec.deterministic_features.homo_oligomerization,
          ),
          // Slim per-gene DB-vote row from /v1/catalog/{sym} — the 5-DB
          // presence strip. Null-tolerant: 404 for genes outside the
          // candidate universe → strip omitted.
          catalogRow: adaptCatalogRow(catalogJson),
          benchmarkRow: adaptBenchmarkRow(benchJson),
          triageHeadline: triageJson
            ? parseTriageHeadline(triageJson as TriageRunsPayload)
            : null,
          deepDiveGenes: buildGeneJumpEntries(
            genesJson,
            synonymsJson as SynonymOverlay | null,
          ),
          fgLibrary,
          inFgLibrary: symbolInFgLibrary(fgLibrary, symbol),
          oversized: symbolIsOversized(fgLibrary, symbol),
          oversizedOrfKb: symbolOversizedOrfKb(fgLibrary, symbol),
          tedmanPme: tedmanSurfacePme,
        },
      });

      // ── Lazy evidence ledger — off the critical path ──────────────────
      // The citation ledger is the biggest single slice of the record, so
      // when the core response omits it (post-split Worker) it's fetched
      // separately and merged in AFTER first paint. Non-blocking: the page
      // has already rendered above; this only hydrates the evidence-
      // dependent surfaces (EvidenceLedgerCard, ExpressionCard citation
      // chips, EvidenceDrawer). A miss/failure degrades to an empty ledger
      // (fetchJson → null → []) rather than crashing. Skipped entirely when
      // the core record already carried the ledger inline (handled above),
      // so this deploy is safe before OR after the Worker split ships.
      //
      // triage/bench/catalog are NOT lazy-loaded here — they stay in the
      // eager Promise.all above and are already part of the initial
      // `setState` — only the evidence ledger is split off the critical path.
      if (!coreHasEvidence) {
        void (async () => {
          const evJson = await fetchJson(
            `${API_BASE}/v1/genes/${symbol}/evidence`,
          );
          if (cancelled) return;
          const evidence = evidenceArrayFromPayload(evJson);
          setState((prev) =>
            prev.kind === "ready"
              ? {
                  kind: "ready",
                  data: {
                    ...prev.data,
                    // Merge the ledger in and run the deferred renumber NOW
                    // that it's present — it rewrites the record's inline
                    // `aN_evi_NN` chip tokens into the merged `evi_N`
                    // sequence. Setting `evidence` (even to []) also flips
                    // the ledger card out of its loading skeleton.
                    rec: renumberEvidenceIds({ ...prev.data.rec, evidence }),
                  },
                }
              : prev,
          );
        })();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Client-side document title, mirroring the old server generateMetadata.
  // Per-gene SEO prerendering is an accepted non-goal (the page is JS-
  // rendered now); this just keeps browser tabs / bookmarks / history
  // legible once the record resolves.
  useEffect(() => {
    if (state.kind === "ready") {
      document.title = `${state.data.rec.gene.hgnc_symbol} — Surfaceome record`;
    } else if (state.kind === "notfound" && state.symbol) {
      document.title = `${state.symbol} — record not found`;
    }
  }, [state]);

  if (state.kind === "ready") {
    return <GeneDetail {...state.data} />;
  }

  if (state.kind === "notfound") {
    return (
      <Shell>
        <section className={`page-width ${styles.state}`}>
          <NotFoundNotice />
          <p style={{ marginTop: "1.75rem" }}>
            <Link href="/">&larr; Browse the surfaceome catalog</Link>
          </p>
        </section>
      </Shell>
    );
  }

  if (state.kind === "error") {
    return (
      <Shell>
        <section className={`page-width ${styles.state}`}>
          <p className={`label-mono ${styles.stateEyebrow}`}>Couldn&rsquo;t load</p>
          <h1 className="h-display">Something went wrong loading {state.symbol}</h1>
          <p className="lede">
            The record for {state.symbol} couldn&rsquo;t be fetched. This is
            usually a temporary network or service hiccup — try again in a
            moment.
          </p>
          <div className={styles.stateActions}>
            <button
              type="button"
              className={styles.retry}
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Try again
            </button>
            <Link href="/">&larr; Browse the surfaceome catalog</Link>
          </div>
        </section>
      </Shell>
    );
  }

  // Loading — minimal, brand-consistent skeleton mirroring the page shape.
  return (
    <Shell>
      <div className={`page-width ${styles.skeleton}`} aria-busy="true">
        <span className="sr-only">Loading gene record…</span>
        <div className={styles.skelRow}>
          <div className={styles.skelBar} style={{ width: "2rem", height: "1.5rem" }} />
          <div className={styles.skelBar} style={{ width: "12rem", height: "1.5rem" }} />
        </div>
        <div className={styles.skelBar} style={{ width: "min(28rem, 70%)", height: "2.75rem" }} />
        <div className={styles.skelBar} style={{ width: "100%", height: "9rem" }} />
        <div className={styles.skelRow}>
          <div className={styles.skelBar} style={{ width: "6rem", height: "1.75rem" }} />
          <div className={styles.skelBar} style={{ width: "6rem", height: "1.75rem" }} />
          <div className={styles.skelBar} style={{ width: "6rem", height: "1.75rem" }} />
        </div>
        <div className={styles.skelBar} style={{ width: "100%", height: "16rem" }} />
      </div>
    </Shell>
  );
}
