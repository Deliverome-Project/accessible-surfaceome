# viewer

Web app for the accessible-surfaceome catalogue. Vite + React + TypeScript SPA.
Deploys as static assets to Cloudflare Pages — no Functions, no D1.

## Develop

```bash
cd viewer
npm install
npm run dev    # http://localhost:5173
```

Visit `/gene/KAAG1` to see the seed record. Other gene URLs render a
"record not yet ingested" stub until the M2 annotation pipeline produces
per-gene `SurfaceomeRecord` JSONs.

## Build

```bash
npm run build  # tsc -b && vite build → viewer/dist
```

## Data contract

Per-gene records live under `public/data/genes/{SYMBOL}.json` and must validate
against the [`SurfaceomeRecord`](../src/accessible_surfaceome/tools/_shared/models.py)
Pydantic schema. The seed `KAAG1.json` was extracted from the Claude Design
prototype's `data/kaag1.js`; future records will be emitted by a Python builder
(deferred).

Agent / curl access:
- `/data/genes/{SYMBOL}.json` — direct static URL.
- `/gene/{SYMBOL}?format=json` — preflight intercepts before React mounts and
  renders the JSON as plaintext.
- `/gene/{SYMBOL}?format=md` — same, rendered as Markdown.

## Deploy to Cloudflare Pages

- Build command: `cd viewer && npm ci && npm run build`
- Output directory: `viewer/dist`
- Framework preset: None (Vite static)
- Node version: 20
- `public/_redirects` rewrites all unknown paths to `index.html` so the SPA
  router owns `/gene/:symbol`.
- `public/_headers` sets long-cache for `/fonts/*`, short-cache for `/data/*`.

## Out of scope (future PRs)

- Cmd+K corpus switcher with client-side `MiniSearch` over a `corpus.json`
  manifest.
- Source drawer with char-offset evidence highlighting (waits on M3 source
  corpus persistence).
- Stub records hydrated from `data/processed/candidate_universe/candidate_universe.tsv`.
- Python builder + CI sync from `data/processed/` to `viewer/public/data/`.
