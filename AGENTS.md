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

## Managed Agents — push prompt + schema edits before annotating
The `surface_triage` and `surface_annotator` agents are **Anthropic Managed Agents** — Anthropic stores its own snapshot of each agent's system prompt + tool list + model. That remote snapshot is the source of truth at run time. Editing a file under `src/accessible_surfaceome/agents/<name>/prompts/system.md` does **NOT** push the change; `annotate` and `triage` will keep running against the previously-registered prompt.

**Always run `uv run accessible-surfaceome agents sync` after editing:**
- any `src/accessible_surfaceome/agents/*/prompts/*.md`
- the agent payload in `src/accessible_surfaceome/agents/*/agent.py` (model, tool list, etc.)
- the SurfaceomeRecord / SurfaceomeRecordDraft schema in `src/accessible_surfaceome/tools/_shared/models.py` if the prompt references the new shape

`agents sync` is cheap (one metadata round-trip per agent, no model call) and idempotent — it diffs the local `system.md` sha256 against `.runs/agents-registry.json` and `PATCH`es the agent only when the sha changed. The registry is local (per-worktree, gitignored under `.runs/`) so each worktree tracks its own remote agent version.

If you skip sync, the orchestrator logs a loud `PROMPT DRIFT` warning at the start of every run, naming the stale sha and pointing at the sync command. It does not fail the run — but the run will use the **stale** prompt and may emit a degraded (older-schema-shape) record, wasting model spend. The annotator run is ~$0.30–0.50 on Sonnet 4.6 per gene, so burning a sweep on a stale prompt is expensive.

## Agent Command Allowlist
- Codex and Claude agents may run `uv run python <module-or-script> [args...]` for repo analyses and processing.
- Prefer `uv run ...` over bare `python ...`.

## Worktrees, Env, and Data Hydration
- Claude Code and Codex App may create their own worktrees; do not assume repo scripts control worktree creation.
- After entering an agent-created worktree, run `scripts/bootstrap-worktree.sh none` unless the task needs data.
- Use `scripts/bootstrap-worktree.sh candidate` for candidate-universe data, or `scripts/bootstrap-worktree.sh all` only when all data artifacts are needed.
- `.env` is gitignored and should be symlinked from the canonical local checkout or `ACCESSIBLE_SURFACEOME_ENV_SOURCE`; never commit `.env`. The CLI loads it from the repo root at startup with shell-env precedence; see `.env.example` for documented keys (`ANTHROPIC_API_KEY`, `NCBI_API_KEY`).
- Run `git lfs fsck` only after full data hydration.

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

## Final-Figure Gist Convention

When a figure is **promoted** to `data/analysis/triage_bench_final/` (or any other `*_final/` analysis directory) it must ship with a GitHub gist for reader-side reproduction. The gist is what gets linked from a Substack / blog post under the figure, since Substack can't host CSV/code downloads.

Each gist contains exactly two files:
- `01_<figure_slug>.md` — one-paragraph context, run command, hyperlinks to the canonical data source and figure generator. The `01_` prefix forces it to the top of the gist's alphabetical file list.
- `make_<figure_slug>.py` — standalone Python reproduction script. Uses **PEP 723 inline-script metadata** (`# /// script ... # ///` header) to declare deps so readers run it with `uv run make_<figure_slug>.py` — no `pip install` step.

**Data fetching** — script reads from whichever source is canonical:
- **D1 (preferred when canonical source is D1)** — query the public read-only D1 endpoint via HTTP.
- **Canonical TSV at `raw.githubusercontent.com`** — when the figure's data lives in `data/processed/**.tsv` in the public repo, fetch directly via raw URL pinned to `main` (or a commit SHA for immutability). **The TSV must be non-LFS** (LFS pointers don't resolve over raw URLs) and the repo must be public — add a `-filter -diff -merge text` exemption in `.gitattributes` to un-LFS any small canonical TSV the gists depend on.

Do not bundle a CSV in the gist unless the canonical source is unreachable.

**Visibility:** create as **secret** by default — `gh gist create 01_<slug>.md make_<slug>.py -d "<short desc>"` (omit `--public`). Secret gists are unguessable-URL only. Flip to public via the web UI when discoverability is the goal; **public → secret is not reversible**. Always confirm with the user before publishing.

Record the gist URL in the canonical generator's module docstring under a `# Reproduction:` line. The on-repo plotting script remains the source of truth; the gist is the readers' minimal-dependency mirror.

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
- **Upload**: `scripts/upload_triage_runs_to_d1.py` after any sweep
  produces per-cell JSON records under `data/eval/triage_subbench_v1/`.
- **Verify**: `scripts/d1_triage_verify.py` reconciles D1 vs on-disk
  JSON; exits non-zero on divergence.
- **CI backup → R2**: every push to `main` that touches the relevant
  paths (`cloudflare/d1_schema.sql`, `data/eval/triage_subbench_v1/**`,
  `data/annotations/**`, `data/triage/**`,
  `src/accessible_surfaceome/cloud/**`, the uploader / backup scripts
  themselves) triggers `scripts/d1_export_to_r2.sh`, which runs
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
