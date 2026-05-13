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

Reference records: `HSPA1A.json` (conditional-surface stress-induced),
`TGOLN2.json`.

Same files double as the static fetch endpoint:
`https://surfaceome.deliverome.org/data/surfaceome/{SYMBOL}.json`.

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
- Node version: 20

`wrangler.toml` records the same target so `npm run deploy` works
locally via Wrangler.

## Layout

- `app/` — Next.js App Router (catalogue `/` + gene detail `/[symbol]/`)
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
