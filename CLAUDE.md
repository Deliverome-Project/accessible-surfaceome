# CLAUDE.md

This file provides guidance to Claude Code for this repository.

## Commit conventions — no Co-Authored-By trailer

Do **not** add `Co-Authored-By: Claude <…>` (or any AI-attribution trailer) to git commit messages or PR descriptions. The repo's `.claude/settings.json` carries the equivalent `attribution.commit/pr: ""` config; this CLAUDE.md instruction is the belt-and-suspenders override for agents whose system prompt would otherwise inject the trailer.

## Project Overview

`accessible-surfaceome` is a workspace for building an annotated catalogue of
human cell-surface proteins from seven public data sources.

Current implementation focus: candidate-universe builders (M1).

## Repository Structure

- `src/accessible_surfaceome/` core package
- `src/accessible_surfaceome/sources/` per-source download/build modules (one file per data source); shared infra in `sources/_support/`
- `src/accessible_surfaceome/merge/` candidate-universe orchestration (loaders, normalization, gene-symbol resolution)
- `src/accessible_surfaceome/audit/` audits + blog figures
- `src/accessible_surfaceome/tools/` per-machine install plumbing
- `viewer/` Next.js 16 app — standalone Cloudflare Pages project deployed at `surfaceome.deliverome.org`
- `data/raw/`, `data/external/`, `data/processed/`, `data/analysis/`
- `docs/` plans/reports

## Setup

```bash
uv sync
```

## Common Commands

```bash
uv run accessible-surfaceome build
uv run python -m accessible_surfaceome.merge
bash scripts/check-py.sh
uv run ty check
uv run pytest -q
cd viewer && npm install && npm run dev   # Next.js viewer at localhost:3000
```

## Quality Checks

- `bash scripts/check-py.sh` runs ruff + ty + compile + pytest.
- Use `uv run pre-commit run --all-files --config .pre-commit-config.yaml` before PR.

## Deep-dive agents run in-process with local prompts (no managed-agent sync)

`surface_triage`, the v1 deep-dive trio (`surface_evidence_compiler`, `biology_compiler`, `surfaceome_synthesizer`), and the v2 block builders + `plan_trim_select` are all invoked **in-process**: each runner reads its local prompt file (`prompts/system.md`) at call time and loops `client.messages.create(...)` — a plain Anthropic Messages API call (the compilers add tools; the synthesizer + triage run tool-less). There is **no Managed-Agents registration, no Anthropic-stored prompt snapshot, and no auto-sync** in the shipped code.

**Editing a prompt takes effect on the very next local invocation — there is nothing to push.** Edit the relevant `prompts/*.md` (or the `SurfaceomeRecord` / `SynthesizerLLMFilters` schema in `src/accessible_surfaceome/tools/_shared/models.py`, which is read locally to build the structured-output tool) and re-run. No `.runs/agents-registry.json` is read at run time; there is no `sync_agent_and_environment` call and no `accessible-surfaceome agents sync` command (the `agents` subcommand just runs the v1 deep-dive). Fast local iteration is the point.

> **Historical note (do not trust stale references).** An earlier design proposed registering these as Anthropic Managed Agents with sha-checked auto-sync on drift (`.runs/agents-registry.json`, `sync_agent_and_environment`, `ANNOTATE_NO_AUTO_SYNC`). **That machinery was never wired into the shipped code** — every runner is a plain in-process `messages.create` loop reading its local prompt. If you find references to managed-agent sync / auto-sync / `ANNOTATE_NO_AUTO_SYNC` anywhere, they are stale and describe a design that doesn't exist.

### v2 is the production deep-dive path

The **production deep-dive pipeline is `surfaceome_v2`** ([src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py](src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py), invoked via [scripts/surfaceome_v2_annotate.py](scripts/surfaceome_v2_annotate.py)). It runs `plan_trim_select` (dual A1/A2 literature passes) → 10 in-process block builders → the in-process synthesizer (`run_synthesizer_with_drafts` → `_run`, which reads [surfaceome_synthesizer/prompts/system.md](src/accessible_surfaceome/agents/surfaceome_synthesizer/prompts/system.md) locally and calls `messages.create` with no tools) → derives `Filters` → assembles + publishes the record. Every prompt under [plan_trim_select/prompts/](src/accessible_surfaceome/agents/plan_trim_select/prompts/), [surfaceome_v2/prompts/](src/accessible_surfaceome/agents/surfaceome_v2/prompts/), and [surfaceome_synthesizer/prompts/](src/accessible_surfaceome/agents/surfaceome_synthesizer/prompts/) takes effect at the next local invocation — no sync. See [docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md](docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md) "Production architecture update (post-PR #38)" for the v1/v2 trade-off table.

The v1 orchestrator (`surfaceome_v1`) stays for historical reproducibility; it is not the production path. Its `_derive_filters` helper is reused by v2.

**Cost note:** a full v2 deep-dive is ~$2–3 on Sonnet 4.6 (the synthesizer step alone ~$0.10–0.20). There is **no stale-remote-prompt risk** — the local prompt is always what runs — but a re-run costs real money, so validate a prompt change on one gene before sweeping the cohort.

### v2 publishes records by default — `--no-publish` to opt out

After a v2 annotate run validates, `scripts/surfaceome_v2_annotate.py` writes the record to **three** surfaces:

1. `data/annotations/{symbol}.json` — the agent's canonical disk artifact (was previously gated behind `--persist`; now default-on, opt out with `--no-persist`).
2. `viewer/public/data/surfaceome/{symbol}.json` — the viewer's offline / Worker-down fallback.
3. Public Cloudflare D1 `surface_annotation.annotation_json` — what the `api.deliverome.org/surfaceome/v1/genes/:symbol` Worker serves.

Items (2) and (3) happen via [`accessible_surfaceome.cloud.surface_annotation.publish_record`](src/accessible_surfaceome/cloud/surface_annotation.py), default-on with `--no-publish` to skip. The D1 push is **auto-skipped** with a warning (not an error) when the `CLOUDFLARE_*` env vars aren't set, so CI without secrets still works.

**Why default-on:** previously a record could land on disk via `--persist` but never reach D1 — which meant the Worker kept serving a stale schema-incomplete row and the viewer crashed on missing fields (e.g. `rec.deterministic_features.surface_bind.has_data`). The fix is to add the field to the **records**, not defensive `?.` chains in the viewer. Publishing-by-default is the mechanism that enforces this.

The same `publish_record` helper backs `scripts/upload_viewer_snapshots_to_d1.py` (the bulk-sync maintenance utility) via its `publish_record_dict` variant, so the agent-time and bulk-sync paths can't drift. When in doubt about whether D1 is in sync with the in-tree snapshots, run the maintenance script (dry-run) — it'll report any gaps.

**Edge-cache purge-on-publish.** After the D1 write, `publish_record` purges the Worker's edge cache for the affected URLs (`/v1/genes/{SYMBOL}` + `/v1/catalog` + `/v1/genes`) so a republished record goes live **immediately** rather than after the Worker's `Cache-Control` TTL (up to 1 day for per-gene records). The purge is targeted by-URL — never `purge_everything`, since the Worker shares the `deliverome.org` zone with the main site. It needs `CLOUDFLARE_ZONE_ID` plus a **Zone → Cache Purge** scope on `CLOUDFLARE_API_TOKEN`; missing either soft-skips with a warning (records then go live on TTL). This is the freshness half of the "never let D1 drift" rule — long TTLs stay safe *because* publish purges. The zone's **cache rule** (ignore query strings — kills `?_=random` cache-busting amplification) is applied by [`scripts/apply_cf_edge_rules.py`](scripts/apply_cf_edge_rules.py) (dry-run by default, `--execute`; Cache Rules are on every plan). **Per-IP rate limiting lives in the Worker** via the native Workers Rate Limiting binding (`env.RATE_LIMITER` / `RATE_LIMITER_HEAVY` in `cloudflare/workers/surfaceome_api/wrangler.toml` — in-colo, free, not KV; tighter on `/v1/catalog` + `*.tsv`), because Cloudflare's zone-level WAF Rate Limiting Rules need Pro+ (`apply_cf_edge_rules.py --only ratelimit` applies those if the zone has the feature).

## Triage body-fetch: Unpaywall + PDF fallback

The abstract-triage stage of `plan_trim_select` ([abstract_triage.py](src/accessible_surfaceome/agents/plan_trim_select/abstract_triage.py)) fetches a `worth_fetching` paper's body through a 3-step chain, each falling through on miss/empty:

1. **PMC JATS** via `paper.pmc_id`, or PMID→PMCID via NCBI eLink.
2. **Unpaywall OA PDF** — DOI → OA locations → **all** PDF URLs tried best-quality-first (publisher publishedVersion > repository), so a bot-blocked publisher copy can still be recovered from a repository copy (OSTI, institutional repos). Each PDF is parsed by [`pdf_parse.py`](src/accessible_surfaceome/agents/plan_trim_select/pdf_parse.py) (pdfplumber: `extract_words` spacing, gutter-based 2-column split, font-aware run-in/bold heading detection → the JATS `SectionName` enum). Failure → abstract fallback (never crashes the batch).

Operational notes:
- **Dep**: `pdfplumber` (MIT). `pypdfium2` is pinned `<5.9.0` via `[tool.uv] constraint-dependencies` — a supply-chain cooldown (5.9.0 was <7 days old when added); safe to relax after it ages out.
- **Binary cache**: `CachedHTTP.get_bytes` caches downloaded PDFs to `data/external/blob_cache/` (gitignored — copyrighted PDFs; never commit). Streamed with a size cap (`_MAX_PDF_BYTES`) + page cap; per-host courtesy interval so we don't hammer publishers at cohort scale.
- **Config**: `UNPAYWALL_EMAIL` (optional; falls back to the project contact). Keep the **polite, identifiable User-Agent** — do not impersonate a browser. Several publishers (ASH/*Blood*, Wiley) 403 our UA regardless; those fall back to abstract by design.
- **Provenance / licensing**: `TriageAction.fetch_source` records `pmc_xml` vs `unpaywall_pdf`; `TriageAction.fetch_license` records the raw Unpaywall OA license of the recovered copy ("must track per-item license"). Redistribution is **not gated** — we ship only short substring-anchored snippets (fair use), but the license is captured so a gate can be added later. PDF clips key on the clean `PMID:`/`PMC:` source id (not `DOI:`).
- **Validate** with `scripts/probe_triage_fetch.py` / `scripts/probe_pdf_fallback.py` ($0, no model calls).

## Agent Command Allowlist

- Agents may run `uv run python ...` commands for repository modules/scripts.

## Worktrees, Env, and Data Hydration

- Claude Code and Codex App may create their own worktrees; after entering one, run `scripts/bootstrap-worktree.sh none` unless the task needs data.
- Use `scripts/bootstrap-worktree.sh candidate` for candidate-universe data, or `scripts/bootstrap-worktree.sh all` only when all data artifacts are needed.
- `.env` is gitignored and should be symlinked from the canonical local checkout or `ACCESSIBLE_SURFACEOME_ENV_SOURCE`; never commit `.env`. The CLI loads it from the repo root at startup with shell-env precedence; see `.env.example` for documented keys (`ANTHROPIC_API_KEY`, `NCBI_API_KEY`).
- Run `git lfs fsck` only after full data hydration.

## Git Hooks

- Enable hooks with `./scripts/setup-git-hooks.sh`.

## CI

- CI workflow: `.github/workflows/ci.yml`
- Runs `uv sync --frozen`, `uv lock --check`, `bash scripts/check-py.sh`.

## Pull Request Conventions

PR titles are validated by `.github/workflows/lint-pr-title.yml` (Conventional
Commits). A title that doesn't match fails the check and blocks merge.

- **Format**: `<type>(<scope>): <subject>` — scope is optional.
- **Allowed types**: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`.
- **Allowed scopes**: `surface-proteome`, `sources`, `merge`, `audit`, `agents`, `tools`, `data`, `docs`, `ci`, `deps`, `viewer`.
- **Pick a scope by what the PR mostly touches**: `sources/` → `sources`,
  `merge/` → `merge`, `audit/` → `audit`, `agents/` (Managed Agent
  orchestrator, system prompt, agent definition) → `agents`, `tools/`
  (custom-tool handlers like `gene_lookup`, `patent_lookup`) → `tools`,
  dependency bumps → `deps`, CI workflows → `ci`, project-wide /
  cross-cutting → `surface-proteome`. If you need a scope that isn't
  listed, update the workflow's `scopes:` block in the same PR — don't
  invent a new one.

## Gene identifier resolution

When writing any code that takes "a gene" as input — agent tool, sweep
runner, figure generator, manual one-off — **the entry point must be a
stable identifier, not a gene symbol.** Bare gene symbols silently
resolve to the wrong protein for a small but real subset of human
genes (~0.2% of the 19,464-row protein-coding cohort), including
high-profile failures like **COX1** (cyclooxygenase-1 vs the
mitochondrial cytochrome c oxidase the cohort actually meant) and
**WAS** (Wiskott-Aldrich protein vs the MT-RNR1 rRNA gene). The audit
that surfaced these lives at
[`scripts/audit_resolver_hgnc_id_v3.py`](scripts/audit_resolver_hgnc_id_v3.py);
the documented divergence list is at
`data/analysis/resolver_definitive_audit_v3.tsv`.

### The canonical resolver

`src/accessible_surfaceome/tools/gene_lookup.py:resolve_by_hgnc_id` is
the preferred entry point. Callers thread `hgnc_id` through from the
cohort row:

    bundle = resolve_by_hgnc_id(row["hgnc_id"], http=http)

The cohort file
[`data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv`](data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv)
carries `hgnc_id` for every gene (100% coverage as of last refresh) —
no symbol-keyed sweep should exist for cohort-driven code paths.

The legacy `resolve(symbol_or_acc)` stays in the module for free-text
agent tool calls (where only a symbol or accession-shape string is
available); it emits a `UserWarning` on the symbol path so misuse is
auditable in logs.

### Stable-ID cache in D1

Every gene's resolved identifiers are materialized in D1's
`gene_identifier` table (private; public mirror at
`gene_identifier_public`). Schema lives at
[`cloudflare/d1_schema.sql`](cloudflare/d1_schema.sql) and
[`cloudflare/d1_public_schema.sql`](cloudflare/d1_public_schema.sql).
Downstream tools query stable identifiers directly:

    SELECT uniprot_acc, ensembl_gene, ncbi_gene_id, ensembl_canonical_protein
    FROM gene_identifier_public WHERE hgnc_id = ?;

This is the **only** path for stable-ID lookups by downstream code —
no script should call `resolve_by_hgnc_id` at query time when it
could read this table. Resolver upgrades change the `resolver_version`
column; consumers detect staleness by comparing against the resolver
SHA they expect.

Rebuild with [`scripts/build_gene_identifier_table.py`](scripts/build_gene_identifier_table.py)
after any resolver patch or cohort refresh — `--execute` to write to
D1, otherwise dry-run. Idempotent UPSERT on `hgnc_id`; sub-5-minute on
a warm cache.

## Working with the D1 databases

Two D1 databases:
- **`surfaceome_agents`** (private) — full agent-run history with
  prompts, costs, prose reasoning. Schema:
  [`cloudflare/d1_schema.sql`](cloudflare/d1_schema.sql).
- **`surfaceome_public`** (mirror) — column-whitelisted subset the
  Worker + viewer read. Schema:
  [`cloudflare/d1_public_schema.sql`](cloudflare/d1_public_schema.sql).
  Synced from the private DB by `scripts/d1_public_mirror_*.py`.

### Querying D1 from Python

`accessible_surfaceome.cloud.d1_client.D1Client` is the canonical
client; it speaks Cloudflare's REST API directly (no wrangler
needed). Auth pulls `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
+ the database UUID from `.env`. Pattern:

    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env
    load_env()
    with D1Client() as d1:
        rows = d1.query(
            "SELECT uniprot_acc FROM gene_identifier WHERE hgnc_id = ?;",
            ["HGNC:1234"],
        )
        # rows → list[dict] — column names as keys

For UPSERTs / mutations, the same `query()` method handles them — D1
returns an empty result set for non-SELECT statements. **D1's HTTP
API doesn't accept multi-statement batches**; submit one statement
per call (loop chunked for bulk loads).

### Applying schema changes when wrangler isn't handy

The deprecated wrangler v1 on common install paths can't speak D1.
Rather than installing the new wrangler in every fresh worktree,
apply DDL by calling `D1Client.query()` with each `CREATE TABLE` /
`CREATE INDEX` statement one at a time. Example used to bring up
`gene_identifier`:

    statements = ["CREATE TABLE IF NOT EXISTS gene_identifier (...);",
                  "CREATE INDEX IF NOT EXISTS idx_gene_identifier_... ON ...;",
                  ...]
    with D1Client() as d1:
        for s in statements:
            d1.query(s, [])

Same trick works for ad-hoc analytical SELECTs from a notebook /
script — no need to install wrangler just to peek at row counts.

### Key tables to know

| Table | Purpose | Primary lookup |
|---|---|---|
| `gene_identifier` | **Stable-ID cache.** Per-gene canonical (uniprot_acc, ncbi_gene_id, ensembl_gene, ensembl_canonical_protein) resolved through the HGNC-ID path. **Read this before re-resolving from any other identifier.** | `hgnc_id`, `hgnc_symbol`, `uniprot_acc` |
| `triage_run` | Per-(model × variant × replicate × gene) triage cells. | `(run_id, gene_symbol, model, prompt_variant, replicate)` |
| `deep_dive_run` | Per-gene deep-dive (surface_annotator) records. | `(run_id, gene_symbol)` |
| `candidate_universe_public` | Genome-wide DB-vote table (the catalog index). | `(universe_version, gene_symbol, uniprot_acc)` |
| `benchmark_version` | Bench-snapshot symbol → uniprot pinning. | `(bench_version, gene_symbol)` |

### `run_id` conventions

- `genome_full_sonnet_ncbi_v1` — the canonical 2026-05-12 Sonnet
  triage sweep over the cohort.
- `genome_full_sonnet_ncbi_v1__resolver_v3_fix` — corrected re-runs
  of the 45 cells the v3 resolver audit flagged. **Originals are
  preserved**; analytics that should incorporate the fix should
  COALESCE-prefer the fix run over the original (see the
  Postgres-flavored snippet below).

Composite-source SELECT that gives "latest verdict per (gene_symbol,
model, variant), preferring fix rows over originals":

    SELECT * FROM triage_run t
    WHERE (t.run_id = 'genome_full_sonnet_ncbi_v1__resolver_v3_fix')
       OR (t.run_id = 'genome_full_sonnet_ncbi_v1'
           AND NOT EXISTS (
               SELECT 1 FROM triage_run f
               WHERE f.run_id = 'genome_full_sonnet_ncbi_v1__resolver_v3_fix'
                 AND f.gene_symbol = t.gene_symbol
                 AND f.model = t.model
                 AND f.prompt_variant = t.prompt_variant
           ));

Anything else that reads `triage_run` should adopt this pattern
until the fix run is mirrored back into the canonical run_id.

### Failure modes the HGNC-ID path is designed to avoid

Three classes of bug the symbol-keyed path has, all encoded in the
audit's divergence buckets:

1. **Primary-name collisions across reviewed UniProt entries**
   (`multi_xref_canonical_pick_disagrees`) — when ≥2 reviewed
   Swiss-Prot entries share a primary `geneName.value`, UniProt's
   `gene_exact:` server-rank ordering decides the winner non-
   deterministically. The HGNC-ID picker enumerates HGNC's
   `uniprot_ids` xref explicitly and tiebreaks on `(reviewed,
   primary-name-match, canonical-isoform, earliest firstPublicDate,
   acc)` — pinning the canonical Swiss-Prot record.
2. **HGNC xref empty** (`production_caught_hgnc_missed`) — HGNC
   curates the gene but hasn't filled the UniProt xref. The
   resolver falls back to UniProt symbol search via HGNC's primary
   symbol, then HGNC's `prev_symbol` list, so these genes don't
   drop out.
3. **Symbol-reassignment drift** (`production_missed_hgnc_caught` +
   `synonym_fallback_vs_canonical`) — HGNC re-assigns a symbol;
   symbol-keyed lookup returns the gene the symbol points to *now*
   (sometimes the wrong kingdom: WAS → MT-RNR1 rRNA). HGNC-ID
   resolution returns the gene the cohort row actually meant.

### Downstream searches: identifier-per-source

Build any new tool by reading from the resolved `IdentifierBundle`,
never by re-resolving from the symbol. Once the bundle is in hand:

| Source | Identifier from the bundle |
|---|---|
| AlphaFold DB / PDB / InterPro / Pfam / DrugBank / Reactome (protein) | `bundle.uniprot_acc` |
| Ensembl / GTEx / HPA / Open Targets / STRING (gene) | `bundle.hgnc_id` or `bundle.ensembl_gene` |
| PubMed / Europe PMC (free text) | OR of `bundle.aliases + bundle.previous_symbols + bundle.hgnc_symbol` |
| dbSNP / ClinVar / OMIM | `bundle.ncbi_gene_id` or `bundle.hgnc_id` |

Symbol-keyed queries to structured databases reintroduce the same
bug class one layer down — don't.

### Refreshing the audit

After any cohort regeneration, any UniProt or HGNC API behavior
change, or any picker logic change, re-run the audit:

    uv run python scripts/audit_resolver_hgnc_id_v3.py

Sub-minute on a warm cache, ~60-90 min on a cold cache. Outputs
`data/analysis/resolver_definitive_audit_v3.tsv` (per-symbol
divergences) and `_d1_rows.tsv` / `_d1_rows_full.tsv` (affected D1
rows for Phase-4-style targeted reruns). The
`scripts/audit_resolver_hgnc_id_v3_extend.py` companion scans
`triage_run`, `deep_dive_run`, and `benchmark_version` in one pass.

Pinned regression cases (BBC3, ND4, PRNP, TSPO, ABHD4, HSD17B8,
SACK1A, CLMB, COX1, COX2, WAS) live at
[`tests/test_gene_lookup_resolver.py`](tests/test_gene_lookup_resolver.py)
— any picker / fallback regression breaks these.

## Coding Style

See [docs/coding-style.md](docs/coding-style.md) for the conventions we
hold code to and the short rubric for assessing diffs.

## Plotting Conventions

Every plot in this repo uses `src/accessible_surfaceome/audit/_plotting_config.py`:

- **Always start a plotting script with `setup_plotting_style(...)`.** It applies seaborn whitegrid + the Deliverome palette + the brand rcParams (Manrope, transparent figure/axes background, 300 DPI on save). It also registers bundled fonts from `assets/fonts/` so Manrope actually resolves — calling it before `plt.subplots()` is the contract.
- **Use seaborn's plotting functions** (`sns.barplot`, `sns.scatterplot`, `sns.boxplot`, etc.) over raw matplotlib. Build a tidy long-format `pandas.DataFrame` first and pass it through `data=...`. Color via the `CATEGORICAL_PALETTE` / `SEQUENTIAL_PALETTES` exports, not ad-hoc hex codes.
- **Call `sns.despine(ax=ax, top=True, right=True)` after creating each axes.** The despine inside `setup_plotting_style` runs *before* any axes exist and is a no-op for new figures.
- **Save with `save_figure(fig, filename, output_dir, formats=('pdf', 'png'))`** — PDF for vector publication, PNG for raster with alpha. **Never JPEG** — it can't carry the transparent background that the config requests, so the saved image gets a forced-white fill.
- **Output to `data/analysis/<area>/`.** Don't write figures into source dirs or repo root.
- **LFS-track raster outputs ≥10 MB** per the standard rule; check `.gitattributes` if you're producing a large PNG.

## Final-figure data flow (pre-publication)

**The work is pre-publication.** Figures and tables that ship to readers today are draft artifacts — at submission time they'll be re-pinned to immutable Zenodo DOIs and the figure scripts + gists will swap their source URLs over. Until then, the lineage is:

```
  private D1 (triage_run)
    │
    ├─sync_public_d1.py───────▶ public D1 (triage_run_public, candidate_universe_public, ...)
    │                              │
    │                              ├─Worker /v1/triage/export.tsv ─────▶ live consumers (notebooks, agents)
    │                              ├─Worker /v1/benchmark/export.tsv
    │                              ├─Worker /v1/catalog
    │                              ├─Worker /v1/benchmark/matrix
    │                              ├─Worker /v1/genes/{SYMBOL}
    │                              └─Worker /v1/triage/{SYMBOL}
    │
    └─export_mainbench_to_tsv.py──▶ data/processed/triage_bench/mainbench_canonical_v1.tsv
                                      │ (re-reads from PUBLIC D1, not private — so the public
                                      │  mirror is the citable source. LFS-exempted in
                                      │  .gitattributes so raw.githubusercontent.com serves
                                      │  text, not a pointer.)
                                      │
                                      └─raw.githubusercontent.com/{REPO}/{BRANCH}/…
                                          │
                                          └─figure scripts + published gists
                                              (data/analysis/figures/make_*.py,
                                               gist.github.com/beccajcarlson/...)
```

**Final figures read from `raw.githubusercontent.com/{REPO}/{BRANCH}/…`** — not the Worker, not the local file system. Reasons:
- **Citation stability.** Pinning `BRANCH` to a commit SHA at publication time freezes the file forever; the API endpoint could move or change shape.
- **Two clean halves of the contract.** Predictions live in `data/processed/triage_bench/mainbench_canonical_v1.tsv` (refreshed from public D1 by `scripts/export_mainbench_to_tsv.py`); truth labels live in `data/eval/triage_benchmark_v1.tsv` (the curated input). The Worker is a convenience surface for non-figure consumers — agents, notebooks, the viewer.
- **Pre-pub flexibility.** Today the gists' `BRANCH = "main"` so a re-run picks up fresh data. At publication, `BRANCH` becomes a commit SHA and the gist URL pins to a Zenodo DOI.

**Refresh procedure** (after any sweep that updates predictions in public D1):

```bash
# Pulls the latest mainbench_canonical_v1 rows from public D1 and writes
# data/processed/triage_bench/mainbench_canonical_v1.tsv. Identical shape
# to /v1/triage/export.tsv?run_id=mainbench_canonical_v1&replicate=1.
uv run python scripts/export_mainbench_to_tsv.py

# Backfill stable IDs (hgnc_id, ensembl_gene, ncbi_gene_id, uniprot_acc) into
# the figure TSVs by joining each row against gene_identifier_public. Run
# after ANY of the four figure TSVs are regenerated; the script is
# idempotent and only touches columns it owns:
#   • data/processed/candidate_universe/candidate_universe.tsv
#   • data/eval/triage_benchmark_v1.tsv
#   • data/processed/triage_bench/mainbench_canonical_v1.tsv
#   • data/processed/triage_bench/db_optimized_cutoffs.tsv
uv run python scripts/augment_figure_tsvs_with_stable_ids.py

git add data/processed/triage_bench/mainbench_canonical_v1.tsv \
        data/processed/candidate_universe/candidate_universe.tsv \
        data/eval/triage_benchmark_v1.tsv \
        data/processed/triage_bench/db_optimized_cutoffs.tsv
git commit -m "chore(triage): refresh canonical TSVs from public D1 + augment stable IDs"
```

### Figure-input TSV conventions

Any TSV that drives a published figure (and lives under `data/processed/**` or `data/eval/**` for raw-GitHub fetch) must follow these conventions so external readers can reanalyze without re-resolving identifiers or doing multi-file joins for common questions.

**1. Stable identifiers on every gene-keyed row.**

Per the "Gene identifier resolution" section above, `hgnc_id` is the canonical stable key — symbol-only joins silently misroute ~0.2% of human genes (the COX1 / WAS class). Every per-gene or per-protein TSV row must carry:

| Identifier | When required |
|---|---|
| `hgnc_id` | Always (for any gene-keyed row) |
| `hgnc_symbol` | Always |
| `uniprot_acc` | When the row is keyed on or otherwise references a protein |
| `ensembl_gene` | Always |
| `ncbi_gene_id` | Always |
| `ensembl_canonical_protein` | When the row references a specific protein isoform |

The `scripts/augment_figure_tsvs_with_stable_ids.py` script is the canonical place to backfill these by joining against `gene_identifier_public`. **Extend that script** (don't write a new one) when adding a new figure-input TSV — the join logic should live in one place.

**2. Denormalize the most-common reanalysis questions.**

A reader should be able to answer common questions in one filter, not a 3-way join. Concretely, the augment script also denormalizes:

| TSV | Denormalized columns | Saves the join to |
|---|---|---|
| `candidate_universe.tsv` | `sonnet_verdict`, `sonnet_reason`, `has_deep_dive`, `is_bench_member` | catalog API / `surface_annotation` / bench TSV |
| `triage_benchmark_v1.tsv` | `n_db_votes`, `sonnet_verdict`, `sonnet_reason` | candidate_universe / catalog API |
| `mainbench_canonical_v1.tsv` | `ground_truth_verdict`, `ground_truth_class`, `is_match` (soft-credit), 5 per-DB `*_surface_flag`, `n_db_votes`, `has_deep_dive` | bench TSV / candidate_universe / `surface_annotation` |
| `db_optimized_cutoffs.tsv` | All 5 canonical `*_surface_flag` columns + cutoff-variant flags (SURFY thresholds, HPA tiers, CSPA-with-unspecific, GO-experimental+curated) + `n_sources_surface`, `n_sources_optimized` | candidate_universe |

Decide what to denormalize by asking: "Is this a join a typical reanalyst needs for an obvious question?" — if yes, add it. Don't denormalize speculatively.

**3. Stay un-LFS, committable, and size-bounded.**

Each figure TSV must be **LFS-exempted** (`-filter -diff -merge text` in `.gitattributes`) so `raw.githubusercontent.com` serves it as plain text rather than an LFS pointer. That puts a soft ceiling on file size:

- **Hard cap**: GitHub's 100 MB per-file limit on non-LFS files.
- **Practical cap**: ~5 MB per file. Beyond that, `git diff` review gets painful and `pd.read_csv(url)` over a slow link becomes annoying.
- **Today's set** sums to ~2.4 MB across 4 TSVs (largest is `candidate_universe.tsv` at 1.85 MB / 5,680 rows × 84 cols). Plenty of headroom.

If a planned addition would push a TSV over the practical cap, prefer (a) a separate sidecar TSV, (b) a derived summary file, or (c) writing to D1 and serving via the Worker — not a wider TSV.

**4. Never include full reasoning prose.**

The TSVs carry short coded reasons (`predicted_reason`, `sonnet_reason`, `ground_truth_signal`) — never the full `verdict_reasoning` or deep-dive notes. Full prose stays in private D1 and the Worker's per-gene endpoints. This keeps the TSVs small *and* keeps the citation-stable reanalysis files free of model-version-specific reasoning that doesn't transfer cleanly across model upgrades.

**5. New figure → check the TSV list before adding a 6th TSV.**

The current set is 4 augmented TSVs + 1 aggregate (`db_cutoff_tradeoff_points.tsv` — summary stats only, no gene IDs). When adding a new figure, first try to fit its data into one of the existing TSVs (most figures need a subset of what's already there). Only add a 6th TSV if the data is genuinely orthogonal — and if you do, add it to the augment script's coverage immediately so it stays in sync.

CI doesn't enforce that figure scripts only read from `BASE` (raw GitHub) — flag any new `make_*.py` that reaches into the API or a private path during review.

**At publication:** swap `BRANCH = "main"` for a pinned commit SHA in every figure script + gist, register the figure files on Zenodo, and update each gist's README to cite the Zenodo DOI alongside the raw GitHub URL.

## Final-Figure Gist Convention

When a figure is **promoted** to `data/analysis/triage_bench_final/` (or any other `*_final/` analysis directory) it must ship with a GitHub gist for reader-side reproduction. The gist is what gets linked from a Substack / blog post under the figure, since Substack can't host arbitrary CSV/code downloads.

Each gist contains exactly two files:
- `01_<figure_slug>.md` — one-paragraph context, run command, hyperlinks to the canonical data source and the canonical figure generator in the repo. The `01_` prefix forces this file to the top of the gist's alphabetical file list so it acts as a README.
- `make_<figure_slug>.py` — standalone Python reproduction script. Uses [**PyPA inline script metadata**](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) — `# /// script ... # ///` header to declare dependencies so readers run it with `uv run make_<figure_slug>.py` — no `pip install` step.

**Data fetching** — script reads from whichever source is canonical:
- **D1 (preferred when the canonical source is D1)** — script queries the public read-only D1 endpoint via HTTP. Used for figures driven by `triage_run`, `deep_dive_run`, `resolver_context_version`, etc.
- **Canonical TSV at `raw.githubusercontent.com`** — when the figure's data lives in a `data/processed/**.tsv` in the public repo, fetch it directly via the raw URL pinned to `main` (or a commit SHA for stronger immutability). **The TSV must be non-LFS** (LFS pointers don't resolve over the raw URL) and the repo must be public — add a `-filter -diff -merge text` exemption in `.gitattributes` to un-LFS any small canonical TSV the gists depend on.

Do not bundle a CSV in the gist unless the canonical source is unreachable (private repo, D1 without a public endpoint). Keep the gist as a thin wrapper around the canonical data.

**Visibility:** create as **public** by default — `gh gist create --public 01_<slug>.md make_<slug>.py -d "<short desc>"`. Figure-reproduction gists are linked from Substack / blog posts, so they're meant to be discoverable; public is the right default for this category. **GitHub does NOT allow flipping visibility after creation** (neither secret → public nor the reverse) — only delete-and-recreate, which invalidates the URL and breaks every place it's embedded (PNG `Source` tEXt, PDF `Subject`, canonical generator's `# Reproduction:` line, and the gist mirror's `GIST_URL` constant under `data/analysis/figures/`). Pick the right visibility on first creation. Before creating a new gist for an existing figure, **check the slug → gist-ID map in the saved-memory `figure_gists.md` reference** — duplicates have happened (e.g. an outdated `make_venn.py` predates the conforming `make_db_overlap_venn.py`).

Record the gist URL in the canonical generator's module docstring under a `# Reproduction:` line so readers can find it from the source script. The on-repo plotting script remains the source of truth; the gist is the readers' minimal-dependency mirror.

**Also embed the gist URL in the artifact itself** via `save_figure(..., gist_url=...)` (in `src/accessible_surfaceome/audit/_plotting_config.py`). The helper writes the URL into the PNG's `Source` tEXt chunk and the PDF's `Subject` info field, so the URL travels with the file when it gets dragged into a Substack draft, copied to Slack, or sent in email. Reading the metadata back:

| Audience | How to read it |
|---|---|
| **CLI / scripted** | `exiftool figure.png \| grep Source` (Homebrew: `brew install exiftool`). Also `pngcheck -t figure.png`, or `magick identify -verbose figure.png \| grep Source`. |
| **Python** | `from PIL import Image; Image.open("figure.png").info["Source"]` |
| **Non-technical reader** | Drop the PNG into an online viewer like [exif.tools](https://exif.tools/), [exifer.com](https://www.exifer.com/), or [onlineexifviewer.com](https://onlineexifviewer.com/) — they show every text chunk with the keyword name (look for "Source" or "PNG: Source"). On macOS, **GIMP** (free) → File → Open → Image → Image Properties → Comments. **macOS Preview's Inspector** (Cmd+I → ⓘ tab) does *not* surface PNG tEXt chunks, so don't rely on it. |
| **Doesn't work** | GitHub web preview, Slack image preview, the OS file properties dialog, Photoshop's File Info (it reads XMP, not PNG tEXt). |

So this is *author-side metadata*: it persists through any PNG-aware tool but isn't surfaced to a casual viewer in a browser. The on-image footer + gist link in the Substack post stays the primary surface for non-technical readers; the tEXt chunk is the durable backup.

## Web Viewer

`viewer/` is a **standalone Next.js 16 app** that ships as its own
Cloudflare Pages project at **`surfaceome.deliverome.org`**. It is *not*
a sub-route of `deliverome.org`'s main site — separate build, separate
deploy target, separate domain.

### Tooltip / InfoTip citation rule

Any tooltip (InfoTip body text, StatusPill `title=`, etc.) that
cites a paper **must include a PMID identifier AND a clickable link
to it** — never just an author-year phrase. **PMID is the default
identifier**: link to `https://pubmed.ncbi.nlm.nih.gov/{PMID}/`. Add
a DOI only as a *secondary* identifier when a reader genuinely needs
the publisher landing page — don't lead with it, and never ship
DOI-only.

Acceptable patterns:

* `Balbi et al. 2026, [PMID 41604262](https://pubmed.ncbi.nlm.nih.gov/41604262/)` — the default shape
* `Dana et al. 2019, [PMID 30445541](https://pubmed.ncbi.nlm.nih.gov/30445541/)`
* `Ramaraj et al. 2012, [PMID 22246133](https://pubmed.ncbi.nlm.nih.gov/22246133/)` — DOI optional, appended after the PMID only when it adds something
* `Bordeaux 2010 / Edfors 2018` — **not acceptable on its own**; reach for the
  PMIDs and link them. If you can't find the exact PMID, search PubMed
  before shipping (the user can't trace the citation otherwise).

Why PMID over DOI: the PubMed link doubles as the durability check —
a dead or retracted citation surfaces as a 404 when you verify it.
`doi.org` bot-blocks non-browser clients (returns HTTP 403 to
`curl`), so a DOI link can't be machine-verified during review the
way a PubMed link can. PMID is also the canonical biomedical
identifier and always resolves to a single record.

Why tooltips carry citations at all: they're the only on-page surface
where the cutoff / threshold provenance lives. A reader who wants to
verify the threshold must be one click from the primary source — the
gene-page prose can't carry every citation.

The text-bank entry point is `viewer/lib/tooltips.tsx`. Per-component
TT_* string constants (in `FiltersCard.tsx`, `AccessibilityRisksCard.tsx`,
etc.) follow the same rule. When you add a new threshold-bearing
tooltip, include the citation chain — never punt with "see
literature" or "per established practice".

The design language is borrowed from
`Deliverome-Project/deliverome-internal` PR #24 (Rosy Maroon: Maroon ·
Teal · Amber · Lavender; Manrope + Playfair Display via
`next/font/google`; PascalCase component dirs with `.module.css`; type
primitives `.h-display` / `.h-section` / `.lede` / `.label-mono` from
`app/globals.css`). Tokens are mirrored at
`viewer/app/design-tokens.css` — they have to be re-synced manually
when the deliverome.org system rev's.

Data: `viewer/public/data/surfaceome/{SYMBOL}.json` is the committed
in-tree snapshot (also reachable as
`https://surfaceome.deliverome.org/data/surfaceome/{SYMBOL}.json`).
Every gene is SSG'd through `generateStaticParams`; the loader at
`viewer/lib/surfaceome.ts` fetches the public Worker at
`api.deliverome.org/surfaceome/v1/genes/{SYMBOL}` (source in
`cloudflare/workers/surfaceome_api/`, bound to the `surfaceome_public`
D1 mirror) **first** and falls back to the committed `fs` snapshot only
on error — same record shape. Set `SURFACEOME_API_BASE=local` (or
empty) to force fs-only.

### Records source of truth — never edit a JSON snapshot without syncing D1

**The live site reads D1, not the committed JSON.** The Worker serves
each gene from public D1's `surface_annotation.annotation_json`; the
`viewer/public/data/surfaceome/*.json` snapshots are only the in-tree
source of truth + the on-error SSG fallback. So **a record change that
lands only in the JSON silently drifts the live site** — the page keeps
rendering D1's stale row. This is exactly what blanked the Family chip:
the `protein_family` → `llm_family` rename updated the JSON + viewer
code, but D1 still served the pre-rename shape, so `llm_family` was
missing and `prettyEnum(undefined)` rendered `—`.

Rules for changing what a gene page renders:

- **Don't hand-edit a JSON snapshot to change record content/schema and
  stop there.** The edit hasn't reached the live site until it's in D1.
- **Land the change in D1.** Normal path: re-run the annotator
  (`scripts/surfaceome_v2_annotate.py`), which publishes to public D1
  via `accessible_surfaceome.cloud.surface_annotation.publish_record`
  after every successful run. If you hand-edited the committed
  snapshots, push them with
  `uv run python scripts/upload_viewer_snapshots_to_d1.py --execute`
  (idempotent `INSERT OR REPLACE` on `(gene_symbol, schema_version)`;
  drops stale older-schema rows). Re-sync D1 in the **same** change as
  the JSON edit so the Worker and the in-tree snapshots never diverge.
- **Don't paper over JSON ↔ D1 schema drift with defensive shims / `?.`
  chains in the loader.** Fix the records and re-sync D1. A transitional
  loader shim is acceptable only as a stopgap while D1 is being
  re-synced — delete it once D1 carries the new schema.

Per-gene records must validate against the `SurfaceomeRecord` Pydantic
schema in `src/accessible_surfaceome/tools/_shared/models.py`. See
`viewer/README.md` for local dev + Cloudflare Pages deploy.

## Cloudflare D1 + R2 backups for agent runs

The `surfaceome_agents` D1 database stores every `surface_triage`
and `surface_annotator` invocation with full reproducibility metadata
(prompt SHA, benchmark version, schema version, prose reasoning). It's
separate from the website's `signups` D1. **The Pages binding lives
in the deliverome main-site repo's `wrangler.toml`** — this repo's
Python tooling reads / writes via D1's HTTP API and does not require
a Pages binding.

- **Schema**: `cloudflare/d1_schema.sql` — 6 tables, 3 views. Triage +
  deep-dive share the DB; cross-table joins (`triage_vs_deep_dive`)
  are the primary analytics target.
- **Upload**: `scripts/triage_runner.py --d1 --run-id <tag>` streams
  each completed cell into `triage_run` via `D1RunSink` as the sweep
  progresses. No separate batch-upload step. Idempotent on
  `(run_id, gene_symbol, model, prompt_variant, replicate, prompt_sha)`,
  so restarting a crashed sweep with the same `--run-id` skips cells
  that already landed.
- **Backup to R2** is CI-driven: `.github/workflows/d1-backup.yml`
  runs `scripts/d1_export_to_r2.sh` on every push to `main` that
  touches `cloudflare/d1_schema.sql`, `data/annotations/**`,
  `data/triage/**`, the uploader code, or the
  backup scripts themselves. Each run drops a timestamped SQL dump and
  a stable `latest.sql` pointer into the R2 bucket
  `deliverome-d1-backups`. Manual trigger via `workflow_dispatch`.
- **Layered recovery** (cloudflare/README.md has the full walkthrough):
  Time Travel (7-30 days, automatic) → R2 dated dumps (CI, durable
  long-term) → on-disk JSON under `data/eval/` and `data/annotations/`
  (canonical source — re-uploadable into a fresh D1).
- **Wrangler is pinned at the repo root** via `/package.json` —
  run `npm ci` from the repo root once to install it under
  `node_modules/.bin/wrangler`. The cloudflare/ scripts call
  `npx --yes wrangler ...` so the pinned version always wins over
  any globally installed wrangler. CI does the same `npm ci`.
- **Node version pin: `.nvmrc` is the source of truth**
  (currently `24.14.1`). It's mirrored at `viewer/.nvmrc` because
  `cd viewer && nvm use` won't walk up the tree. Workflows read it via
  `node-version-file:` so CI never drifts from local dev. The
  `engines.node` field in `package.json` (root) and `viewer/package.json`
  uses `^24` as a *floor* assertion (`engine-strict=true` in `viewer/.npmrc`
  promotes the engines mismatch from warn to error). The
  `viewer/@types/node` dep tracks the same major.
- **`NODE_VERSION` on Cloudflare Pages lives outside the repo.** Set it
  to the same value as `.nvmrc` (Settings → Environment Variables →
  Production + Preview). **When bumping Node anywhere here, always
  remind the user to bump `NODE_VERSION` on Cloudflare Pages in the
  same change.** Skipping it means the Pages build either keeps using
  the old Node (silent drift) or falls through to Cloudflare's rolling
  default (which can shift under you).
- **`viewer/.npmrc` hardening** (per lirantal/npm-security-best-practices):
  - `engine-strict=true` — refuse `npm install` on wrong Node major
  - `audit-level=high` — `npm audit` (and implicit audit) exits non-zero on high+
  - `min-release-age=7` — quarantine: refuse to install package versions
    published in the last 7 days. Defense against fresh supply-chain
    attacks (see Mini Shai-Hulud, 2026-05-12). As of npm 11.11.0 this
    config is defined but not yet wired into resolution (no-op today,
    activates automatically when npm completes the wiring, likely
    11.12+). For new dep additions today, use `npm run safe-add
    <package>` (in `viewer/`) — that script enforces the cooldown via
    the working `--before` CLI flag.
  - `viewer/package.json` `overrides.postcss` — pins all transitive
    postcss to the patched line, regardless of what `next` declares.
- **`next` is pinned to an exact canary version** (`16.3.0-canary.11`)
  in `viewer/package.json` because every stable 16.x through 16.2.6
  is in the vulnerable range for ~13 GHSA high-severity advisories
  (Server Component DoS, RSC cache poisoning, middleware/proxy
  bypasses, etc.). The fix is in 16.3 canary. **Bump to `^16.3.0`
  once Next 16.3.0 ships stable** — CI's `npm audit --audit-level=high`
  step will then continue to pass.
- **Required CI secrets** (one-time): `CLOUDFLARE_API_TOKEN` (D1:Edit
  + R2:Edit) and `CLOUDFLARE_ACCOUNT_ID`. The R2 bucket itself is
  provisioned locally via `npx --yes wrangler r2 bucket create deliverome-d1-backups`.

When editing the D1 schema or adding a new uploader path, add it to
the workflow's `paths:` filter so CI catches the change.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
