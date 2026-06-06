# v2 Deterministic-Feature Backfill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the ortholog / paralog / isoform / canonical-topology deterministic-feature D1 tables for the genome-wide v2 `yes`/`contextual` genes, so a later v2 deep-dive run renders full records (and add an explicit "checked, none found" sentinel so genuine absence is distinguishable from not-computed).

**Architecture:** This is a **data + small-schema** change, not a feature build. #47 already carries the loader (`_fetch_paralogs`/`_fetch_orthologs`), the paralog ≥80% close-paralog topology promotion, and ortholog topology projection. The gap is (a) the D1 tables were swept for the v1 triage scope, not v2; (b) `compara_paralog.ecd_pct_similarity` exists in #47's loader SQL + Pydantic but not in the D1 table / `.sql` schema; (c) the viewer TS `ParalogEntry` drifted (missing #47's topology fields); (d) no absence sentinel. We audit the gap, extend the **existing** per-cohort topology versions in place (never mint a new "latest"), and add the sentinel.

**Tech Stack:** Python 3 (uv), Cloudflare D1 (HTTP API via `_query_public`), DeepTMHMM (single-worker), Pydantic v2 (`extra="forbid"`), Next.js viewer TS types.

**Critical invariant — version coupling:** Records read `_latest_topology_version_for_cohort(cohort)`. The current latest per cohort is: `human_canonical` → `topo_2026_05_16`, `human_isoforms` → `topo_2026_05_25`, `mouse_ortholog`/`cyno_ortholog` → `topo_2026_05_16`, paralog → `paralog_topo_2026_05_16`, ortholog_ecd → `orthologecd_topo_2026_05_16_idfix`. **All backfill rows MUST be stamped with these existing version strings** (INSERT OR IGNORE appends new genes, no-ops existing). Minting a new version would orphan the ~11k already-swept genes.

**Pre-flight (run once, do not commit):**
```bash
cd /Users/rebeccacarlson/git/accessible-surfaceome/.claude/worktrees/nice-shamir-4ba05b
git status   # confirm on the #47-rebased branch, clean tree
uv sync
ls .env      # symlinked by bootstrap; required for D1
```

---

## Task 1: Coverage-classifier core (pure function + test)

**Files:**
- Create: `src/accessible_surfaceome/audit/v2_deterministic_coverage.py`
- Test: `tests/test_v2_deterministic_coverage.py`

The classifier is the one piece of real logic; isolate it from D1 so it's unit-testable.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v2_deterministic_coverage.py
from accessible_surfaceome.audit.v2_deterministic_coverage import (
    FeaturePresence,
    classify_gene,
)


def test_all_present_yields_present():
    p = FeaturePresence(
        canonical=True, isoforms=True, paralogs=True, orthologs=True
    )
    row = classify_gene("EGFR", "P00533", p)
    assert row["canonical_topology_status"] == "present"
    assert row["paralogs_status"] == "present"
    assert row["orthologs_status"] == "present"
    assert row["isoform_topology_status"] == "present"


def test_missing_canonical_is_needs_backfill():
    p = FeaturePresence(
        canonical=False, isoforms=False, paralogs=False, orthologs=False
    )
    row = classify_gene("FOO1", "Q00001", p)
    # Canonical is never "genuinely absent" — every protein has a main sequence.
    assert row["canonical_topology_status"] == "needs-backfill"
    # The others are "needs-backfill" in pass 1 (genuine-absence resolved post-sweep).
    assert row["paralogs_status"] == "needs-backfill"
    assert row["orthologs_status"] == "needs-backfill"
    assert row["isoform_topology_status"] == "needs-backfill"


def test_row_carries_identifiers():
    p = FeaturePresence(True, True, True, True)
    row = classify_gene("EGFR", "P00533", p)
    assert row["hgnc_symbol"] == "EGFR"
    assert row["uniprot_acc"] == "P00533"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v2_deterministic_coverage.py -q`
Expected: FAIL — `ModuleNotFoundError: accessible_surfaceome.audit.v2_deterministic_coverage`

- [ ] **Step 3: Write minimal implementation**

```python
# src/accessible_surfaceome/audit/v2_deterministic_coverage.py
"""Classify each v2 yes/contextual gene's deterministic-feature coverage.

Pass 1 (this module) is presence-based: a feature with a D1 row is
``present``; a feature with no D1 row is ``needs-backfill``. Genuine
absence (a singleton with no paralogs, a single-isoform gene, a gene with
no one2one ortholog) is resolved in pass 2 *after* the backfill sweep —
whatever still has no row once the sweep has tried is reclassified
``genuinely-absent`` and stamped via the checked-none sentinel (Task 5).
``canonical`` is never genuinely absent: every protein has a main sequence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeaturePresence:
    canonical: bool
    isoforms: bool
    paralogs: bool
    orthologs: bool


def _status(present: bool) -> str:
    return "present" if present else "needs-backfill"


def classify_gene(
    hgnc_symbol: str, uniprot_acc: str, p: FeaturePresence
) -> dict[str, str]:
    return {
        "hgnc_symbol": hgnc_symbol,
        "uniprot_acc": uniprot_acc,
        "canonical_topology_status": _status(p.canonical),
        "isoform_topology_status": _status(p.isoforms),
        "paralogs_status": _status(p.paralogs),
        "orthologs_status": _status(p.orthologs),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_v2_deterministic_coverage.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/accessible_surfaceome/audit/v2_deterministic_coverage.py tests/test_v2_deterministic_coverage.py
git commit -m "feat(audit): v2 deterministic-coverage classifier core"
```

---

## Task 2: Audit script — query D1, write the manifest

**Files:**
- Create: `scripts/audit_v2_deterministic_coverage.py`

This wires the Task-1 classifier to D1: pull the v2 `yes`/`contextual` genes (COALESCE the `__resolver_v3_fix` rerun, exactly like `build_topology_candidate_set.py`), resolve to UniProt via `gene_identifier`, probe each feature table at its existing latest version, classify, and write a manifest TSV. No new logic to unit-test — it's I/O orchestration over the tested core.

- [ ] **Step 1: Write the script**

```python
# scripts/audit_v2_deterministic_coverage.py
"""Audit deterministic-feature coverage for the genome-wide v2 candidates.

Reads the v2 yes/contextual genes from public D1 (COALESCE'ing the
``__resolver_v3_fix`` rerun per CLAUDE.md run_id conventions), probes the
deterministic-feature tables at their CURRENT latest version, classifies
each (gene × feature), and writes a manifest TSV that sizes the backfill.

    uv run python scripts/audit_v2_deterministic_coverage.py \
        --triage-run-id genome_full_sonnet_ncbi_v2

Output: data/analysis/v2_deterministic_coverage/manifest.tsv
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_topology_version_for_cohort,
    _query_public,
)
from accessible_surfaceome.audit.v2_deterministic_coverage import (
    FeaturePresence,
    classify_gene,
)
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)
OUT_DIR = Path("data/analysis/v2_deterministic_coverage")


def _v2_candidates(run_id: str) -> list[dict]:
    """yes/contextual genes for the v2 run, mapped to canonical UniProt accs."""
    return _query_public(
        "SELECT gi.hgnc_symbol AS hgnc_symbol, gi.uniprot_acc AS uniprot_acc, "
        "       gi.ensembl_gene AS ensembl_gene, gi.hgnc_id AS hgnc_id "
        "FROM triage_run t "
        "LEFT JOIN triage_run f "
        "  ON f.gene_symbol = t.gene_symbol "
        "  AND f.run_id = ? "
        "JOIN gene_identifier_public gi ON gi.hgnc_symbol = t.gene_symbol "
        "WHERE t.run_id = ? "
        "  AND COALESCE(f.predicted_verdict, t.predicted_verdict) "
        "      IN ('yes', 'contextual') "
        "  AND gi.uniprot_acc IS NOT NULL AND gi.uniprot_acc != ''",
        [f"{run_id}__resolver_v3_fix", run_id],
    )


def _present_accs(sql: str, params: list) -> set[str]:
    return {r["uniprot_acc"] for r in _query_public(sql, params) if r.get("uniprot_acc")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--triage-run-id", default="genome_full_sonnet_ncbi_v2")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()

    cands = _v2_candidates(args.triage_run_id)
    accs = sorted({c["uniprot_acc"] for c in cands})
    logger.info("v2 yes/contextual genes: %d (%d distinct uniprot)", len(cands), len(accs))

    canon_v = _latest_topology_version_for_cohort("human_canonical")
    iso_v = _latest_topology_version_for_cohort("human_isoforms")

    # Presence sets (one query each; membership test in Python keeps it simple).
    canon = _present_accs(
        "SELECT DISTINCT uniprot_acc FROM topology_public "
        "WHERE cohort='human_canonical' AND topology_version=?",
        [canon_v],
    )
    isos = _present_accs(
        "SELECT DISTINCT uniprot_acc FROM topology_public "
        "WHERE cohort='human_isoforms' AND topology_version=?",
        [iso_v],
    )
    paras = _present_accs(
        "SELECT DISTINCT human_uniprot_acc AS uniprot_acc FROM compara_paralog "
        "WHERE paralog_version='paralog_topo_2026_05_16'",
        [],
    )
    orthos = _present_accs(
        "SELECT DISTINCT human_uniprot_acc AS uniprot_acc FROM compara_ortholog_ecd "
        "WHERE ortholog_ecd_version='orthologecd_topo_2026_05_16_idfix'",
        [],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "manifest.tsv"
    cols = [
        "hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene",
        "canonical_topology_status", "isoform_topology_status",
        "paralogs_status", "orthologs_status",
    ]
    counts = {c: {"present": 0, "needs-backfill": 0} for c in cols if c.endswith("_status")}
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for c in cands:
            acc = c["uniprot_acc"]
            row = classify_gene(
                c["hgnc_symbol"], acc,
                FeaturePresence(
                    canonical=acc in canon,
                    isoforms=acc in isos,
                    paralogs=acc in paras,
                    orthologs=acc in orthos,
                ),
            )
            row["hgnc_id"] = c.get("hgnc_id") or ""
            row["ensembl_gene"] = c.get("ensembl_gene") or ""
            for k, v in counts.items():
                v[row[k]] += 1
            w.writerow(row)

    logger.info("wrote %s", out)
    for k, v in counts.items():
        logger.info("  %-28s present=%-6d needs-backfill=%d", k, v["present"], v["needs-backfill"])
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Run the audit**

Run:
```bash
uv run python scripts/audit_v2_deterministic_coverage.py --triage-run-id genome_full_sonnet_ncbi_v2
```
Expected: writes `data/analysis/v2_deterministic_coverage/manifest.tsv` and logs per-feature `present` / `needs-backfill` counts over the **6,418-accession union scope**. Sanity-check `canonical_topology_status needs-backfill` ≈ 66. Note the isoform/ortholog `needs-backfill` counts are GENE-level **upper bounds** (≈3,014 isoform / ≈1,360 ortholog) — most are genuine-absence (single-isoform / no one2one). The real sequence run is ~1,400 (66 canonical + ~141 alt-isoforms + ~1,190 orthologs); the sweep's UniProt isoform + BioMart ortholog resolution narrows the gene-level set to those actual sequences automatically.

- [ ] **Step 3: Commit the script + manifest**

```bash
git add scripts/audit_v2_deterministic_coverage.py data/analysis/v2_deterministic_coverage/manifest.tsv
git commit -m "feat(audit): manifest of v2 deterministic-feature coverage gaps"
```

- [ ] **Step 4: STOP — review counts with the user before any heavy compute.** The gene-level `needs-backfill` totals are upper bounds; the empirically-measured real sequence run is **~1,400 DeepTMHMM sequences** (66 canonical + ~141 alt-isoforms at a 3%-of-missing alt rate + ~1,190 mouse/cyno orthologs at ~50% one2one). Confirm before kicking off the sweep (Tasks 7–9).

---

## Task 3: Document `ecd_pct_similarity` in the D1 schema + sync the TS `ParalogEntry`

`compute_paralog_ecd_similarity.py` adds the column to D1 at runtime via `ALTER TABLE`, but the `.sql` schema files (used to stand up a fresh DB) don't declare it, and the viewer TS `ParalogEntry` is missing the topology fields #47's Pydantic model has. Fix both so the schema-of-record matches reality and `extra="forbid"` parity holds.

**Files:**
- Modify: `cloudflare/d1_public_schema.sql` (compara_paralog CREATE TABLE)
- Modify: `cloudflare/d1_schema.sql` (compara_paralog CREATE TABLE, if present)
- Modify: `viewer/lib/surfaceome-types.ts` (`ParalogEntry` interface)

- [ ] **Step 1: Add the column to the public schema**

In `cloudflare/d1_public_schema.sql`, in the `compara_paralog` CREATE TABLE, add after the `ecd_pct_identity` line:

```sql
    ecd_pct_similarity       REAL,                    -- identity + BLOSUM62-positive; close pairs (>=80% full-len) only; added 2026-06
```

(Do the same in `cloudflare/d1_schema.sql` if that file declares `compara_paralog`; grep first: `grep -n "compara_paralog" cloudflare/d1_schema.sql`.)

- [ ] **Step 2: Sync the TS `ParalogEntry` to #47's Pydantic model**

Replace the topology-less `ParalogEntry` in `viewer/lib/surfaceome-types.ts` with the fields the Pydantic `ParalogEntry` (models.py) now carries:

```typescript
export interface ParalogEntry {
  paralog_symbol: string;
  paralog_uniprot_acc: string;
  ecd_pct_identity: number | null;
  full_length_pct_identity: number | null;
  family_id: string;
  compara_version: string;
  // Close paralogs (>=80% full-length identity) carry ECD similarity + a
  // full DeepTMHMM topology row (from the paralog's own human_canonical
  // sweep). Distant paralogs stay lean chip-only — these are all null.
  ecd_pct_similarity?: number | null;
  per_residue_topology?: string | null;
  deeptmhmm_label?: string | null;
  tm_helix_count?: number | null;
  ecd_length_residues?: number | null;
  icd_length_residues?: number | null;
  n_terminal_orientation?: string | null;
  c_terminal_orientation?: string | null;
  signal_peptide_length?: number | null;
  sequence?: string | null;
}
```

- [ ] **Step 3: Type-check the viewer**

Run: `cd viewer && npx tsc --noEmit`
Expected: no new errors from `ParalogEntry`. (`cd` back: `cd ..`.)

- [ ] **Step 4: Commit**

```bash
git add cloudflare/d1_public_schema.sql cloudflare/d1_schema.sql viewer/lib/surfaceome-types.ts
git commit -m "fix(data): declare compara_paralog.ecd_pct_similarity + sync TS ParalogEntry topology fields"
```

---

## Task 4: Populate `ecd_pct_similarity` for close paralog pairs

`compute_paralog_ecd_similarity.py` already exists and is idempotent (its `ALTER TABLE` swallows the "column exists" error; the `UPDATE` is keyed on the paralog PK). Running it unblocks #47's loader, which currently errors on `SELECT cp.ecd_pct_similarity`.

- [ ] **Step 1: Dry-run to see the close-pair count**

Run: `uv run python scripts/compute_paralog_ecd_similarity.py`
Expected: logs `close pairs (>=80%): N`, `topology+sequence available for X/Y accessions`, sample rows. No D1 writes.

- [ ] **Step 2: Execute (writes the column + values to public D1)**

Run: `uv run python scripts/compute_paralog_ecd_similarity.py --execute`
Expected: logs `added column ecd_pct_similarity` (or `ALTER skipped` if already present) and `wrote=N`.

- [ ] **Step 3: Verify the loader no longer errors**

Run:
```bash
uv run python -c "
from accessible_surfaceome.env import load_env; load_env()
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import fetch_deterministic_features
d = fetch_deterministic_features('P00533')  # EGFR
print('paralogs:', len(d.paralogs), 'with topology:', sum(1 for p in d.paralogs if p.per_residue_topology))
"
```
Expected: prints a paralog count with ≥1 carrying topology, and **does not** raise `no such column: ecd_pct_similarity`.

- [ ] **Step 4: Commit (no code change — note in the run log / PR body).** No file changes here; this is a D1 data op. Record the `wrote=N` count in the PR note (Task 11).

---

## Task 5: "Checked, none found" absence sentinel — schema + loader stamping

Add explicit flags so a checked-but-empty feature is distinguishable from a not-yet-computed stub, mirroring `SurfaceBindFeatures.has_data`.

**Files:**
- Modify: `src/accessible_surfaceome/tools/_shared/models.py` (`Orthologs`, `DeterministicFeatures`)
- Modify: `src/accessible_surfaceome/agents/surfaceome_v1/d1_deterministic.py` (`fetch_deterministic_features`, `_fetch_orthologs`)
- Test: `tests/test_deterministic_sentinels.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deterministic_sentinels.py
from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    Orthologs,
)


def test_orthologs_checked_defaults_false():
    assert Orthologs().checked is False


def test_deterministic_features_checked_flags_default_false():
    # Build a minimal DeterministicFeatures via its defaults where possible.
    fields = DeterministicFeatures.model_fields
    assert "paralogs_checked" in fields
    assert "isoform_topologies_checked" in fields
    assert fields["paralogs_checked"].default is False
    assert fields["isoform_topologies_checked"].default is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_deterministic_sentinels.py -q`
Expected: FAIL — `checked`/`paralogs_checked` not defined.

- [ ] **Step 3: Add the fields**

In `models.py`, in `class Orthologs(BaseModel)` add after the `cynomolgus` field:

```python
    # Explicit "checked, none found" sentinel (mirrors SurfaceBindFeatures.has_data).
    # ``False`` = this gene's orthologs were never resolved (stub / D1 unreachable);
    # ``True`` with empty mouse+cynomolgus = checked against Ensembl Compara and no
    # one2one ortholog exists. Lets the viewer render "none found" vs a placeholder.
    checked: bool = False
```

In `class DeterministicFeatures(BaseModel)` add after the `paralogs` field:

```python
    # "Checked, none found" sentinels for the bare lists above (same rationale as
    # Orthologs.checked). True once the loader has queried D1 for this gene even
    # when the list came back empty (genuine singleton / single-isoform gene).
    paralogs_checked: bool = False
    isoform_topologies_checked: bool = False
```

- [ ] **Step 4: Stamp the flags in the loader**

In `d1_deterministic.py`:
- In `_fetch_orthologs`, set `checked=True` on the returned `Orthologs(...)` (the function successfully queried D1, so it's checked regardless of emptiness).
- In `fetch_deterministic_features`, when constructing the real (non-stub) `DeterministicFeatures`, pass `paralogs_checked=True` and `isoform_topologies_checked=True`. Leave the `_stub_deterministic_features` path at the `False` defaults (a stub was NOT checked).

Concretely, in `_fetch_orthologs` change the final `return Orthologs(mouse=..., cynomolgus=...)` to `return Orthologs(mouse=..., cynomolgus=..., checked=True)`. In `fetch_deterministic_features`, add `paralogs_checked=True, isoform_topologies_checked=True` to the `DeterministicFeatures(...)` constructor call (the success path only).

- [ ] **Step 5: Run tests + a loader smoke check**

Run: `uv run pytest tests/test_deterministic_sentinels.py -q`
Expected: PASS.

Run:
```bash
uv run python -c "
from accessible_surfaceome.env import load_env; load_env()
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import fetch_deterministic_features
d = fetch_deterministic_features('P00533')
print('orthologs.checked=', d.orthologs.checked, 'paralogs_checked=', d.paralogs_checked, 'iso_checked=', d.isoform_topologies_checked)
"
```
Expected: all three print `True`.

- [ ] **Step 6: Commit**

```bash
git add src/accessible_surfaceome/tools/_shared/models.py src/accessible_surfaceome/agents/surfaceome_v1/d1_deterministic.py tests/test_deterministic_sentinels.py
git commit -m "feat(agents): checked-none sentinel for orthologs/paralogs/isoform topology"
```

---

## Task 6: Sync the sentinel into the TS types

**Files:**
- Modify: `viewer/lib/surfaceome-types.ts` (`OrthologSet`, `DeterministicFeatures`)

- [ ] **Step 1: Add the fields**

In the `OrthologSet` interface add:
```typescript
  checked?: boolean;
```
In the `DeterministicFeatures` interface add:
```typescript
  paralogs_checked?: boolean;
  isoform_topologies_checked?: boolean;
```

- [ ] **Step 2: Type-check**

Run: `cd viewer && npx tsc --noEmit && cd ..`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add viewer/lib/surfaceome-types.ts
git commit -m "feat(viewer): mirror checked-none sentinel in TS types"
```

> **Note — viewer rendering deferred:** the "none found (checked)" UI copy in the OrthologsCard / paralog card is intentionally out of scope here (the genome-wide v2 records don't exist yet, so there's nothing to render). It lands with the deep-dive run or a follow-up; the data + types are in place now.

---

## Task 7: Build the v2-scoped candidate set (needs-backfill subset)

**Files:**
- Create (generated): `data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv` (full v2 scope)
- Create (generated): `data/processed/topology_run_topo_2026_05_16/candidate_accessions.backfill.tsv` (filtered to needs-backfill)

- [ ] **Step 1: Build the full v2 candidate set**

Run:
```bash
uv run python scripts/build_topology_candidate_set.py \
  --topology-version topo_2026_05_16 \
  --triage-run-id genome_full_sonnet_ncbi_v2
```
Expected: writes `data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv` for the v2 yes/contextual scope. (We reuse the existing version string so downstream stamping extends it in place — see the version invariant.)

- [ ] **Step 2: Filter to the needs-backfill genes from the manifest**

Run:
```bash
uv run python - <<'PY'
import csv
from pathlib import Path
man = {r["uniprot_acc"] for r in csv.DictReader(
    open("data/analysis/v2_deterministic_coverage/manifest.tsv"), delimiter="\t")
    if any(r[k] == "needs-backfill" for k in (
        "canonical_topology_status","isoform_topology_status",
        "paralogs_status","orthologs_status"))}
src = Path("data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv")
dst = src.with_suffix(".backfill.tsv")
rows = list(csv.DictReader(open(src), delimiter="\t"))
keep = [r for r in rows if r["uniprot_acc"] in man]
with dst.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=rows[0].keys(), delimiter="\t")
    w.writeheader(); w.writerows(keep)
print(f"kept {len(keep)}/{len(rows)} rows -> {dst}")
PY
```
Expected: prints the kept-row count (the gene-level backfill subset, ≈ a few thousand genes — but the sweep's isoform/ortholog resolution narrows this to ~1,400 actual DeepTMHMM sequences, since most kept genes are single-isoform / no-one2one and only get a "checked, none" flag).

- [ ] **Step 3: Commit the candidate set + backfill subset**

```bash
git add data/processed/topology_run_topo_2026_05_16/candidate_accessions.tsv \
        data/processed/topology_run_topo_2026_05_16/candidate_accessions.backfill.tsv
git commit -m "chore(data): v2-scoped topology candidate set + needs-backfill subset"
```

---

## Task 8: Run the topology sweep (single worker, compute only)

Run DeepTMHMM on the backfill subset, writing JSONL to disk first (`--skip-upload`) so compute is decoupled from the version-sensitive D1 write. `human_canonical`/`mouse_ortholog`/`cyno_ortholog` share `topo_2026_05_16`; `human_isoforms` is on `topo_2026_05_25`, so it's a separate invocation.

**Why `--skip-upload` is mandatory (not optional):** the sweep's auto-upload derives `ortholog_ecd_version = f"orthologecd_{topology_version}"` = `orthologecd_topo_2026_05_16` — but the existing 9,052 ortholog-ECD rows live under `orthologecd_topo_2026_05_16_idfix` (note the `_idfix` suffix from a prior fix script), and `_latest_ortholog_ecd_version()` picks by `computed_at DESC`. An auto-upload would mint the newer `…_idfix`-less version and **orphan all 9,052 existing rows.** The sweep has no flag to override that string, so we skip its upload and run the uploaders manually in Task 9 pinning the existing version. (Topology + paralog version derivations *do* match the existing strings, so only ortholog-ECD is affected — but skipping upload wholesale keeps one consistent, auditable path.)

**Env:** `export DEEPTMHMM_ROOT=/Users/rebeccacarlson/Git/deliverome-internal/analyses/surface-proteome` (or pass `--deeptmhmm-root`).

- [ ] **Step 1: Sweep canonical + orthologs (existing version `topo_2026_05_16`), single worker, no upload**

Run (background — single-worker DeepTMHMM is slow):
```bash
uv run python scripts/run_topology_sweep.py \
  --topology-version topo_2026_05_16 \
  --cohorts human_canonical,mouse_ortholog,cyno_ortholog \
  --candidate-set data/processed/topology_run_topo_2026_05_16/candidate_accessions.backfill.tsv \
  --paralog-version paralog_topo_2026_05_16 \
  --max-workers 1 \
  --skip-upload
```
Expected: produces `predicted_topologies.3line` + topology JSONL under `data/processed/topology_run_topo_2026_05_16/`. Idempotent — re-running skips completed batches.

- [ ] **Step 2: Sweep isoforms (existing version `topo_2026_05_25`), single worker, no upload, skip paralogs**

Run (background):
```bash
uv run python scripts/run_topology_sweep.py \
  --topology-version topo_2026_05_25 \
  --cohorts human_isoforms \
  --candidate-set data/processed/topology_run_topo_2026_05_16/candidate_accessions.backfill.tsv \
  --max-workers 1 \
  --skip-paralogs \
  --skip-upload
```
Expected: isoform-cohort JSONL under `data/processed/topology_run_topo_2026_05_25/`.

- [ ] **Step 3: Sanity-check the JSONL row counts** match the backfill subset's per-cohort expectation from the manifest before uploading. Do **not** commit the large intermediate sweep artifacts (they're gitignored / cleaned); only the candidate TSVs are tracked.

---

## Task 9: Upload the swept rows into the existing D1 versions

Upload with the dedicated `upload_*.py` scripts (same ones the sweep shells out to — see `run_topology_sweep.py:2088-2124`), **passing the existing version strings** so `INSERT OR IGNORE` appends the new genes and no-ops the ~11k already present. The `--jsonl` paths are the per-cohort outputs the sweep wrote under the run dir in Task 8 (the sweep logs each path; also discoverable via `ls data/processed/topology_run_topo_2026_05_16/*.jsonl`). Run each uploader's `--help` once to confirm the JSONL flag spelling before the writes.

- [ ] **Step 1: Upload canonical + ortholog topology (version `topo_2026_05_16`)**

Run (substitute the actual JSONL paths from Task 8's run dir; one `--jsonl` per cohort file):
```bash
uv run python scripts/upload_topology_to_d1.py \
  --topology-version topo_2026_05_16 \
  --cohorts-present human_canonical,mouse_ortholog,cyno_ortholog \
  --jsonl data/processed/topology_run_topo_2026_05_16/<human_canonical>.jsonl \
  --jsonl data/processed/topology_run_topo_2026_05_16/<mouse_ortholog>.jsonl \
  --jsonl data/processed/topology_run_topo_2026_05_16/<cyno_ortholog>.jsonl
```
Verify:
```bash
uv run python -c "
from accessible_surfaceome.env import load_env; load_env()
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import _query_public
print(_query_public(\"SELECT cohort, COUNT(*) n FROM topology_public WHERE topology_version='topo_2026_05_16' GROUP BY cohort\", []))
"
```
Expected: `human_canonical` count rose by ~the backfill canonical count vs the pre-run baseline (11055).

- [ ] **Step 2: Upload isoform topology (version `topo_2026_05_25`)**

```bash
uv run python scripts/upload_topology_to_d1.py \
  --topology-version topo_2026_05_25 \
  --cohorts-present human_isoforms \
  --jsonl data/processed/topology_run_topo_2026_05_25/<human_isoforms>.jsonl
```
Re-verify `human_isoforms` count rose under `topo_2026_05_25`.

- [ ] **Step 3: Upload paralog + ortholog-ECD rows at the EXISTING versions**

Paralogs (existing `paralog_topo_2026_05_16`):
```bash
uv run python scripts/upload_paralogs_to_d1.py \
  --paralog-version paralog_topo_2026_05_16 \
  --compara-release "Compara r112" \
  --jsonl data/processed/topology_run_topo_2026_05_16/<paralog>.jsonl
```
Ortholog ECD — **pin the existing `_idfix` version** (this is the orphan-avoidance step):
```bash
uv run python scripts/upload_ortholog_ecd_to_d1.py \
  --ortholog-ecd-version orthologecd_topo_2026_05_16_idfix \
  --compara-release "Compara r112" \
  --jsonl data/processed/topology_run_topo_2026_05_16/<ortholog_ecd>.jsonl
```
Then re-run **Task 4 Step 2** (`compute_paralog_ecd_similarity.py --execute`) so the newly-added close paralogs get `ecd_pct_similarity`. Verify `_latest_ortholog_ecd_version()` still returns `orthologecd_topo_2026_05_16_idfix` (NOT a new string):
```bash
uv run python -c "
from accessible_surfaceome.env import load_env; load_env()
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import _latest_ortholog_ecd_version
print(_latest_ortholog_ecd_version())
"
```
Expected: `orthologecd_topo_2026_05_16_idfix`.

- [ ] **Step 4: Pass-2 reclassification — regenerate the manifest**

Run: `uv run python scripts/audit_v2_deterministic_coverage.py --triage-run-id genome_full_sonnet_ncbi_v2`
Then anything still `needs-backfill` is genuine-absence (singleton / single-isoform / no one2one ortholog). Commit the updated manifest:
```bash
git add data/analysis/v2_deterministic_coverage/manifest.tsv
git commit -m "chore(data): post-backfill v2 deterministic-coverage manifest (residual = genuine-absence)"
```

---

## Task 10: Re-sync the demo viewer records (sentinel + paralog topology)

The ~12 committed `viewer/public/data/surfaceome/*.json` snapshots predate the sentinel and the populated `ecd_pct_similarity`. Refresh them and re-sync D1 in the **same** change (per CLAUDE.md: never hand-edit a snapshot without syncing D1).

- [ ] **Step 1: Re-run the deterministic patch scripts over the demo set**

Run:
```bash
uv run python scripts/patch_deterministic_paralogs.py --all
uv run python scripts/patch_deterministic_orthologs.py --all
```
Expected: each demo JSON's `deterministic_features.paralogs` now carries `ecd_pct_similarity` + close-paralog topology; `orthologs.checked` is `true`.

- [ ] **Step 2: Push the snapshots to public D1**

Run: `uv run python scripts/upload_viewer_snapshots_to_d1.py --execute`
Expected: `INSERT OR REPLACE` on `(gene_symbol, schema_version)`; logs the rows written.

- [ ] **Step 3: Commit the refreshed snapshots**

```bash
git add viewer/public/data/surfaceome/*.json
git commit -m "chore(data): refresh demo records (checked-none sentinel + paralog ECD similarity) + D1 resync"
```

---

## Task 11: PR note + docs, run quality checks, open the PR

**Files:**
- Modify: `docs/` — add a short note (e.g. extend the deep-dive redesign doc or a new `docs/reports/2026-06-01-v2-deterministic-backfill.md`).

- [ ] **Step 1: Write the explanatory note**

Create `docs/reports/2026-06-01-v2-deterministic-backfill.md` summarizing: the v1→v2 triage-scope gap; the measured coverage table (from the manifest, before/after); that orthologs + isoforms already carry per-residue topology and paralogs get it for ≥80% close pairs; the `ecd_pct_similarity` column addition (with `wrote=N`); the single-worker sweep extending the **existing** versions in place; and the checked-none sentinel.

- [ ] **Step 2: Run the full quality gate**

Run: `bash scripts/check-py.sh`
Expected: ruff + ty + compile + pytest all green.

Run: `cd viewer && npx tsc --noEmit && cd ..`
Expected: clean.

- [ ] **Step 3: Commit the note**

```bash
git add docs/reports/2026-06-01-v2-deterministic-backfill.md
git commit -m "docs(agents): note on v2 deterministic-feature backfill"
```

- [ ] **Step 4: Push and open the PR stacked on #47**

```bash
git push -u origin claude/nice-shamir-4ba05b
gh pr create --base claude/pedantic-mendel-d0be83 \
  --title "feat(agents): backfill ortholog/paralog/isoform/topology for genome-wide v2 candidates" \
  --body-file docs/reports/2026-06-01-v2-deterministic-backfill.md
```
Expected: PR opened with base = #47's branch. (Add the prose "note explaining" to the PR body — the report file doubles as it.)

---

## Self-Review notes (addressed)

- **Spec coverage:** §A audit → Tasks 1–2; §B backfill → Tasks 3,4,7,8,9; §B4 migration → Tasks 3,4; §C sentinel → Tasks 5,6,10; §D PR note → Task 11. ✓
- **Version invariant** (orphan-avoidance) is called out at the top and enforced in Tasks 7–9 by re-using the existing per-cohort version strings. ✓
- **Idempotency:** topology upload is `INSERT OR IGNORE`; `compute_paralog_ecd_similarity.py` ALTER/UPDATE is idempotent; sweep skips completed batches. ✓
- **D1/snapshot drift discipline** (CLAUDE.md) enforced in Task 10 (re-sync in the same change). ✓
- **Manifest-first gate** (Task 2 Step 4) prevents heavy compute before the user confirms the count. ✓
- **Ortholog-ECD orphan bug** (the sweep derives `orthologecd_topo_2026_05_16` but existing rows are `…_idfix`) is the single highest-risk item — neutralized by `--skip-upload` (Task 8) + explicit `--ortholog-ecd-version orthologecd_topo_2026_05_16_idfix` (Task 9 Step 3) + a post-write `_latest_ortholog_ecd_version()` assertion. ✓
- **Env-specific values resolved at execution time (discoverable, not placeholders):** the per-cohort JSONL filenames under the Task-8 run dir (the sweep logs them; `ls …/*.jsonl`) and the DeepTMHMM root path (`DEEPTMHMM_ROOT` env / `--deeptmhmm-root`). The uploader script names + version flags are now concrete (`run_topology_sweep.py:2088-2124`).
