# `scripts/`

Standalone data builders, one-shot migrations, audits, figure builders, and the release ritual — about 134 scripts, in a **flat** directory. Run any with `uv run python scripts/<name>.py` (shell scripts with `bash`). This index lists the entry points you'll actually use, plus the naming scheme for everything else.

## Entry points

| Script | What it does |
|---|---|
| `surfaceome_v2_annotate.py <GENE>` | Deep-dive one gene end-to-end (publishes to D1). |
| `triage_runner.py --model … --d1` | Run the triage benchmark / genome-wide sweep. |
| `build_candidate_universe_v3.py` | Rebuild the M1 candidate universe from the five sources. |
| `build_figure_tsvs.py`, `build_figure_index.py` | Rebuild the per-figure bundled TSVs and `paper/figure_index.md`. |
| `build_positive_control_lists.py` | Rebuild the ADC / TCE / ViralZone positive-control sets. |
| `release/` | Citable-snapshot release ritual — see [`scripts/release/README.md`](release/README.md). |
| `check-py.sh` | Local CI gate (ruff + ty + pytest). |

## Naming scheme (everything else)

- **`build_*`** (15) — derive datasets and tables.
- **`make_*`** (0) — figure renderers, mirrored by `data/analysis/figures/make_*.py` (kept in sync by a guard test).
- **`backfill_*`** (13) — one-shot D1/data migrations, already run; kept for provenance.
- **`audit_*`** (7) / **`probe_*`** (4) — validation and diagnostics (mostly $0, no model calls).
- **`upload_*` / `sync_*` / `apply_*`** — publish to D1 / apply Cloudflare edge rules.

Most non-entry-point scripts are internal one-shots; prefer the entry points above unless you're reproducing a specific build step.
