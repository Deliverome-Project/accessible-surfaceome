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

## Final figures must read from the public API

Every figure promoted to a published gist — and every on-repo generator under `data/analysis/figures/make_*.py` that mirrors one — **must read its data from `api.deliverome.org/surfaceome/v1/*`**, never from `raw.githubusercontent.com/.../*.tsv` or a local TSV path. The canonical predictions TSV (`data/processed/triage_bench/mainbench_canonical_v1.tsv`) and its exporter (`scripts/export_mainbench_to_tsv.py`) were removed on 2026-05-15 once the API became the single source of truth; data now flows private D1 → `scripts/sync_public_d1.py` → `triage_run_public` → `/v1/triage/export.tsv`.

Why:
- **One source of truth.** `triage_run_public` carries every column the figures need, including `cost_usd` and per-call token counts (as of 2026-05-15 — see the schema change at [cloudflare/d1_public_schema.sql](cloudflare/d1_public_schema.sql)). There's no second artifact to drift against.
- **No "TSV got committed but D1 wasn't synced" drift.** Before the policy change, the mainbench D1 sync was 68 rows short of the TSV and the SurfaceBench page silently showed empty cells for two LLM variants. Pinning figures to the API forces both halves of the contract to stay in lockstep — if the API is short, the figure renders short, you notice, you fix the sync.
- **Cost data is now public.** The original policy stripped `cost_usd` + tokens from public D1, which made `make_benchmark_cost_vs_accuracy.py` unreproducible without private credentials. That's reversed; cost data flows through, the figure is reproducible from `/v1/triage/export.tsv`.

The three endpoints final figures pull from:
- **`GET /v1/triage/export.tsv?run_id=<run>&replicate=<n>`** — long-format TSV (gene/model/variant/replicate + verdict/reason/confidence + the 5 cost+token columns + n_web_searches + latency_s). Default `run_id=mainbench_canonical_v1`, default `replicate` unset (returns every replicate).
- **`GET /v1/benchmark/export.tsv`** — 7-column TSV of curated truth labels (gene/uniprot/class/verdict/signal/reason/rationale).
- **`GET /v1/catalog`** — genome-wide per-DB-vote matrix + latest triage verdict; drives whole-proteome figures.

CI doesn't enforce the "API-only" rule yet — flag any new `make_*.py` that imports a TSV path or fetches `raw.githubusercontent.com` during review. The truth-labels TSV at `data/eval/triage_benchmark_v1.tsv` stays committed because it's the *input* to the benchmark upload, but figures still read truth labels via `/v1/benchmark/export.tsv` rather than that file.

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
