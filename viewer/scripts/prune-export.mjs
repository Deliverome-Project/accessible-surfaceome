/*
 * Post-export prune — keep the Pages deployment under Cloudflare's hard
 * 20,000-file-per-deployment limit.
 * ------------------------------------------------------------
 * `next build` (output: "export") copies everything under `public/` into
 * `out/`. At ~5,130 genes the build materializes, per gene, BOTH a
 * `data/surfaceome/{SYM}.json` snapshot AND a `{SYM}.md` export, on top of
 * the ~5,143 per-route `index.html` files. That pushes `out/` over 20,000
 * files and the `wrangler pages deploy` asset-validation step hard-fails:
 *
 *   ✘ Error: Pages only supports up to 20,000 files in a deployment.
 *
 * The per-gene `.json` snapshots are NOT referenced by the shipped site:
 *   - `loadSurfaceomeRecord` reads them only as a BUILD-TIME fs-fallback
 *     (via `process.cwd()/public/...`), and the built pages are fully
 *     pre-rendered SSG HTML — the snapshot is already baked in.
 *   - No client/runtime code fetches `/data/surfaceome/{sym}.json`
 *     (grep-verified); the live site reads from the Worker/D1 API.
 * The per-gene `.md` files ARE user-facing downloads (linked from the gene
 * page at `/data/surfaceome/{sym}.md`) and are KEPT.
 *
 * The `structure-viewer/{UNIPROT}.json` files are likewise consumed only at
 * SSG time by `loadStructureViewerData` (baked into the page); the HTTP path
 * is documented as "for any future client-side loaders" and nothing fetches
 * it at runtime today. They're pruned too for headroom as the cohort grows.
 *
 * Net effect: every HTML page and every `.md` download still ships; only the
 * build-time-only JSON is dropped from the deployment.
 */

import { readdirSync, rmSync, statSync } from "node:fs";
import path from "node:path";

const OUT = path.join(process.cwd(), "out");
const HARD_LIMIT = 20000;

function countFiles(dir) {
  let n = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) n += countFiles(p);
    else n += 1;
  }
  return n;
}

/** Remove every `*.json` directly inside `out/<rel>` (non-recursive by
 *  design — these are flat per-key directories). Returns count removed. */
function pruneJson(rel) {
  const dir = path.join(OUT, rel);
  let removed = 0;
  try {
    for (const name of readdirSync(dir)) {
      if (name.endsWith(".json")) {
        rmSync(path.join(dir, name));
        removed += 1;
      }
    }
  } catch (err) {
    if (err.code !== "ENOENT") throw err;
  }
  return removed;
}

try {
  statSync(OUT);
} catch {
  console.error(`[prune-export] no out/ directory at ${OUT} — did next build run?`);
  process.exit(1);
}

const before = countFiles(OUT);
const removedRecords = pruneJson("data/surfaceome"); // keeps the .md downloads
const removedStructure = pruneJson("structure-viewer");
const after = countFiles(OUT);

console.log(
  `[prune-export] removed ${removedRecords} data/surfaceome/*.json + ` +
    `${removedStructure} structure-viewer/*.json ` +
    `(build-time-only, unreferenced at runtime).`,
);
console.log(
  `[prune-export] out/ file count: ${before} → ${after} (limit ${HARD_LIMIT}).`,
);

if (after >= HARD_LIMIT) {
  console.error(
    `[prune-export] WARNING: out/ still has ${after} files (>= ${HARD_LIMIT}). ` +
      `The Cloudflare Pages deploy will fail asset validation. Prune more ` +
      `(e.g. consolidate per-gene .md, or serve them from the Worker).`,
  );
  process.exit(1);
}
