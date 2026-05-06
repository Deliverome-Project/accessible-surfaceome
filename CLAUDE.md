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
- **Allowed scopes**: `surface-proteome`, `sources`, `merge`, `audit`, `tools`, `data`, `docs`, `ci`, `deps`.
- **Pick a scope by what the PR mostly touches**: `sources/` → `sources`,
  `merge/` → `merge`, `audit/` → `audit`, `tools/` (custom-tool handlers, including the
  surface-annotator agent that calls them) → `tools`, dependency bumps → `deps`,
  CI workflows → `ci`, project-wide / cross-cutting → `surface-proteome`. If you
  need a scope that isn't listed, update the workflow's `scopes:` block in the
  same PR — don't invent a new one.

## Coding Style

See [docs/coding-style.md](docs/coding-style.md) for the conventions we
hold code to and the short rubric for assessing diffs.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
