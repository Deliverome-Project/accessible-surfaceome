# CLAUDE.md

This file provides guidance to Claude Code for this repository.

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

## Managed Agents — auto-sync on drift

The `surface_triage` and `surface_annotator` agents are **Anthropic Managed Agents** — Anthropic stores its own snapshot of each agent's system prompt + tool list + model. The remote snapshot is the source of truth at run time.

**Auto-sync is wired into the annotator orchestrator.** When `annotate` runs, it sha-checks the local `system.md` against `.runs/agents-registry.json`; on drift it calls `sync_agent_and_environment(client)` inline before the first model call. The sync is a single idempotent metadata round-trip (no model call, no extra spend). You no longer need to remember `agents sync` after editing:

- any `src/accessible_surfaceome/agents/surface_annotator/prompts/*.md`
- the agent payload in `src/accessible_surfaceome/agents/surface_annotator/agent.py`
- the `SurfaceomeRecord` / `SurfaceomeRecordDraft` schema in `src/accessible_surfaceome/tools/_shared/models.py` (when the prompt references the new shape)

`uv run accessible-surfaceome agents sync` still works as a manual command for cases where you want to push prompt changes without triggering a full annotate run (CI, schema-only edits, dry-run verification).

**Escape hatch.** Set `ANNOTATE_NO_AUTO_SYNC=1` in the environment to disable auto-sync — the orchestrator falls back to the historical loud `PROMPT DRIFT` warning and runs against the stale remote prompt. Use this on experimental branches that should NOT push their prompt to the production-registered managed agent.

The registry is local (per-worktree, gitignored under `.runs/`) so each worktree tracks its own remote agent version. surface_triage runs through a different code path and doesn't use the Managed Agent registry, so it's not part of the auto-sync.

**Why auto-sync matters:** the surface_annotator run is ~$0.30–0.50 on Sonnet 4.6. Burning a run on a stale prompt produces a record that quietly looks like the previous schema version — easy to miss in summary stats, expensive to discover late.

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

## Final-Figure Gist Convention

When a figure is **promoted** to `data/analysis/triage_bench_final/` (or any other `*_final/` analysis directory) it must ship with a GitHub gist for reader-side reproduction. The gist is what gets linked from a Substack / blog post under the figure, since Substack can't host arbitrary CSV/code downloads.

Each gist contains exactly two files:
- `01_<figure_slug>.md` — one-paragraph context, run command, hyperlinks to the canonical data source and the canonical figure generator in the repo. The `01_` prefix forces this file to the top of the gist's alphabetical file list so it acts as a README.
- `make_<figure_slug>.py` — standalone Python reproduction script. Uses **PEP 723 inline-script metadata** (`# /// script ... # ///` header) to declare dependencies so readers run it with `uv run make_<figure_slug>.py` — no `pip install` step.

**Data fetching** — script reads from whichever source is canonical:
- **D1 (preferred when the canonical source is D1)** — script queries the public read-only D1 endpoint via HTTP. Used for figures driven by `triage_run`, `deep_dive_run`, `resolver_context_version`, etc.
- **Canonical TSV at `raw.githubusercontent.com`** — when the figure's data lives in a `data/processed/**.tsv` in the public repo, fetch it directly via the raw URL pinned to `main` (or a commit SHA for stronger immutability). **The TSV must be non-LFS** (LFS pointers don't resolve over the raw URL) and the repo must be public — add a `-filter -diff -merge text` exemption in `.gitattributes` to un-LFS any small canonical TSV the gists depend on.

Do not bundle a CSV in the gist unless the canonical source is unreachable (private repo, D1 without a public endpoint). Keep the gist as a thin wrapper around the canonical data.

**Visibility:** create as **secret** by default — `gh gist create 01_<slug>.md make_<slug>.py -d "<short desc>"` (omit `--public`). Secret gists are unguessable-URL only (not listed on your profile, not searchable), which is the right default for Substack-linked downloads. Flip to public via the web UI when discoverability is the goal; **public → secret is not reversible** (only delete-and-recreate). Always confirm with the user before publishing.

Record the gist URL in the canonical generator's module docstring under a `# Reproduction:` line so readers can find it from the source script. The on-repo plotting script remains the source of truth; the gist is the readers' minimal-dependency mirror.

## Web Viewer

`viewer/` is a **standalone Next.js 16 app** that ships as its own
Cloudflare Pages project at **`surfaceome.deliverome.org`**. It is *not*
a sub-route of `deliverome.org`'s main site — separate build, separate
deploy target, separate domain.

The design language is borrowed from
`Deliverome-Project/deliverome-internal` PR #24 (Rosy Maroon: Maroon ·
Teal · Amber · Lavender; Manrope + Playfair Display via
`next/font/google`; PascalCase component dirs with `.module.css`; type
primitives `.h-display` / `.h-section` / `.lede` / `.label-mono` from
`app/globals.css`). Tokens are mirrored at
`viewer/app/design-tokens.css` — they have to be re-synced manually
when the deliverome.org system rev's.

Data: `viewer/public/data/surfaceome/{SYMBOL}.json` is the static
deploy artifact (also reachable as
`https://surfaceome.deliverome.org/data/surfaceome/{SYMBOL}.json`).
The page bodies read those JSONs via `fs` at build time and SSG every
gene through `generateStaticParams`. When the public Worker at
`api.deliverome.org/surfaceome/v1/*` is live (source in
`cloudflare/workers/surfaceome_api/`, bound to the `surfaceome_public`
D1 mirror), the loader at `viewer/lib/surfaceome.ts` can swap `fs` for
`fetch()` — same record shape.

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
- **Upload**: `scripts/upload_triage_runs_to_d1.py` after a runner
  produces per-cell JSON records.
- **Verify**: `scripts/d1_triage_verify.py` reconciles D1 vs on-disk
  JSON; exits non-zero on divergence.
- **Backup to R2** is CI-driven: `.github/workflows/d1-backup.yml`
  runs `scripts/d1_export_to_r2.sh` on every push to `main` that
  touches `cloudflare/d1_schema.sql`, `data/eval/triage_subbench_v1/**`,
  `data/annotations/**`, `data/triage/**`, the uploader code, or the
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
- **Required CI secrets** (one-time): `CLOUDFLARE_API_TOKEN` (D1:Edit
  + R2:Edit) and `CLOUDFLARE_ACCOUNT_ID`. The R2 bucket itself is
  provisioned locally via `npx --yes wrangler r2 bucket create deliverome-d1-backups`.

When editing the D1 schema or adding a new uploader path, add it to
the workflow's `paths:` filter so CI catches the change.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
