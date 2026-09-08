# Contributing

Thanks for your interest in this project. This file covers the setup, the checks that must pass, and where things live.

For what the project *is* and how to use it, start with the [README](README.md). For data-source licence terms, see [LICENSING.md](LICENSING.md).

## Setup

```bash
uv sync                  # Python environment (uv is required)
cp .env.example .env     # add ANTHROPIC_API_KEY; NCBI keys raise rate limits
./scripts/setup-git-hooks.sh
```

Cloudflare variables in `.env` are only needed for scripts that read or write D1/R2. Analysis, figure, and annotation work runs without them.

## The check that has to pass

One script runs everything CI runs:

```bash
./scripts/check-py.sh
```

It runs `ruff check` over `src tests scripts`, `ty check`, `compileall`, the full `pytest` suite, and `check_viewer_types_sync.py`, which verifies the viewer's TypeScript interfaces still cover every field on the Pydantic models. Run it before opening a PR. CI runs the same thing plus `pre-commit run --all-files`.

Pre-commit hooks cover formatting, YAML/TOML/JSON validity, merge-conflict markers, the viewer type sync, and three safety hooks: `detect-private-key`, `forbid-env-files`, and `scan-secrets`. Never commit a real `.env`.

## Pull requests

`main` and `dev` are both protected, so work on a branch and open a PR.

PR titles are linted as conventional commits. Allowed types are `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, and `chore`. A scope is optional; if you use one it must be from `surface-proteome`, `sources`, `merge`, `audit`, `agents`, `tools`, `data`, `docs`, `ci`, `deps`, or `viewer`.

## Where things live

| Path | What's in it |
|---|---|
| `src/accessible_surfaceome/` | The library: agents, merge logic, models, cloud clients |
| `scripts/` | Entry points at the root; everything else grouped by role |
| `tests/` | Pytest suite |
| `viewer/` | Next.js site |
| `cloudflare/` | Worker source, D1 schemas, deploy notes |
| `data/` | Inputs and derived artifacts (mostly git-LFS) |
| `paper/`, `docs/` | Manuscript assets and design notes |

Inside `scripts/`, the root holds the entry points you actually invoke. The rest are grouped into `figures/`, `build/`, `audit/`, `cloud/`, `probes/`, `tsv-export/`, `release/`, `precommit/`, and `archive/` for finished one-shots. See [scripts/README.md](scripts/README.md).

## Two things that surprise people

**Figure scripts are mirrored.** Each figure has a canonical generator in `scripts/figures/<slug>.py` and a standalone gist mirror in `data/analysis/figures/make_<slug>.py`. Guard tests assert the pair stays in sync, so edit both or the suite fails.

**The Worker does not auto-deploy.** Merging a change under `cloudflare/workers/` does not ship it. Deploy explicitly with `wrangler deploy` from the Worker directory.

## Data and reproducibility

`data/raw`, `data/external`, `data/processed`, and `data/analysis` are tracked with git-LFS, with targeted exemptions so small provenance files stay readable as normal blobs. Install `git-lfs` before cloning if you need the underlying data.

Every published figure is also deposited as a gist bundling its data and script, indexed by `data/analysis/figures/figure_swhids.json`, so a figure can be reproduced without cloning the repository.
