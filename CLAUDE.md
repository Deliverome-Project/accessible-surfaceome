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
- `viewer/` Vite + React + TypeScript SPA — per-gene record viewer (Cloudflare Pages)
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
cd viewer && npm install && npm run dev   # web viewer at localhost:5173
```

## Quality Checks

- `bash scripts/check-py.sh` runs ruff + ty + compile + pytest.
- Use `uv run pre-commit run --all-files --config .pre-commit-config.yaml` before PR.

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

## Web Viewer

The `viewer/` subproject is a static SPA. Per-gene records live under
`viewer/public/data/genes/{SYMBOL}.json` and must validate against the
`SurfaceomeRecord` Pydantic schema in
`src/accessible_surfaceome/tools/_shared/models.py`. Detail page route is
`/gene/:symbol`; agent/curl access is `?format=json|md` or the static
`/data/genes/{SYMBOL}.json` URL. See `viewer/README.md` for build + deploy.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
