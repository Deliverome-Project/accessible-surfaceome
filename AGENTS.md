# Repository Guidelines

Concise contributor guide for `accessible-surfaceome`.

## Project Structure & Organization
- `src/accessible_surfaceome/` core package.
- `src/accessible_surfaceome/sources/` per-source download + build modules (`uniprot.py`, `go.py`, `surfy.py`, `cspa.py`, `deeptmhmm.py`, `hpa.py`, `compartments.py`); shared infra in `sources/_support/`.
- `src/accessible_surfaceome/merge/` candidate-universe orchestration (loaders, normalization, gene-symbol resolution).
- `src/accessible_surfaceome/audit/` audit + figure scripts.
- `src/accessible_surfaceome/tools/` per-machine install plumbing (not part of the data pipeline).
- `viewer/` Next.js 16 app — **standalone Cloudflare Pages project deployed at `surfaceome.deliverome.org`**. Design tokens mirrored from `Deliverome-Project/deliverome-internal` PR #24 (Rosy Maroon system); manual sync.
- `data/raw/` source workbooks.
- `data/external/` downloaded datasets + traceability manifests.
- `data/processed/` normalized outputs and candidate universe tables.
- `data/analysis/` analytical exports and figures.
- `docs/` plans and reports.
- `README.md`, `CLAUDE.md`, `AGENTS.md` for operational guidance.

## Build, Test, and Development Commands
- Install deps: `uv sync`
- Run CLI: `uv run accessible-surfaceome build`
- Run module directly: `uv run python -m accessible_surfaceome.merge`
- Run checks: `bash scripts/check-py.sh`
- Run type checking: `uv run ty check`
- Run tests: `uv run pytest -q`
- Run hooks: `uv run pre-commit run --all-files --config .pre-commit-config.yaml`
- Run viewer dev server: `cd viewer && npm install && npm run dev` (http://localhost:3000)
- Build viewer for Pages: `cd viewer && npm run build` → `viewer/out/` (static export)
- Deploy viewer: `cd viewer && npm run deploy` (or via Cloudflare Pages CI on push)

## Managed Agents — auto-sync on drift
The `surface_triage` and `surface_annotator` agents are **Anthropic Managed Agents** — Anthropic stores its own snapshot of each agent's system prompt + tool list + model. The remote snapshot is the source of truth at run time.

**Auto-sync is wired into the annotator orchestrator.** On every `annotate` run it sha-checks the local `system.md` against `.runs/agents-registry.json`; on drift it calls `sync_agent_and_environment(client)` inline before the first model call. The sync is a single idempotent metadata round-trip (no model call, no extra spend). Editing any of these no longer requires a manual sync:
- `src/accessible_surfaceome/agents/surface_annotator/prompts/*.md`
- the agent payload in `src/accessible_surfaceome/agents/surface_annotator/agent.py`
- the `SurfaceomeRecord` / `SurfaceomeRecordDraft` schema in `src/accessible_surfaceome/tools/_shared/models.py` when the prompt references the new shape

`uv run accessible-surfaceome agents sync` still works as a manual command (useful for CI, schema-only edits, dry-run verification).

**Escape hatch.** Set `ANNOTATE_NO_AUTO_SYNC=1` in the environment to disable auto-sync — the orchestrator falls back to the historical loud `PROMPT DRIFT` warning and runs against the stale remote prompt. Use on experimental branches that shouldn't push their prompt to the production-registered managed agent.

The registry is local (per-worktree, gitignored under `.runs/`). surface_triage runs through a different code path and doesn't use the Managed Agent registry, so it's not part of auto-sync.

**Why auto-sync matters:** the surface_annotator run is ~$0.30–0.50 on Sonnet 4.6 per gene. Burning a sweep on a stale prompt produces records that quietly look like the previous schema version — expensive to discover late.

## Agent Command Allowlist
- Codex and Claude agents may run `uv run python <module-or-script> [args...]` for repo analyses and processing.
- Prefer `uv run ...` over bare `python ...`.

## Worktrees, Env, and Data Hydration
- Claude Code and Codex App may create their own worktrees; do not assume repo scripts control worktree creation.
- After entering an agent-created worktree, run `scripts/bootstrap-worktree.sh none` unless the task needs data.
- Use `scripts/bootstrap-worktree.sh candidate` for candidate-universe data, or `scripts/bootstrap-worktree.sh all` only when all data artifacts are needed.
- `.env` is gitignored and should be symlinked from the canonical local checkout or `ACCESSIBLE_SURFACEOME_ENV_SOURCE`; never commit `.env`. The CLI loads it from the repo root at startup with shell-env precedence; see `.env.example` for documented keys (`ANTHROPIC_API_KEY`, `NCBI_API_KEY`).
- Run `git lfs fsck` only after full data hydration.

## Gene identifier resolution

When writing any code that takes "a gene" as input — agent tool, sweep
runner, figure generator, manual one-off — **the entry point must be a
stable identifier, not a gene symbol.** Bare gene symbols silently
resolve to the wrong protein for ~0.2% of human genes (~45 of 19k),
including COX1 (cyclooxygenase vs the mitochondrial cytochrome c
oxidase the cohort actually meant) and WAS (Wiskott-Aldrich protein vs
the MT-RNR1 rRNA gene). See
[`scripts/audit_resolver_hgnc_id_v3.py`](scripts/audit_resolver_hgnc_id_v3.py)
for the audit pattern + the per-symbol divergence list at
`data/analysis/resolver_definitive_audit_v3.tsv`.

### Canonical resolver
- [`src/accessible_surfaceome/tools/gene_lookup.py:resolve_by_hgnc_id`](src/accessible_surfaceome/tools/gene_lookup.py)
  is the preferred entry point. Cohort-driven code calls it with
  `resolve_by_hgnc_id(row["hgnc_id"], http=http)`. The cohort file
  carries `hgnc_id` for every gene (100% coverage).
- Legacy `resolve(symbol_or_acc)` stays for free-text agent tool calls;
  it emits a `UserWarning` on the symbol path so misuse is auditable.

### Stable-ID cache in D1
Every gene's resolved (uniprot_acc, ensembl_gene, ncbi_gene_id,
ensembl_canonical_protein) is materialized in D1's `gene_identifier`
table (private) / `gene_identifier_public` (Worker mirror). Downstream
tools query this directly:

    SELECT uniprot_acc, ensembl_gene, ncbi_gene_id
    FROM gene_identifier_public WHERE hgnc_id = ?;

so they don't re-resolve from symbol. Rebuilt with
`scripts/build_gene_identifier_table.py` after resolver or cohort
changes; `resolver_version` column lets consumers detect staleness.

### Downstream-identifier-per-source rule
| Source | Identifier |
|---|---|
| AlphaFold DB / PDB / InterPro / Pfam / DrugBank / Reactome (protein) | `uniprot_acc` |
| Ensembl / GTEx / HPA / Open Targets / STRING (gene) | `hgnc_id` or `ensembl_gene` |
| PubMed / Europe PMC (free text) | OR of `aliases + previous_symbols + hgnc_symbol` |
| dbSNP / ClinVar / OMIM | `ncbi_gene_id` or `hgnc_id` |

Symbol-keyed queries to structured databases reintroduce the same bug
class one layer down — don't.

Regression tests at
[`tests/test_gene_lookup_resolver.py`](tests/test_gene_lookup_resolver.py)
pin BBC3, ND4, PRNP, TSPO, ABHD4, HSD17B8, SACK1A, CLMB, COX1, COX2,
WAS — any picker / fallback regression breaks these.

## Working with the D1 databases

Two D1s: `surfaceome_agents` (private, full reasoning + costs) and
`surfaceome_public` (column-whitelisted mirror the Worker reads).
Schemas: [`cloudflare/d1_schema.sql`](cloudflare/d1_schema.sql) and
[`cloudflare/d1_public_schema.sql`](cloudflare/d1_public_schema.sql).

### Query from Python

`accessible_surfaceome.cloud.d1_client.D1Client` speaks Cloudflare's
REST API directly — no wrangler needed. Auth pulls from `.env`
(`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`):

    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env
    load_env()
    with D1Client() as d1:
        rows = d1.query("SELECT uniprot_acc FROM gene_identifier WHERE hgnc_id = ?;", ["HGNC:1234"])

D1's HTTP API doesn't accept multi-statement batches; submit one
statement per `query()` call (loop for bulk loads).

### Applying DDL when wrangler isn't available

Use `D1Client.query()` per `CREATE TABLE` / `CREATE INDEX`
statement:

    statements = ["CREATE TABLE ...;", "CREATE INDEX ...;"]
    with D1Client() as d1:
        for s in statements: d1.query(s, [])

### Key tables

| Table | Purpose | Primary lookup |
|---|---|---|
| `gene_identifier` | Stable-ID cache (per-gene canonical IDs). **Read here before re-resolving anything.** | `hgnc_id`, `hgnc_symbol`, `uniprot_acc` |
| `triage_run` | Per-cell triage records. | `(run_id, gene_symbol, model, prompt_variant, replicate)` |
| `deep_dive_run` | Surface-annotator deep-dive records. | `(run_id, gene_symbol)` |
| `candidate_universe_public` | Catalog index. | `(universe_version, gene_symbol, uniprot_acc)` |
| `benchmark_version` | Bench-snapshot symbol pinning. | `(bench_version, gene_symbol)` |

### `run_id` conventions

- `genome_full_sonnet_ncbi_v1` — canonical 2026-05-12 Sonnet sweep.
- `*__resolver_v3_fix` suffix — corrected re-runs that supersede a
  parent run for affected cells (originals preserved). Analytics
  that should reflect the fix must COALESCE-prefer the fix run
  over its parent; see CLAUDE.md for the canonical query.

## Coding Style & Naming Conventions
See [docs/coding-style.md](docs/coding-style.md) for the full conventions
and the rubric we use to assess diffs. Quick summary: Python 3.11+,
ruff-formatted, names that describe what's there, one way to do common
things (paths, traceability), validate at boundaries only, no plumbing
masquerading as algorithm.

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
git add data/processed/triage_bench/mainbench_canonical_v1.tsv
git commit -m "chore(triage): refresh canonical TSV from public D1"
```

CI doesn't enforce that figure scripts only read from `BASE` (raw GitHub) — flag any new `make_*.py` that reaches into the API or a private path during review.

**At publication:** swap `BRANCH = "main"` for a pinned commit SHA in every figure script + gist, register the figure files on Zenodo, and update each gist's README to cite the Zenodo DOI alongside the raw GitHub URL.

## Final-Figure Gist Convention

When a figure is **promoted** to `data/analysis/triage_bench_final/` (or any other `*_final/` analysis directory) it must ship with a GitHub gist for reader-side reproduction. The gist is what gets linked from a Substack / blog post under the figure, since Substack can't host CSV/code downloads.

Each gist contains exactly two files:
- `01_<figure_slug>.md` — one-paragraph context, run command, hyperlinks to the canonical data source and figure generator. The `01_` prefix forces it to the top of the gist's alphabetical file list.
- `make_<figure_slug>.py` — standalone Python reproduction script. Uses **PEP 723 inline-script metadata** (`# /// script ... # ///` header) to declare deps so readers run it with `uv run make_<figure_slug>.py` — no `pip install` step.

**Data fetching** — script reads from whichever source is canonical:
- **D1 (preferred when canonical source is D1)** — query the public read-only D1 endpoint via HTTP.
- **Canonical TSV at `raw.githubusercontent.com`** — when the figure's data lives in `data/processed/**.tsv` in the public repo, fetch directly via raw URL pinned to `main` (or a commit SHA for immutability). **The TSV must be non-LFS** (LFS pointers don't resolve over raw URLs) and the repo must be public — add a `-filter -diff -merge text` exemption in `.gitattributes` to un-LFS any small canonical TSV the gists depend on.

Do not bundle a CSV in the gist unless the canonical source is unreachable.

**Visibility:** create as **public** by default — `gh gist create --public 01_<slug>.md make_<slug>.py -d "<short desc>"`. Figure-reproduction gists are linked from Substack / blog posts; public is the right default for this category. GitHub does NOT allow flipping visibility after creation; pick correctly on first creation. Before creating a new gist for an existing figure, check the saved-memory `figure_gists.md` slug → gist-ID map — duplicates have happened.

Record the gist URL in the canonical generator's module docstring under a `# Reproduction:` line. The on-repo plotting script remains the source of truth; the gist is the readers' minimal-dependency mirror.

**Also embed the gist URL in the artifact itself** via `save_figure(..., gist_url=...)` in `src/accessible_surfaceome/audit/_plotting_config.py`. PNG gets a `Source` tEXt chunk; PDF gets a `Subject` info-field. Reading it back:

- CLI: `exiftool figure.png | grep Source` (Homebrew `brew install exiftool`); also `pngcheck -t figure.png` or ImageMagick's `magick identify -verbose`.
- Python: `from PIL import Image; Image.open("figure.png").info["Source"]`.
- Non-technical reader: drop the PNG into an online EXIF viewer (e.g. exif.tools, exifer.com, onlineexifviewer.com) — they show every text chunk with the keyword name. GIMP's *Image Properties → Comments* also works. macOS Preview's Inspector does **not** show PNG tEXt chunks; GitHub / Slack previews don't either. So the URL is author-side metadata, not something a casual web viewer surfaces.

## Data Rules & Formats
- Keep raw inputs unchanged in `data/raw/`.
- Keep downloaded datasets and traceability artifacts in `data/external/`.
- Write derived outputs to `data/processed/` or `data/analysis/`.
- Prefer TSV/CSV for tabular interchange.

## Large Files & LFS
- Treat large data artifacts (`>=10 MB`) as LFS candidates.
- Update `.gitattributes` for newly introduced large-file patterns.

## Testing Guidelines
- Place tests in `tests/` as `test_*.py`.
- For data scripts, validate required columns and key uniqueness assumptions.

## CI & Checks
- CI runs on PRs and pushes to `main` via `.github/workflows/ci.yml`.
- CI validates lockfile consistency and runs Ruff, ty, compile, and pytest checks.
- `.github/workflows/d1-backup.yml` exports the `surfaceome_agents`
  D1 database to the R2 bucket `deliverome-d1-backups` on every push
  to `main` that touches the D1 schema, the eval data, or the
  uploader code. See **Cloudflare D1 + R2** below.

## Cloudflare D1 + R2 backups for agent runs
- The `surfaceome_agents` D1 database stores every `surface_triage`
  and `surface_annotator` invocation with full reproducibility metadata
  (prompt SHA, benchmark version, schema version, prose reasoning).
  It's separate from the website's `signups` D1. **The Pages binding
  lives in the deliverome main-site repo's `wrangler.toml`** — this
  repo's Python tooling reads / writes via D1's HTTP API and doesn't
  need a Pages binding.
- **Schema**: `cloudflare/d1_schema.sql` — 6 tables (`prompt_version`,
  `benchmark_version`, `triage_run`, `deep_dive_run`,
  `deep_dive_evidence`, `deep_dive_search_log`) plus 3 views. Triage
  and deep-dive share the DB so cross-table joins
  (`triage_vs_deep_dive`) are cheap.
- **Upload**: `scripts/triage_runner.py --d1 --run-id <tag>` streams
  each completed cell into `triage_run` via `D1RunSink` as the sweep
  progresses. No separate batch-upload step. Idempotent on
  `(run_id, gene_symbol, model, prompt_variant, replicate, prompt_sha)`,
  so restarting a crashed sweep with the same `--run-id` skips cells
  that already landed.
- **CI backup → R2**: every push to `main` that touches the relevant
  paths (`cloudflare/d1_schema.sql`, `data/annotations/**`,
  `data/triage/**`, `src/accessible_surfaceome/cloud/**`, the
  backup scripts themselves) triggers `scripts/d1_export_to_r2.sh`,
  which runs
  `wrangler d1 export` and uploads to the R2 bucket
  `deliverome-d1-backups` under a dated key plus a stable
  `latest.sql` pointer.
- **Layered recovery** (cloudflare/README.md has the full walkthrough):
  Time Travel (7-30 days, automatic) → R2 dated dumps (CI, durable
  long-term) → on-disk JSON under `data/eval/` and `data/annotations/`
  (canonical source — re-uploadable into a fresh D1).
- **Wrangler is pinned** at the repo root via `/package.json`
  (devDependency). Run `npm ci` once to install it under
  `node_modules/.bin/`; the cloudflare/ scripts and the CI workflow
  both invoke it as `npx --yes wrangler ...` so the pinned version
  always wins.
- **Node version pin lives in `.nvmrc`** (root + `viewer/.nvmrc`),
  currently `24.14.1`. Workflows read it via `node-version-file:` so
  CI never drifts from local dev. `engines.node: ^24` in both
  `package.json`s acts as a floor and is enforced as an error (not a
  warning) via `engine-strict=true` in `viewer/.npmrc`. `viewer/@types/node`
  tracks the same major. **`NODE_VERSION` build env var on Cloudflare
  Pages lives outside the repo and must be kept in sync with `.nvmrc`
  (Settings → Environment Variables → Production + Preview). When
  bumping Node anywhere here, always remind the user to bump it on
  Cloudflare Pages in the same change.** Skipping it leaves the Pages
  build on the old Node (silent drift) or on Cloudflare's rolling
  default (shifts under you).
- **`viewer/.npmrc` hardening** (per lirantal/npm-security-best-practices):
  `engine-strict=true`, `audit-level=high`, `min-release-age=7`
  (forward-looking; npm 11.11.0 defines but doesn't yet enforce). For
  the cooldown to actually filter today, use `npm run safe-add
  <package>` (in `viewer/`) — that script wraps `npm install` with
  the working `--before=<7-days-ago>` flag.
- **`next` pinned to exact `16.3.0-canary.11`** because stable 16.x
  through 16.2.6 carries ~13 GHSA high-severity advisories with no
  stable fix yet. Bump to `^16.3.0` once Next 16.3.0 ships stable.
- **CI secrets** (one-time, in repo Settings → Secrets and variables
  → Actions): `CLOUDFLARE_API_TOKEN` (scoped D1:Edit + R2:Edit) and
  `CLOUDFLARE_ACCOUNT_ID`. The R2 bucket is provisioned locally via
  `npx --yes wrangler r2 bucket create deliverome-d1-backups`.
- When adding a new data path the DB stores, add it to the
  `paths:` filter in `.github/workflows/d1-backup.yml` so CI catches
  the change and exports a fresh dump.

## Pull Request Conventions
PR titles are validated by `.github/workflows/lint-pr-title.yml` (Conventional
Commits via `amannn/action-semantic-pull-request`). A title that doesn't match
fails the check and blocks merge.

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
- Match the commit-message subject style: terse, imperative, no trailing period.

## Doc Sync Rule
- Keep `AGENTS.md` and `CLAUDE.md` aligned when workflow guidance changes.
