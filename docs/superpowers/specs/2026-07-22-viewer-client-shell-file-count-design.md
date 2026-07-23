# Viewer: decouple deploy file-count from gene count (client-shell gene page)

**Date:** 2026-07-22
**Status:** Design — awaiting review
**Branch:** `claude/viewer-client-shell` (off `main` @ `a5fb5b05d`)

## Problem

The viewer is a fully static Next.js export (`output: "export"`, `trailingSlash: true`) deployed to Cloudflare Pages. It pre-renders one route per deep-dive gene via `generateStaticParams` in `viewer/app/[symbol]/page.tsx`, and `viewer/scripts/build-markdown-exports.mjs` materializes a per-gene `.json` + `.md` into `public/`. At ~5,116 genes the export is **41,140 files**; the `scripts/prune-export.mjs` backstop (added in PR #121) drops the per-gene build-time `.json` but only reaches **36,024**, still far above Cloudflare Pages' hard **20,000-file** per-deployment limit. `wrangler pages deploy` fails asset validation, so **nothing deploys** — the production viewer is stuck on an old build and gene pages (e.g. `/TFRC/`) 404.

The file count is dominated by per-gene artifacts (route HTML + RSC/segment payloads + `.md` + `.json`). Pruning build-time data files cannot fix it: the per-route HTML/RSC alone scales with gene count and blows the cap. This is architectural, not a prune tweak.

## Goal

Make the Pages deploy file count **independent of gene count** so the site deploys and scales, while preserving the gene detail page's content, the pretty `/{SYMBOL}/` URLs, and both (JSON + rich Markdown) downloads.

## Non-goals

- No change to the data pipeline, D1 schema, or the record contents.
- No change to any page other than the per-gene detail page (home/catalog, benchmark, compare, prompts, api, reproducibility, homomer-demo stay server-static and untouched).
- Not pursuing full SSR (`@cloudflare/next-on-pages`) — explicitly rejected below.
- Not building per-gene SEO prerendering now (possible future follow-up).

## Decisions (resolved with the maintainer)

1. **Render model: client-rendered shell (Approach A).** Only the per-gene detail page moves to in-browser rendering. Rejected: full SSR via next-on-pages (bigger migration; `loadGeneName`'s `readFileSync` of repo TSVs breaks on the Workers runtime; per-request edge CPU) and the hybrid prerender-core (two rendering paths to maintain). A is the lowest-risk, most durable option and stays on static Pages hosting; it is upgradeable to hybrid later without rework.
2. **`.md` download: keep it rich, serve from R2.** The `.md` bundles content not in the record JSON (AFDB isoform/ortholog sequences, DeepTMHMM topology). Generate it at pipeline time, store in R2, serve via a new Worker route. Rejected: dropping it (loses real content) and Worker-generates-from-D1 (D1 lacks the AFDB/topology extras).

Accepted trade-off: gene pages become JS-dependent — Google still indexes rendered JS, but server-side previews / non-Google crawlers / social link-cards degrade. Acceptable for a niche scientific tool where most discovery is direct links / the paper / internal use.

## Architecture

Three coordinated pieces. The viewer piece is what unblocks the deploy; the R2/Worker piece keeps the `.md` download alive.

### 1. Viewer — gene detail page becomes a client shell

- **Remove the `[symbol]` dynamic route.** Under `output: "export"`, a dynamic segment requires `generateStaticParams` to enumerate every param — that is exactly the per-gene explosion. Delete `viewer/app/[symbol]/` (page + its `page.module.css` moves with the shell).
- **Add one static shell route** at `viewer/app/gene/page.tsx` → emits a single `out/gene/index.html`. It is a client component (`"use client"`) that:
  - reads the symbol from `window.location.pathname` (the URL stays `/{SYMBOL}/`; see `_redirects`),
  - fetches the record from the Worker: `GET ${SURFACEOME_API_BASE}/v1/genes/{symbol}` (default `https://api.deliverome.org/surfaceome`), which is already edge-cached (PR #119),
  - renders a loading skeleton while fetching, the full page on success, and a not-found state on 404.
- **`viewer/public/_redirects`** (new): `/*  /gene/index.html  200`. Cloudflare Pages serves an exact static asset first and only falls through to `_redirects` when none matches — so `/benchmark/`, `/_next/*`, `/data/*`, `/sitemap.xml`, etc. still resolve to their own files; only unmatched paths like `/TFRC/` rewrite (200, URL preserved) to the shell. Existing bookmarks, inbound links, and the sitemap keep working.
- **Flip the record-rendering section cards to client components.** The ~10 currently-server presentational cards under `viewer/components/surfaceome/*` take a plain `rec` prop and do no server-only work; add `"use client"` where needed and confirm none import `node:fs`/build-only modules. The 3 already-client cards (`CommunityNotesCard`, `EvidenceDrawer`, `EvidenceClickDelegator`) are unchanged. Chrome (`SectionTabs`, `Reveal`, `GeneJump`, `FeedbackModal`) is already client.
- **Display name:** use the record's `deterministic_features.surface_bind.protein_name` (already in the payload). The build-time gene-name TSV (`loadGeneName`) is **not** needed on the detail page. The still-static catalog/home keeps its current build-time name handling — no gene-name-map work required.
- **Downloads on the shell toolbar:** JSON link already points at the Worker (`/v1/genes/{SYM}`) — unchanged. Markdown link repoints from `/data/surfaceome/{SYM}.md` → `${API_BASE}/v1/genes/{SYM}.md` (see piece 3).
- **CORS requirement (must verify/add):** the in-browser `fetch('/v1/genes/{symbol}')` is cross-origin (`surfaceome.deliverome.org` → `api.deliverome.org`), so the Worker must return `Access-Control-Allow-Origin` (site origin or `*`) on `/v1/genes/*` (and `/v1/genes/*.md`). Verify current behavior; add if missing. This is the one thing that will silently break the page if overlooked.

### 2. Stop emitting per-gene files at Pages-build time

- `build-markdown-exports.mjs` no longer runs as part of `npm run build` and no longer writes `public/data/surfaceome/{SYM}.{json,md}`. Per-gene static `.json` is dropped entirely (the record comes from the Worker). Its markdown role moves to the standalone R2 job (piece 3).
- Removing the AFDB/DeepTMHMM fetch loop from the Pages build is a side benefit: faster, more reliable Pages builds.
- **Keep `scripts/prune-export.mjs` as a backstop** (fail the build if `out/` ≥ 20,000). After this change `out/` is `O(static routes)` — ~14 routes + `_next` + sitemap/robots + a few committed sample/data files, i.e. low hundreds to low thousands, permanently independent of gene count. The guard should essentially never fire again; keeping it is cheap insurance.
- Committed sample files under `public/data/surfaceome/` (3 genes) and `public/structure-viewer/` (2 accessions) may remain as-is (negligible) or be removed; either is fine.

### 3. Rich `.md` → R2, served by the Worker

- **Repurpose `build-markdown-exports.mjs` into a standalone job** (run in CI when the gene set changes, **not** in the Pages build). It generates each rich `.md` exactly as today (fetching AFDB sequences + DeepTMHMM topology) and **uploads to R2** instead of writing `public/`. This decouples `.md` generation from both the Pages build and the gene count.
- **Worker:** add an R2 binding and a route `GET /v1/genes/{symbol}.md` that streams the object from R2 with `Content-Type: text/markdown`, cache headers, and CORS. Lives in `cloudflare/workers/surfaceome_api/src/index.js` (+ `wrangler.toml` binding).
- **Credentials:** the existing `CLOUDFLARE_API_TOKEN` in `.env` is R2/D1-scoped (per prior work it authorizes R2, and errors only on the Pages API), so the R2 upload is feasible with current credentials. Confirm the target bucket name/account during implementation.

## Data flow (gene page)

```
Browser → GET /TFRC/  (Cloudflare Pages)
  └─ no static asset matches → _redirects `/* → /gene/index.html 200`
       └─ shell JS reads "TFRC" from path
            ├─ fetch https://api.deliverome.org/surfaceome/v1/genes/TFRC  (D1, edge-cached)  → render
            └─ 404 → not-found state
Downloads:  JSON → /v1/genes/TFRC        (Worker/D1)
            Markdown → /v1/genes/TFRC.md  (Worker → R2)
```

## Why the file count works (independent of gene count)

Removing the `[symbol]` route eliminates **all** per-gene route artifacts (HTML + RSC/segment payloads + any per-route emission), regardless of the exact per-gene multiplier that produced 41,140 files. Combined with dropping per-gene `.json`/`.md` from `public/`, the deployment's file set reduces to the fixed static routes + shared `_next` bundle + sitemap/robots. Adding genes no longer adds files. The 20k cap is no longer reachable by growing the cohort.

## Error handling

- **Unknown / mistyped symbol:** shell fetch → Worker 404 → render a clear not-found state (offer link back to catalog). The `/*` fallback intentionally serves the shell for any unmatched path; the shell owns the 404 UX.
- **Worker/API unreachable or 5xx:** shell renders an error state with a retry affordance (record fetch failed), not a blank page.
- **`.md` missing in R2:** Worker route returns 404; the download link surfaces it as a normal failed download. The generation job should log/verify coverage.
- **CORS misconfig:** covered by the explicit verify-CORS step; add an integration check.
- **Offline CI build (`SURFACEOME_API_BASE=local`):** no gene enumeration is needed anymore — the offline build just emits the shell + static pages. Simpler than today's sentinel-param path.

## Testing

- **Existing card render-tests** (`viewer/tests/*.test.tsx`, react-dom/server) still pass — cards stay presentational; adjust imports only if a card's module path moves.
- **Shell:** add a render test that mounts the shell against a mocked record fetch (success → key sections present) and a mocked 404 (→ not-found state).
- **Worker `.md` route:** add a test hitting the new route against an R2 stub (hit → `text/markdown` body + CORS header; miss → 404).
- **CORS:** assert `Access-Control-Allow-Origin` on `/v1/genes/*` and `/v1/genes/*.md` responses.
- **Routing (`_redirects`):** Cloudflare Pages routing can't be unit-tested; document a manual preview-deploy check — `/{SYM}/` renders, `/benchmark/` still serves its own page, `/_next/*` and `/data/*` unaffected, unknown `/ZZZ/` shows not-found.
- **Backstop:** keep the `out/`-count assertion in `prune-export.mjs`.

## Rollout / sequencing (ordered so nothing ships broken)

1. **R2 + Worker `.md` first:** run the standalone job to populate R2; add + deploy the Worker `/v1/genes/{sym}.md` route (and confirm CORS on `/v1/genes/*`). Verify `curl …/v1/genes/TFRC.md` returns the rich markdown.
2. **Then the viewer PR:** shell + `_redirects` + remove `[symbol]` + drop per-gene emission from `build` + repoint the `.md` link. This PR is what clears the 20k cap and unblocks the Pages deploy.
3. Merge → Cloudflare Pages Git integration deploys automatically. Verify `/TFRC/` and `/EGFR/` render live and both downloads work.

(If it's cleaner to land as one PR, keep the same internal order — R2/Worker changes must be live before the viewer relies on the `.md` route and the record fetch.)

## Risks / open questions (resolve during implementation)

- **Worker CORS** on the record + `.md` endpoints — verify first; highest-risk silent failure.
- **R2 bucket** name/account + that `CLOUDFLARE_API_TOKEN` can write it — confirm.
- **Where the `.md`→R2 job runs** — new GH Actions workflow, manual/dispatch or on gene-set change; define trigger.
- **Catalog/home → gene links** must use `/{SYM}/` (relative) so the `_redirects` fallback catches them — verify no link depends on a prerendered `[symbol]` asset.
- **Loading skeleton** design for the brief fetch window — keep minimal, brand-consistent.
- **SEO** — sitemap still lists gene URLs (Google renders JS). Accepted; revisit with a prerender-core follow-up if organic search traffic proves to matter.

## Out of scope (tracked elsewhere)

- Evidence-grade false-negative re-grade (`task_003f93ac`), isoform-AFDB metric backfill (`task_9ae78237`), the `PMC:` citation-title display bug, and the `sharp`/`libvips` `npm audit` gate in `viewer build check` (a GH-Actions concern, independent of the Pages deploy).
