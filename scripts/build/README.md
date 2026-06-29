# scripts/build/

Data acquisition + derived-artifact build steps. Each script fetches an
upstream source or builds a downstream snapshot. Run order generally
follows: `fetch_*` → `build_*` → `compute_*` → `run_*_sweep`. See the
project README for the full data-flow diagram.

Outputs land in `data/external/` (raw) or `data/processed/` (derived).
Re-run `scripts/check-py.sh` after touching any builder to make sure the
schema fingerprints in `tests/version_fingerprints.json` still match.
