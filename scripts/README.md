# scripts/

Top-level scripts in this directory are **canonical entry points** for
production sweeps. Sub-directories group the supporting build / upload /
audit pipeline by function so a scientist landing on the repo can find
the right script in seconds.

| Entry point | What it does |
|---|---|
| `triage_runner.py` | Genome-wide triage sweep against the candidate universe |
| `surfaceome_v2_annotate.py` | Per-gene deep-dive annotation (full v2 record) |
| `deep_dive_sweep.py` | Cohort orchestrator for parallel deep-dive batches |
| `surfaceome_v2_replay_builders.py` | Replay individual v2 block builders (cheap prompt iteration) |
| `bootstrap-worktree.sh` | Hydrate a fresh worktree per CLAUDE.md guidance |
| `check-py.sh` | ruff + ty + compile + pytest |
| `setup-git-hooks.sh`, `precommit` | Local hook plumbing |
| `d1_export_to_r2.sh`, `d1_triage_backup.sh` | Backup D1 → R2 |

| Subdir | What's in it |
|---|---|
| `build/` | Data acquisition + build steps (`fetch_*`, `build_*`, `compute_*`, `run_*_sweep`) |
| `upload/` | Sync derived artifacts to D1 + R2 + figure gists |
| `figures/` | Canonical figure generators (paired with `data/analysis/figures/make_*.py` mirrors) |
| `audit/` | Read-only audits, schema-fingerprint drift detection, prompt-review regen |
| `cloud/` | Cloudflare edge config + public-Worker TSV exports |
| `tsv-export/` | Augment public TSVs with stable IDs |
| `probes/` | $0 validation probes (no model calls) |
| `release/` | Release packaging (Zenodo deposit chain) |
| `archive/` | Completed one-shot scripts kept for provenance — do NOT re-run unmodified |

For details on each script's inputs/outputs, run the script with `--help`
or read the module docstring.
