# Web viewer: next steps after Phase 1

> Snapshot at 2026-05-07. Phase 1 shipped a Vite + React + TypeScript SPA
> under [`viewer/`](../../viewer/) with the Detail page core (header,
> vitals, key findings, recommendation, four tabs, tweaks panel, export
> menu, `?format=json|md` preflight). Only KAAG1 has a record. This doc
> captures what's deferred and the order I'd build it in.

## What Phase 1 shipped

- `/gene/:symbol` route reads `viewer/public/data/genes/{SYMBOL}.json` and
  validates the `SurfaceomeRecord` schema at the type level (TS mirror in
  [`viewer/src/lib/types.ts`](../../viewer/src/lib/types.ts) of the Pydantic
  model in [models.py](../../src/accessible_surfaceome/tools/_shared/models.py)).
- Detail page: `GeneHeader` + 5-cell vitals strip, `KeyFindings` with
  `HlaAllele`/`Peptide` typed tokens, Recommendation + Modalities, tabs
  (Surface biology / Expression / Therapeutic landscape / Risk flags / Raw
  record), Tweaks panel (density toggle), Export menu (clipboard + download
  MD/JSON, open-raw `?format=md|json`).
- `?format=json|md` preflight intercepts before React mounts and replaces
  the document with a plaintext payload — same contract as the prototype.
- Cite chips render the count + toggle; the inline drill is a stub.
- Cloudflare Pages config: `_redirects` excludes `/data/*` from the SPA
  fallback so missing JSON returns 404, `_headers` long-caches `/fonts/*`
  and short-caches `/data/*`.

## What's deferred, and why

### M2-blocked (waits on annotator output)

- **Stub records for the other ~5,679 genes.** The wide TSV
  [`data/processed/candidate_universe/candidate_universe.tsv`](../../data/processed/candidate_universe/candidate_universe.tsv)
  has enough per-source flag data to render a partial Detail page (header
  identifiers + DB votes tab + a `surface_biology.db_comparison` block). We
  could ship that today, but the rest of the page would render empty cards
  for `targetability`, `expression`, `risk_flags`, etc., which is more
  confusing than a clean "not yet ingested" stub. Deferred until the M2
  annotator produces full `SurfaceomeRecord` JSONs we can drop in.

### M3-blocked (waits on source-corpus persistence)

- **Source drawer with char-offset evidence highlighting.** The prototype's
  `SourceDrawer` slides in from the right, shows the full source body with
  every quote span highlighted, and lets you click any highlight for a
  popover with the claim + back-links to citing buckets. It needs the
  evidence schema — `evidence_id` → `spans[] { source_id, char_offset,
  quote, section }` — which doesn't exist in `data/processed/` yet. The
  M3 source-corpus persistence work in
  [docs/plans/2026-05-06-evidence-provenance-architecture.md](2026-05-06-evidence-provenance-architecture.md)
  unblocks this.
- **Evidence master tab** (filterable by direction / tier / verified-only).
  Same reason.

### Independent (can ship any time)

- **Cmd+K corpus switcher.** Keyboard-triggered palette over a
  build-emitted `corpus.json` manifest, indexed with
  [MiniSearch](https://github.com/lucaong/minisearch) (~7 KB). Symbol /
  alias / indication / modality / tldr search. The prototype's
  `Switcher` component is straightforward to port; the only new piece is
  the manifest format and the Python builder that emits it.
- **Python builder** (`src/accessible_surfaceome/web/build_dataset.py`):
  reads `data/processed/candidate_universe/candidate_universe.tsv` plus
  any per-gene `SurfaceomeRecord` JSONs the annotator has produced, emits
  `viewer/public/data/genes/*.json` and `viewer/public/data/corpus.json`,
  and validates everything against the Pydantic model on its way out.
  CLI hook: `uv run accessible-surfaceome build-web`.
- **CI sync.** GitHub Action: on push to `main`, run the Python builder,
  commit any changes under `viewer/public/data/`, and let Cloudflare Pages
  auto-deploy. Alternative: skip the commit and have the Pages build
  command run the Python pipeline (`uv sync && uv run accessible-surfaceome
  build-web`) before `npm run build` — keeps `viewer/public/data/` out of
  git but makes Pages builds slow + flaky. Prefer the commit path.
- **Cloudflare Pages deployment + custom domain.** Pick a subdomain on the
  existing Deliverome Cloudflare account (e.g. `surfaceome.deliverome.org`
  — confirm before deploy). Build command: `cd viewer && npm ci && npm
  run build`; output: `viewer/dist`; Node 20.
- **Identifier-token style variants.** The prototype offers four
  treatments for HLA alleles + peptides (specimen / inline / underline /
  plate). Phase 1 ships specimen only. Re-add the `data-token-style`
  attribute hook on the root + the variant CSS rules from the prototype's
  [`styles.css`](https://api.anthropic.com/v1/design/h/dCFstrQhWLbJh6rMnHRmKw).
  Low-stakes; do it when designers start asking.

## Order I'd build them

1. **Python builder + KAAG1 round-trip** — even though we ship the seed
   JSON today, codify the round-trip from `SurfaceomeRecord` → JSON file so
   future records have a single emit path and a place to add validation.
2. **Cloudflare Pages deployment.** Get a public URL up so the team can
   actually use the viewer. Doesn't depend on M2/M3.
3. **Cmd+K switcher + corpus.json + MiniSearch.** This is the "good
   search" the user asked about during stack design. Independent of M2/M3
   and high user value.
4. **CI sync** so the deployed viewer reflects whatever `data/processed/`
   currently holds.
5. **Per-gene stubs from the wide TSV.** Once we have a partial-record
   convention (e.g. record with all annotator-only buckets nulled out) and
   the Detail page renders gracefully against it.
6. **Source drawer + Evidence master tab.** When M3 source-corpus
   persistence lands.

## Open questions for the user

- **Domain.** `surfaceome.deliverome.org`? `viewer.surfaceome.deliverome.org`?
  Or stand it up under a different parent domain entirely?
- **Partial-record contract.** When the wide TSV is the only data we have
  for a gene, do we (a) ship a stub that says "not yet ingested" and only
  show identifiers + DB votes, or (b) generate a `SurfaceomeRecord` with
  every annotator-derived field set to `null`/`unknown` and let the Detail
  page render its empty states everywhere? (a) is what Phase 1 does; (b)
  surfaces partial data sooner but bloats the JSON.
- **Stale/retracted source banners.** The prototype's tweaks panel can
  simulate stale source hashes and retraction notices. Keep that as a
  hidden tweaks toggle once the source drawer lands, or surface it as a
  page-level banner whenever the underlying source flags it?
