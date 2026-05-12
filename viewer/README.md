# viewer

Web app for the accessible-surfaceome catalogue. Vite + React + TypeScript SPA.
Deploys as static assets to Cloudflare Pages.

## Develop

```bash
cd viewer
npm install
npm run dev    # http://localhost:5173
```

Reference records currently published:

- `/gene/HSPA1A` — conditional-surface stress test (cell_state_stress +
  immunogenic_cell_death + oncogenic_state)
- `/gene/TGOLN2` — trafficking-cycling test (TGN ↔ PM)

Other gene URLs render a "record not yet ingested" stub until the agent
produces a `SurfaceomeRecord` v0.4.0 JSON for that gene.

## Build

```bash
npm run build  # tsc -b && vite build → viewer/dist
```

## Data contract

Two paths into the same data, depending on deployment phase:

### Phase 1 — static JSON (today)

Per-gene records live under `public/data/genes/{SYMBOL}.json` and must
validate against the
[`SurfaceomeRecord`](../src/accessible_surfaceome/tools/_shared/models.py)
Pydantic schema (`SCHEMA_VERSION = "v0.4.0"`). The committed snapshots
are produced by `accessible-surfaceome agents annotate <gene>` and
hand-copied into `viewer/public/data/genes/`.

Agent / curl access:

- `/data/genes/{SYMBOL}.json` — direct static URL.
- `/gene/{SYMBOL}?format=json` — preflight intercepts before React mounts
  and renders the JSON as plaintext.
- `/gene/{SYMBOL}?format=md` — same, rendered as Markdown.

### Phase 2 — public Worker API (planned)

The viewer will read from the `surfaceome_public` D1 mirror via the
read-only Cloudflare Worker at `cloudflare/workers/surfaceome_api/`.
Endpoints:

```
GET /v1/genes/:symbol            — full SurfaceomeRecord
GET /v1/orthologs/:symbol        — mouse + cyno orthologs
GET /v1/benchmark[/{symbol}]     — curated truth labels
GET /v1/triage/:symbol           — per-call triage verdicts
```

Public URL target: `api.deliverome.org/surfaceome/*` (custom domain on
the Worker once the apex zone is configured). The static-JSON path stays
as a CDN-cached fallback.

## Deploy to Cloudflare Pages

This `viewer/` directory builds as a standalone Pages project at
`surfaceome.deliverome.org`:

- Cloudflare Pages → new project → connect this GitHub repo
- Project name: `surfaceome-viewer`
- Build command: `cd viewer && npm ci && npm run build`
- Output directory: `viewer/dist`
- Framework preset: None (Vite static)
- Node version: 20
- Custom domain: `surfaceome.deliverome.org`

The main `deliverome.org` site links to this subdomain from a "Surfaceome"
nav item / data tab — no shared codebase needed.

- `public/_redirects` rewrites all unknown paths to `index.html` so the
  SPA router owns `/gene/:symbol`.
- `public/_headers` sets long-cache for `/fonts/*`, short-cache for
  `/data/*`.

## Out of scope (future PRs)

- Cmd+K corpus switcher with client-side `MiniSearch` over a
  `corpus.json` manifest.
- Source drawer with char-offset evidence highlighting from the
  persisted `Evidence.spans[i].char_offset`.
- Stub records hydrated from
  `data/processed/candidate_universe/candidate_universe.tsv` so every
  candidate has a "not yet annotated" page.
- Worker-API integration (Phase 2) — flip the data fetcher from
  `/data/genes/...` to `/v1/genes/...` against `surfaceome.api.deliverome.org`.
