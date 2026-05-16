# accessible-surfaceome

A `uv` project that builds an annotated catalogue of human cell-surface
proteins **accessible to therapeutic targeting, agnostic to therapeutic
modality.** Full design notes:
[docs/plans/2026-04-16-surface-proteome-annotation.md](docs/plans/2026-04-16-surface-proteome-annotation.md).

The headline call per protein is *accessibility* — physical surface
localization, extracellular-face exposure, and any conditional/induced
surface presentation (cell-state induced, tissue subset, trafficking
cycling). The project shipped MIT-licensed; copyright Michael Smallegan
and Rebecca Carlson.

## What's in here

The project has three production layers, all in this repo:

1. **M1 candidate universe** — seven-source merge (SURFY, CSPA, UniProt,
   GO, HPA, DeepTMHMM, COMPARTMENTS) into a per-protein vote panel.
   `src/accessible_surfaceome/sources/` + `merge/`.
2. **Surface triage agent** — lightweight per-protein verdict
   (`yes`/`contextual`/`no`) with confidence + key_uncertainty. Pure-model
   inference, no tools. `src/accessible_surfaceome/agents/surface_triage/`.
3. **Surface annotator agent (deep dive)** — per-protein
   `SurfaceomeRecord` v0.5.0 with surface_biology (+ membrane
   microdomains), isoform_accessibility, coreceptor_requirements,
   orthology, paralogs, surface_engagement_validation, structured
   contradiction adjudication, and a full Evidence chain anchored to
   verbatim quotes from cached sources. Surface-localization assays
   carry assay-type-specific detail (mass-spec method, antibody
   identity, cell-type context). Runs Sonnet 4.6.
   `src/accessible_surfaceome/agents/surface_annotator/`.

## Cloud / public data

The project owns two Cloudflare D1 databases on the same account:

- **`surfaceome_agents`** (private) — full agent runs, prompt history,
  token / cost telemetry, raw model output. The pipeline reads + writes
  this via the HTTP API; see `cloudflare/d1_schema.sql` +
  `cloudflare/d1_compara_schema.sql`.
- **`surfaceome_public`** (public mirror) — column-whitelisted subset of
  the private DB: Ensembl Compara orthologs, benchmark truth labels,
  triage verdicts (sans cost/token data), and per-gene
  `SurfaceomeRecord` JSONs. Schema in `cloudflare/d1_public_schema.sql`.
  Synced one-way from private via `scripts/sync_public_d1.py`.

A read-only **Cloudflare Worker** at
`cloudflare/workers/surfaceome_api/` exposes `surfaceome_public` as a
JSON API:

```
GET /v1/health
GET /v1/genes                    — list of annotated genes
GET /v1/genes/:symbol            — full SurfaceomeRecord
GET /v1/orthologs/:symbol        — mouse + cyno orthologs
GET /v1/benchmark[/{symbol}]     — curated truth labels
GET /v1/triage/:symbol           — per-call model verdicts
```

Deploy: `cd cloudflare/workers/surfaceome_api && npx wrangler deploy`.

## Viewer

The `viewer/` directory is a Vite + React + TypeScript SPA that renders
`SurfaceomeRecord` JSONs. Today it reads static files from
`viewer/public/data/genes/*.json` (committed snapshots — currently
HSPA1A and TGOLN2 as v0.5.0 reference records). The eventual path is
for the viewer to read from the public Worker API instead.

Plan: deploy at `surfaceome.deliverome.org` via a Cloudflare Pages
project pointed at this repo's `viewer/` directory.

## Layout

- `src/accessible_surfaceome/sources/` - one module per M1 data source (`uniprot.py`, `go.py`, `surfy.py`, `cspa.py`, `deeptmhmm.py`, `hpa.py`, `compartments.py`, `ensembl_compara.py`); each exposes `download` / `build` subcommands. Shared helpers under `sources/_support/`.
- `src/accessible_surfaceome/merge/` - candidate-universe orchestration; loaders, normalization, and gene-symbol resolution.
- `src/accessible_surfaceome/agents/surface_triage/` - the triage agent (orchestrator + prompts + Pydantic models).
- `src/accessible_surfaceome/agents/surface_annotator/` - the deep-dive agent (orchestrator + tool registry + deep-dive pack loader + evidence-promotion pipeline + audit module).
- `src/accessible_surfaceome/audit/` - audit scripts and blog figures.
- `src/accessible_surfaceome/controls.py` - control-panel builder.
- `src/accessible_surfaceome/cloud/` - D1 HTTP client + triage-run uploader.
- `src/accessible_surfaceome/tools/` - shared per-tool helpers + Pydantic models.
- `cloudflare/` - D1 schemas + Worker code for the public API.
- `scripts/` - one-shot data refreshers (`refresh_compara.sh`, `upload_compara_to_d1.py`, `sync_public_d1.py`), the triage runner (`triage_runner.py`), and per-eval render scripts.
- `viewer/` - SPA codebase.
- `data/raw/` `data/external/` `data/processed/` `data/annotations/` - source snapshots, normalized tables, and agent outputs (annotations dir is gitignored; viewer/public/data/genes/ holds the published snapshot).
- `docs/` - project plans, eval reports, decisions.
- `tests/` - pytest suite.

## Commands

From this directory:

```bash
uv sync
uv run accessible-surfaceome build
uv run python -m accessible_surfaceome.merge
uv run python -m accessible_surfaceome.sources.surfy build
uv run python -m accessible_surfaceome.sources.cspa build
uv run python -m accessible_surfaceome.sources.deeptmhmm build
uv run python -m accessible_surfaceome.controls build \
  --controls-json /path/to/canonical_delivery_positive_controls/controls.json \
  --surfaceome-csv /path/to/surfaceome_expressed.csv \
  --mygene-symbol-universe-tsv /path/to/candidate_universe.tsv
```

The candidate-universe merge writes TSV outputs under
`data/processed/candidate_universe/`. The control builder writes a
consolidated panel under
`data/processed/controls/surfaceome_control_panel.tsv` (ADC + Lycia/LYTAC
positives, patent delivery-handle positives, negative controls).

## Agent commands

```bash
# Sync the deep-dive agent to Anthropic (one-time per code change to agent.py / prompts)
uv run accessible-surfaceome agents sync

# Annotate one gene end-to-end (Sonnet 4.6, ~$0.30-0.50, ~5 min):
uv run accessible-surfaceome agents annotate HSPA1A

# Audit the corpus round-trip + Sonnet entailment on a record:
uv run accessible-surfaceome agents audit-corpus HSPA1A

# Run the triage benchmark sweep (147-gene mainbench):
uv run python scripts/triage_runner.py --model claude-sonnet-4-6 --replicates 1 --d1
```

## D1 / public-mirror commands

```bash
# Refresh Ensembl Compara CSV + upload to D1:
bash scripts/refresh_compara.sh

# One-way push from private surfaceome_agents → public surfaceome_public:
uv run python scripts/sync_public_d1.py

# Deploy the public API Worker:
cd cloudflare/workers/surfaceome_api && npx wrangler deploy
```

Eval reports and design decisions live under `docs/evals/` and
`docs/decisions/`. Latest reference annotations:
[HSPA1A](docs/evals/hspa1a-deep-dive-eval-2026-05.md) (conditional-surface
stress test) and TGOLN2 (trafficking_cycling test).

## Documentation

- [Figure reproducibility schema (v1)](docs/figure-reproducibility-schema.md) — what we embed in each figure so downstream tools can verify reproduction
