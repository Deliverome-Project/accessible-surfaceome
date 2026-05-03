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

## Git Hooks

- Enable hooks with `./scripts/setup-git-hooks.sh`.

## CI

- CI workflow: `.github/workflows/ci.yml`
- Runs `uv sync --frozen`, `uv lock --check`, `bash scripts/check-py.sh`.

## Coding Style

See [docs/coding-style.md](docs/coding-style.md) for the conventions we
hold code to and the short rubric for assessing diffs.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
