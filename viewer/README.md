# viewer

Next.js 16 app for the accessible-surfaceome catalogue. Ships as its
own Cloudflare Pages project at
[`surfaceome.deliverome.org`](https://surfaceome.deliverome.org) —
separate domain, separate build, separate deploy target from the main
`deliverome.org` site.

## Stack

- Next.js 16 + React 19, **static export** (`output: "export"`).
- Design tokens mirrored from `Deliverome-Project/deliverome-internal`
  PR #24 (Rosy Maroon: Maroon · Teal · Amber · Lavender; Manrope +
  Playfair Display via `next/font/google`). Source of truth for the
  palette lives in deliverome-internal — re-sync manually when the
  design system rev's.
- PascalCase component dirs with co-located `.module.css`.

## Develop

```bash
cd viewer
npm install
npm run dev      # http://localhost:3000
npm run check    # tsc --noEmit
npm run build    # next build → ./out (static)
```

## Data contract

Per-gene records live under `public/data/surfaceome/{SYMBOL}.json`.
They must validate against the
[`SurfaceomeRecord`](../src/accessible_surfaceome/tools/_shared/models.py)
Pydantic schema. The page bodies read these JSONs via `fs` at build
time and SSG every gene through `generateStaticParams`.

Reference record: `GPR75.json` (orphan class-A GPCR worked
example for the v1.0.0 schema).

Same files double as the static fetch endpoint:
`https://api.deliverome.org/surfaceome/v1/genes/{SYMBOL}` (JSON) and
`https://api.deliverome.org/surfaceome/v1/genes/{SYMBOL}.md` (Markdown). The
`public/data/surfaceome/` copies are build-time inputs, not public URLs.

Agents that prefer the live API hit the read-only Worker:
[`api.deliverome.org/surfaceome/v1/genes/{SYMBOL}`](https://api.deliverome.org/surfaceome/v1/genes)
(Worker source: `cloudflare/workers/surfaceome_api/`, bound to the
public D1 mirror `surfaceome_public`). Same `SurfaceomeRecord` shape.

## Deploy to Cloudflare Pages

This `viewer/` directory is its **own Pages project** — don't mix it
with the deliverome.org site.

- Project: `surfaceome-viewer`
- **Root directory: `viewer/`** (set in the Pages project settings —
  scopes the build to this subtree so Pages does *not* try to
  `pip install` the parent `pyproject.toml`, which adds ~2 min of
  unrelated work to every deploy)
- Build command: `npm ci && npm run build`
- Output directory: `out`
- Custom domain: `surfaceome.deliverome.org`
- Framework preset: Next.js (Static HTML Export)
- Node version: 24 (see `.nvmrc`; `package.json` sets `engines.node: ^24` with `engine-strict`)

`wrangler.toml` records the same target so `npm run deploy` works
locally via Wrangler.

### Gene deep-dive routing (`functions/[[path]].js`)

Per-gene pages (`/TFRC/`, `/A2ML1/`, …) are **one** client-rendered shell
(`app/gene/` → `out/gene/index.html`) — a single static file for all ~5k
genes, so the deployment stays under the Pages 20,000-file cap. A catch-all
Pages Function routes gene URLs to that shell **asset-first**: it serves the
real static asset when one exists (home, `/benchmark/`, `/_next/*` chunks,
`/data/*`), and only falls back to the shell for a genuine gene URL (a single
extension-less path segment requested as a document). Missing assets and
multi-segment dead links keep their real 404 — so a partial deploy fails
visibly instead of white-screening behind the shell.

> Do **not** reintroduce a `_redirects` `/*  /gene/  200` splat for this. A
> working splat matches every directory-style route (home, `/benchmark/`) and
> masks missing `/_next/*` chunks as 200-HTML → the whole site renders the
> stuck shell. That regression is why this is a Function, not a redirect.

### Build gotcha: `build:snapshot` load-sensitivity

`npm run build` runs `scripts/build-data-snapshot.mjs` first, which
pre-fetches all ~5k per-gene records from the live Worker. Every bulk
per-gene fetch the build runs (this script's record pre-fetch, and
`scripts/build-markdown-exports.mjs`'s record + evidence-ledger fetch)
is **paced** through a shared concurrency- and rate-limited scheduler
(`scripts/lib/build-fetch.mjs`) — default 4 concurrent requests, 8
requests/second, overridable via `SURFACEOME_BUILD_FETCH_CONCURRENCY` /
`SURFACEOME_BUILD_FETCH_RPS`. At the defaults the ~5,300-gene record
pre-fetch takes roughly 11 minutes. This exists because an earlier,
unpaced version of the build drove 27k-62k Worker requests per 15 min
(baseline 6-16k) during a Pages build, which pushed cache-miss traffic
onto the shared public D1 hard enough to 500 real users
(2026-09-28 incident).

Every fetch also retries 429/5xx/network errors **and** a 200 response
carrying `X-Surfaceome-Degraded` (the Worker's serve-time enrichment
failed) with exponential backoff, honouring `Retry-After` when the
Worker sends one — a degraded record is retried, never baked into the
static build. A gene whose record or evidence-ledger fetch is still
failing/degraded after retries is **skipped** (no file written, no R2
object touched) and logged; the build **fails the whole run only if
more than `SURFACEOME_BUILD_MAX_FAILED_FRAC` (default 1%, `build-data-
snapshot.mjs` keeps its pre-existing 2% default) of genes failed/skipped
— so one bad gene doesn't break a deploy, but a real Worker/D1 outage
does. So avoid deploying while another job is hammering the same
Worker/D1 (e.g. an R2 `.md` populate); if the threshold trips, just
retry once the Worker is healthy.

## Layout

- `app/` — Next.js App Router (catalogue `/` + client gene shell `app/gene/`,
  served for `/{SYMBOL}/` via `functions/[[path]].js`)
- `app/design-tokens.css` — Rosy Maroon palette mirror
- `app/globals.css` — resets + type primitives
- `components/Shell/` — site shell (header + footer specific to the
  surfaceome subdomain — minimal, no funder strip / nav dropdowns)
- `components/NumberedEyebrow/` — section eyebrow
- `components/Reveal/` — IntersectionObserver fade-in (ported from
  deliverome-internal site/components/reveal.tsx)
- `components/surfaceome/` — record cards (SurfaceBiology, DeepDive,
  Expression, Landscape, RiskFlags) + primitives (StatusPill, FieldRow,
  CiteCount, SectionCard, DBVotes, GeneHeader)
- `lib/surfaceome-types.ts` — TypeScript mirror of the Pydantic schema
- `lib/surfaceome.ts` — fs-backed loader + enum prettifier
