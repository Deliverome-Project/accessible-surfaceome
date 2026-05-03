# Repository Guidelines

Concise contributor guide for `accessible-surfaceome`.

## Project Structure & Organization
- `src/accessible_surfaceome/` core package.
- `src/accessible_surfaceome/candidates/` candidate-universe builders and data-source integration.
- `data/raw/` source workbooks.
- `data/external/` downloaded datasets + traceability manifests.
- `data/processed/` normalized outputs and candidate universe tables.
- `data/analysis/` analytical exports and figures.
- `docs/` plans and reports.
- `README.md`, `CLAUDE.md`, `AGENTS.md` for operational guidance.

## Build, Test, and Development Commands
- Install deps: `uv sync`
- Run CLI: `uv run accessible-surfaceome build`
- Run module directly: `uv run python -m accessible_surfaceome.candidates.merge`
- Run checks: `bash scripts/check-py.sh`
- Run type checking: `uv run ty check`
- Run tests: `uv run pytest -q`
- Run hooks: `uv run pre-commit run --all-files --config .pre-commit-config.yaml`

## Agent Command Allowlist
- Codex and Claude agents may run `uv run python <module-or-script> [args...]` for repo analyses and processing.
- Prefer `uv run ...` over bare `python ...`.

## Coding Style & Naming Conventions
- Python 3.11+.
- Use docstrings and clear function boundaries.
- Prefer explicit error messages for missing files/columns in data workflows.
- Keep outputs reproducible from scripts.

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

## Doc Sync Rule
- Keep `AGENTS.md` and `CLAUDE.md` aligned when workflow guidance changes.
