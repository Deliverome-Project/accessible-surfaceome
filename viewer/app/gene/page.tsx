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
import type { CatalogRow, GeneEntry } from "../../lib/surfaceome";
import type {
  BenchmarkRow as BenchmarkRowPayload,
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

/** Map the `/v1/genes` index to the GeneJump typeahead set. Every deep-dive
 *  gene now loads through this shell, so the whole set is offered (the old
 *  page filtered to non-stale entries only because a non-generated symbol
 *  would 404 under `output: export` — no longer a constraint). `stale` isn't
 *  computed client-side; the freshness dot is off on the gene page anyway. */
function genesToEntries(j: unknown): GeneEntry[] {
  const data = j as { genes?: Array<{ gene_symbol?: string }> } | null;
  const out: GeneEntry[] = [];
  for (const g of data?.genes ?? []) {
    if (g.gene_symbol) out.push({ symbol: g.gene_symbol, stale: false });
  }
  return out;
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
  };
}

interface ReadyData {
  rec: SurfaceomeRecord;
  geneName: { name: string; synonyms: string[] } | null;
  structureData: StructureViewerData | null;
  schwekeHomomer: SchwekeHomomerLoaderRow | null;
  catalogRow: CatalogRow | null;
  benchmarkRow: BenchmarkRowPayload | null;
  triageHeadline: TriageHeadlinePayload | null;
  deepDiveGenes: GeneEntry[];
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

    (async () => {
      const symbol = symbolFromPath(window.location.pathname);
      if (!symbol) {
        if (!cancelled) setState({ kind: "notfound", symbol: null });
        return;
      }

      // The record is the only hard requirement.
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
      const [triageJson, benchJson, genesJson, catalogJson] = await Promise.all([
        fetchJson(`${API_BASE}/v1/triage/${symbol}`),
        fetchJson(`${API_BASE}/v1/benchmark/${symbol}`),
        fetchJson(`${API_BASE}/v1/genes`),
        fetchJson(`${API_BASE}/v1/catalog/${symbol}`),
      ]);
      if (cancelled) return;

      // Renumber the merged evidence ledger's ids client-side, exactly as
      // the old server loader (`loadSurfaceomeRecord`) did — chip ids
      // collide across the per-section blocks otherwise.
      const rec = renumberEvidenceIds(rawRec);

      // Display name from the record (the build-time NCBI/HGNC gene-name TSV
      // is not client-safe). `protein_name` is only populated for
      // SURFACE-Bind proteins; null → GeneHeader shows the bare symbol.
      const proteinName = rec.deterministic_features.surface_bind.protein_name;

      setState({
        kind: "ready",
        data: {
          rec,
          geneName: proteinName ? { name: proteinName, synonyms: [] } : null,
          structureData: structureViewerDataFromRecord(
            rec.gene.uniprot_acc,
            rec.deterministic_features.canonical_topology,
          ),
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
          deepDiveGenes: genesToEntries(genesJson),
        },
      });
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
