# CLAUDE.md

This file provides guidance to Claude Code for this repository.

## Project Overview

`accessible-surfaceome` is a standalone surface-proteome annotation workspace sourced from `deliverome-internal/analyses/surface-proteome`.

Current implementation focus: candidate-universe builders (M1).

## Repository Structure

- `src/surface_proteome/` core package
- `src/surface_proteome/candidates/` source download/build/merge modules
- `data/raw/`, `data/external/`, `data/processed/`, `data/analysis/`
- `docs/` plans/reports

## Setup

```bash
uv sync
```

## Common Commands

```bash
uv run accessible-surfaceome build
uv run python -m surface_proteome.candidates.merge
bash scripts/check-py.sh
uv run pytest -q
```

## Quality Checks

- `bash scripts/check-py.sh` runs ruff + compile + pytest.
- Use `uv run pre-commit run --all-files --config .pre-commit-config.yaml` before PR.

## Agent Command Allowlist

- Agents may run `uv run python ...` commands for repository modules/scripts.

## Git Hooks

- Enable hooks with `./scripts/setup-git-hooks.sh`.

## CI

- CI workflow: `.github/workflows/ci.yml`
- Runs `uv sync --frozen`, `uv lock --check`, `bash scripts/check-py.sh`.

## Doc Sync Rule

Keep `CLAUDE.md` and `AGENTS.md` aligned when guidance changes.
