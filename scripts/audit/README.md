# scripts/audit/

Read-only analysis + drift-detection scripts. The `audit_*` scripts examine
production records (D1, in-tree TSVs, on-disk JSON) for anomalies. The
`check_*` scripts gate commits via `.pre-commit-config.yaml` — they assert
that schema fingerprints, triage coverage, and viewer-type sync invariants
still hold. `gen_prompt_review.py` regenerates `docs/prompt_review.html`
after any agent-prompt edit (must run in the same commit per CLAUDE.md).
