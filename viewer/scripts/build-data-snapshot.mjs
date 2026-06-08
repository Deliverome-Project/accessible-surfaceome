#!/usr/bin/env node
/**
 * Pre-fetch the over-2MB Worker endpoints to disk so SSG can read them
 * from filesystem rather than refetching per-worker per-page.
 *
 * ## What this fixes
 *
 * Next.js's Data Cache rejects fetched responses larger than 2MB. Two of
 * our Worker endpoints exceed that cap and keep growing:
 *
 *   /v1/catalog            ~5.7 MB  (genome-wide catalog)
 *   /v1/benchmark/matrix   ~3.0 MB  (147 × per-DB × per-model)
 *
 * Each SSG worker that calls them gets a Data-Cache miss, refetches from
 * the Worker, and the build log fills with "Failed to set Next.js data
 * cache, items over 2MB can not be cached". On a recent build that was
 * ~15 identical fetches against a single endpoint — costing build wall
 * time AND hammering D1 every deploy.
 *
 * Pre-fetching at build start gives us:
 *   1) one fetch per endpoint per build
 *   2) deterministic build inputs (no race against a Worker that's
 *      mid-write)
 *   3) zero Data-Cache warnings in the build log
 *
 * ## What this script does
 *
 * - Reads SURFACEOME_API_BASE the same way the runtime loaders do.
 * - Fetches /v1/catalog + /v1/benchmark/matrix.
 * - Writes them to `viewer/build-cache/{catalog,benchmark-matrix}.json`
 *   (gitignored — these are derived artifacts).
 * - Exits 0 (with a no-op) when API_BASE is `local` or empty so the
 *   smoke build still works without network.
 *
 * The runtime loaders in `viewer/lib/surfaceome.ts` look at the
 * build-cache directory first via `readBuildCache()`, then fall back to
 * a live fetch if the file is missing — so a contributor running
 * `next dev` without first running the snapshot still gets data.
 *
 * Wired into `package.json` BEFORE `next build`:
 *
 *   "build": "npm run build:exports && npm run build:snapshot && next build --webpack"
 */
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const API_BASE = process.env.SURFACEOME_API_BASE
  || "https://api.deliverome.org/surfaceome";

const CACHE_DIR = path.resolve("build-cache");

const ENDPOINTS = [
  { endpoint: "/v1/catalog", file: "catalog.json" },
  { endpoint: "/v1/benchmark/matrix", file: "benchmark-matrix.json" },
];

function fmtMB(bytes) {
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

async function snapshot() {
  if (!API_BASE || API_BASE === "local") {
    console.log(
      `[snapshot] SURFACEOME_API_BASE=${API_BASE || "<empty>"} — skipping ` +
        `pre-fetch (runtime loaders will return empty stubs).`,
    );
    return;
  }

  await mkdir(CACHE_DIR, { recursive: true });

  for (const { endpoint, file } of ENDPOINTS) {
    const url = `${API_BASE}${endpoint}`;
    const t0 = performance.now();
    console.log(`[snapshot] fetching ${url}`);
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      console.error(`[snapshot] ${endpoint} → fetch failed: ${e.message}`);
      process.exit(1);
    }
    if (!res.ok) {
      console.error(`[snapshot] ${endpoint} → HTTP ${res.status}`);
      process.exit(1);
    }
    const body = await res.text();
    const out = path.join(CACHE_DIR, file);
    await writeFile(out, body);
    const dt = Math.round(performance.now() - t0);
    console.log(`  wrote ${out} (${fmtMB(body.length)}, ${dt} ms)`);
  }
}

await snapshot();
