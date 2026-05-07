# Repository Guidelines

Concise contributor guide for `accessible-surfaceome`.

## Project Structure & Organization
- `src/accessible_surfaceome/` core package.
- `src/accessible_surfaceome/sources/` per-source download + build modules (`uniprot.py`, `go.py`, `surfy.py`, `cspa.py`, `deeptmhmm.py`, `hpa.py`, `compartments.py`); shared infra in `sources/_support/`.
- `src/accessible_surfaceome/merge/` candidate-universe orchestration (loaders, normalization, gene-symbol resolution).
- `src/accessible_surfaceome/audit/` audit + figure scripts.
- `src/accessible_surfaceome/tools/` per-machine install plumbing (not part of the data pipeline).
- `viewer/` Vite + React + TypeScript SPA — per-gene record viewer, deploys to Cloudflare Pages.
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
- Build viewer: `cd viewer && npm install && npm run build`
- Run viewer dev server: `cd viewer && npm run dev` (http://localhost:5173)

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
