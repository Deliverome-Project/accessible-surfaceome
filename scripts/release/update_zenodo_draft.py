"""Update an existing Zenodo draft deposit in place.

The ``publish-archive.py`` script always creates a NEW draft (mints a
new reserved DOI). When we want to keep the same DOI but replace the
files / description, the Zenodo API supports edit-in-place on draft
deposits:

  GET  /api/deposit/depositions/{id}              — fetch state + bucket URL
  GET  /api/deposit/depositions/{id}/files        — list files + checksums
  DELETE /api/deposit/depositions/{id}/files/{fid} — delete one file
  PUT  /api/files/{bucket}/{filename}             — upload (S3-style)
  PUT  /api/deposit/depositions/{id}              — patch metadata

This script targets deposit 20805384 (the benchmarking + triage data
deposit) and performs a NON-DESTRUCTIVE, checksum-aware sync of ONLY
the files it manages (the two consolidated TSVs + README):

  1. Managed files whose content changed (local MD5 != remote checksum)
     → overwritten in place via the bucket PUT (which replaces by name,
     so no delete is needed). Unchanged managed files are SKIPPED — no
     re-upload, no timestamp churn.
  2. Files THIS script used to ship but no longer does → deleted ONLY if
     their exact names are listed in RETIRED_FILENAMES. This is surgical
     and name-scoped; there is NO blanket "delete every file" step.
  3. Every other file on the deposit — e.g. ``deep_dives_all.tar.gz``,
     uploaded by ``publish-archive.py`` / the deep-dive tarball refresh —
     is left completely untouched and reported as "preserved".
  4. Description + title → refreshed only if they actually differ.

Historically this script deleted ALL files before re-uploading, which
silently wiped the 100+ MB deep-dive tarball on every run. The sync
below never touches a file it does not manage.

Run after ``scripts/release/build_consolidated_deposit_tsvs.py``
produces the new TSVs at /tmp/zenodo_deposit_consolidated/.

Environment:
  ZENODO_TOKEN — required (same scope as publish-archive.py)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

DEPOSIT_ID = "20805384"
TMP_DIR = Path("/tmp/zenodo_deposit_consolidated")
NEW_FILES = [
    TMP_DIR / "triage-runs-genome-with-reasoning.tsv",
    TMP_DIR / "triage-benchmark-with-reasoning.tsv",
    # Built by build_consolidated_deposit_tsvs.py alongside the two TSVs but
    # never uploaded until now.
    TMP_DIR / "deep-dive-preset-membership.tsv",
]
README_PATH = TMP_DIR / "README.md"
# Row counts of the built files, written by build_consolidated_deposit_tsvs.py.
MANIFEST_PATH = TMP_DIR / "deposit_manifest.json"
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
# Reproducibility replicates (Supplementary Figure 16): the frozen bundle, tarred
# deterministically so an unchanged bundle re-syncs as "unchanged".
REPLICATES_BUNDLE = Path(__file__).resolve().parents[2] / "data/processed/deep_dive_concordance_v1"
REPLICATES_TARBALL = TMP_DIR / "deep-dive-reproducibility-replicates-v1.tar.gz"  # built by _build_replicates_tarball

# Filenames THIS script used to ship but no longer does. They are deleted
# from the deposit only if present — surgical and name-scoped. This is the
# ONLY path that ever issues a DELETE; it never touches files outside this
# list. Add a name here when you rename or drop one of this script's own
# outputs (e.g. the old pre-consolidation per-lane TSVs). Files managed by
# OTHER scripts — deep_dives_all.tar.gz, manuscript.pdf — must NOT appear
# here; leaving them off is what keeps them preserved.
RETIRED_FILENAMES: list[str] = []

ZENODO_BASE = "https://zenodo.org/api"


def _md5(path: Path) -> str:
    """Streaming MD5 of a local file — matches Zenodo's stored checksum."""
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _remote_checksum(file_rec: dict) -> str | None:
    """Zenodo file checksum normalized to bare md5 hex.

    The deposit /files listing returns plain hex; the newer records API
    returns ``md5:<hex>``. Strip the optional algorithm prefix so a direct
    string compare against :func:`_md5` works either way."""
    c = file_rec.get("checksum")
    if not c:
        return None
    return c.split(":", 1)[1] if ":" in c else c


def _head_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _build_readme() -> str:
    sha = _head_sha()
    return f"""# The accessible human surfaceome — data deposit

Data outputs from the **accessible-surfaceome** project, which reconciles which
human proteins are reachable on the outside of the cell — the "surfaceome" that
most antibody, ADC, and cell-therapy drugs act on. The main public surface
databases disagree often, so the project scores every protein-coding gene with
an LLM agent pipeline: a fast genome-wide **triage** pass, a **benchmark**
against curated ground truth, and an evidence-cited **deep dive** on the strong
candidates. This deposit holds the data those three stages produced.

**Reserved DOI:** `10.5281/zenodo.20805384` — stable across draft updates,
activates on publish.

Four data files + this README. Each is a flat TSV or a gzipped folder of
per-gene JSON, readable with any TSV reader (pandas, R) or `tar xzf` — no
project code needed. Each is also reproducible from the project's public
read-only API (recipes at the end).

---

## 1. `triage-runs-genome-with-reasoning.tsv` — genome-wide first-pass triage

**33,728 rows**, one per (gene × run). The triage agent is a single LLM call per
gene that reads a context block and returns a surface-accessibility verdict
(`yes` / `contextual` / `no`), a controlled-vocabulary reason, a confidence and
its free-text reasoning, with per-call token / cost / latency accounting.

Five runs, tagged by the `run_id` column:

- **`genome_full_sonnet_ncbi_v2`** — the primary sweep with NCBI gene-summary
  context: **19,324 genes**, one row each.
- Four **PubMed-context rescue lanes**, which re-triage the **14,404 genes** the
  primary sweep called `no` and at most one surface database supports, with
  PubMed abstracts in the prompt:
  - **`genome_full_sonnet_pubmed_ncbi_v1`** — 2,626 genes in no database whose
    `no` reason was ambiguous (endomembrane, secreted, inner leaflet, …)
  - **`genome_intracellular_pubmed_ncbi_v1`** — 10,287 genes in no database
    called cytoplasmic, nuclear or mitochondrial
  - **`genome_1db_trim_pubmed_ncbi_v1`** — 1,417 genes in exactly one database
  - **`genome_optcut_zerodb_pubmed_ncbi_v1`** — 74 genes that moved from one
    database to none under the optimized CSPA cutoff

  A re-triaged gene carries an NCBI row plus its PubMed row; every other gene
  carries one row. The lanes are disjoint except for 9 genes the 74-gene lane
  re-ran after an earlier lane, which carry a row from each. A few lane rows have `prompt_variant` = `naive`: the PubMed fetch failed
  for that gene and the call ran on the gene symbol alone.

| Column | Meaning |
|---|---|
| `run_id` | which run the row is from (see above) |
| `gene_symbol` | HGNC gene symbol |
| `uniprot_acc`, `hgnc_id`, `ensembl_gene` | stable identifiers |
| `db_uniprot`, `db_go`, `db_surfy`, `db_cspa`, `db_hpa` | 0/1 — does each of the five surface databases (UniProt, GO, SURFY, CSPA, HPA) call this gene surface? |
| `n_db_surface` | how many of the five agree (0–5) |
| `model`, `prompt_variant`, `replicate` | which model / context variant / replicate produced the row |
| `predicted_verdict` | `yes` / `contextual` / `no` |
| `predicted_reason` | short controlled-vocabulary reason tag |
| `predicted_confidence` | `low` / `medium` / `high` |
| token / cost / latency columns | `prompt_tokens`, `completion_tokens`, `cache_creation_tokens`, `cache_read_tokens`, `n_web_searches`, `cost_usd`, `latency_s` |
| `predicted_key_uncertainty` | the agent's one-line statement of what would change its call |
| `verdict_reasoning` | the agent's free-text rationale for the verdict |
| `error` | why a row has no verdict: `refusal` (the model's safety classifier declined) or a runner error; empty for a normal call |

**Reconciling the NCBI and PubMed rows.** When a gene has both an NCBI and a PubMed row,
prefer the PubMed verdict only when it is *more* inclusive (PubMed
`yes`/`contextual` over NCBI `no`); a PubMed `no` never overrides an NCBI
`yes`/`contextual`, since absence of literature is not evidence of absence:

```python
def reconciled_verdict(ncbi, pubmed):
    if pubmed in ("yes", "contextual") and ncbi == "no":
        return pubmed
    return ncbi
```

---

## 2. `triage-benchmark-with-reasoning.tsv` — the 147-gene accuracy benchmark

**7,938 rows.** The same triage call run over a 147-gene curated panel with
ground-truth labels, so per-model / per-variant accuracy can be measured
directly.

Coverage of the model × prompt-variant grid is **intentionally uneven** — not
every model is run under every variant:

- **Haiku 4.5** and **Sonnet 4.6** — all four variants (`naive`, `ncbi`,
  `web_ncbi`, `pubmed_ncbi`)
- **Opus 4.8**, **Haiku 5.5** and **Sonnet 5.5** — `naive` + `ncbi`
- **Sonnet 5** and **Opus 5** — `ncbi`
- **Opus 5.5** — `ncbi` and `ncbi_effort_low` (the `ncbi` prompt run at low
  reasoning effort)

That is **18 (model × variant) cells × 3 replicates × 147 genes = 7,938 rows**.
Opus 5.5 declined to answer some calls (a safety-classifier refusal): those
rows have an empty `predicted_verdict` and `error` = `refusal`, and the
benchmark figures leave them out of accuracy and report the refusal rate.
Every replicate is kept (not a pre-aggregated majority) so per-replicate
variability is visible. The curated truth label is joined onto every row:

| Column | Meaning |
|---|---|
| `truth_verdict` | curated truth: `yes` / `contextual` / `no` |
| `truth_signal` | curated accessibility signal (`likely_accessible`, `possibly_accessible`, `unlikely`, …) |
| `truth_reason` | curated reason (controlled vocabulary) |
| `truth_class` | the benchmark's disagreement bucket for the gene |

plus every column from file 1.

---

## 3. `deep_dives_all.tar.gz` — evidence-cited per-gene records

**5,332 JSON records**, one per gene (`<SYMBOL>.json`; `tar tzf` lists them).
Each is a deep-dive agent output: the full evidence chain with verbatim source
quotes, the structured surface call, and a classification —

- **`deep_dive_tier`** — `canonical` (high-confidence surface) / `likely` /
  `low` / `uncertain` / `no`
- **`deep_dive_facet`** — `cell_state_induced` or `cell_type_restricted`, where
  it applies

The tier uses the same rule the project's public catalog applies and is attached
to each record as served, so the classification here matches that catalog.

---

## 4. `deep-dive-preset-membership.tsv` — catalog preset membership per deep-dive gene

One row per gene with a deep-dive record. The `in_*` columns (1/0) say whether
the gene falls in each of the public catalog's presets (`canonical`, `likely`,
`induced`, `cell_type_restricted`), computed with the same predicates the
catalog uses (`accessible_surfaceome.release.catalog_presets`). The
`induction_*` columns split `induced` by trigger, and the remaining columns are
the record fields those predicates read, so any preset can be re-derived
locally.

---

## 5. `deep-dive-reproducibility-replicates-v1.tar.gz` — run-to-run reproducibility

**Not published records.** 50 deep-dive genes drawn at random (two disjoint
batches of 25) and re-analyzed to measure reproducibility (Supplementary
Figure 16 of the manuscript). Three record sets, one line per gene in each
(`{"hgnc_symbol", "sample_batch", "record"}`, `record` a full SurfaceomeRecord
with its evidence ledger):

- **`published.jsonl.gz`** — the published record exactly as served when the
  study ran (2026-09-27; run `cu_v3_sonnet_2026_06`), the comparator
- **`full_rerun.jsonl.gz`** — the whole pipeline re-run from scratch with the
  same prompts (run `deep_dive_concordance_v1`)
- **`fixed_evidence_replay.jsonl.gz`** — section builders + synthesizer re-run
  on each published record's own evidence (discovery and selection held fixed)

plus `sample_genes.tsv` (the 50 genes and their batch) and a README. The same
records are queryable from the API, labelled `reproducibility_replicate: true`.

---

## Reproducing from the public API

Every file is rebuildable from the read-only API at
`https://api.deliverome.org/surfaceome/v1/` (no credentials):

```
# File 1 — the five genome runs (tag each with its run_id, then concatenate)
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v2'
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_pubmed_ncbi_v1'
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_intracellular_pubmed_ncbi_v1'
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_1db_trim_pubmed_ncbi_v1'
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_optcut_zerodb_pubmed_ncbi_v1'

# File 2 — benchmark predictions + curated truth (join on gene_symbol)
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v2'
curl 'https://api.deliverome.org/surfaceome/v1/benchmark'

# File 3 — the deep-dive records
curl 'https://api.deliverome.org/surfaceome/v1/genes'          # gene index
curl 'https://api.deliverome.org/surfaceome/v1/genes/EGFR'     # one record

# File 4 — preset membership: each deep-dive gene's `ddf` block on the catalog,
# run through accessible_surfaceome.release.catalog_presets
curl 'https://api.deliverome.org/surfaceome/v1/catalog'

# File 5 — the reproducibility replicates (NOT published records)
curl 'https://api.deliverome.org/surfaceome/v1/replicates'                 # study + gene index
curl 'https://api.deliverome.org/surfaceome/v1/genes/M6PR/replicates'      # one gene's replicates
curl 'https://api.deliverome.org/surfaceome/v1/genes/M6PR/replicates/deep_dive_concordance_v1/full_rerun'
```

## License

CC-BY-4.0. Upstream sources keep their own terms (UniProt, GO, HPA — CC-BY /
CC-BY-SA; SURFY and CSPA are published academic resources).

## Source

Produced by the accessible-surfaceome project
(<https://github.com/Deliverome-Project/accessible-surfaceome>, commit
`{sha[:12]}`). The manuscript will be added to this record in a later draft
update.
"""


_DESCRIPTION_HTML = (
    "Benchmark, triage, and deep-dive data outputs for the "
    "accessible-surfaceome project. This version ships five data files "
    "plus an in-deposit README documenting every column and the "
    "source-join recipe.<br><br>"
    "<b>triage-runs-genome-with-reasoning.tsv</b> — 33,728-row "
    "long-format TSV, with each call's verdict, reason, confidence and "
    "free-text reasoning, consolidating the genome-wide Sonnet+NCBI sweep "
    "(19,324 genes × 1 rep) AND the four PubMed-context rescue "
    "lanes that re-triage the genes it called no with at most one "
    "supporting database. A `run_id` column tags every row so the lanes "
    "can be split or merged at read time; each re-run gene has an NCBI row "
    "plus its PubMed row(s). The "
    "read-side reconciliation rule (prefer PubMed when it is more "
    "inclusive than NCBI) is documented in the README and applied "
    "server-side by the live /v1/catalog endpoint.<br><br>"
    "<b>triage-benchmark-with-reasoning.tsv</b> — 7,938-row long-format "
    "multi-replicate TSV covering the 147-gene curated benchmark across 8 "
    "models with uneven prompt-variant coverage (Haiku 4.5 + Sonnet 4.6: "
    "all 4 variants; Opus 4.8, Haiku 5.5, Sonnet 5.5: naive + ncbi; Sonnet 5, "
    "Opus 5: ncbi; Opus 5.5: ncbi + ncbi at low reasoning effort) — 18 "
    "(model × variant) cells × 3 replicates × 147 genes — with each "
    "call's free-text reasoning and the curated truth verdict / signal / "
    "reason / class joined onto every row.<br><br>"
    "<b>deep_dives_all.tar.gz</b> — one JSON per published "
    "SurfaceomeRecord (5,332 records), each carrying its full evidence "
    "chain, per-claim verbatim quotes, every structured attribute (the "
    "filters block and the deterministic features), and the deep-dive "
    "classification "
    "(`deep_dive_tier` + `deep_dive_facet`) computed by the same "
    "predicate the viewer ships and attached server-side on "
    "/v1/genes/{symbol}.<br><br>"
    "<b>deep-dive-preset-membership.tsv</b> — one row per deep-dive gene "
    "with 1/0 membership in each public-catalog preset (canonical, likely, "
    "induced, cell-type restricted) and the record fields the presets "
    "read.<br><br>"
    "<b>deep-dive-reproducibility-replicates-v1.tar.gz</b> — run-to-run "
    "reproducibility replicates, NOT published records: for 50 randomly "
    "sampled deep-dive genes, the published record as served when the "
    "study ran, a full from-scratch re-run with the same prompts, and a "
    "fixed-evidence replay (builders + synthesizer only). Source data for "
    "Supplementary Figure 16; also queryable at /v1/replicates.<br><br>"
    "All data files are reproducible from the public read-only API at "
    "https://api.deliverome.org/surfaceome/v1/ (no credentials)."
)


# Deep-dive tarball entry for publish-archive's bundle builder. Fetching the
# raw /v1/genes responses means the tarball records now carry deep_dive_tier
# (the Worker attaches it at serve time), so the deposit stores the tier with
# every record — no extra step.
_DEEP_DIVES_ENTRY = {
    "deep_dives_bundle": True,
    "filename": "deep_dives_all.tar.gz",
    "index_url": "https://api.deliverome.org/surfaceome/v1/genes",
    "gene_url_template": "https://api.deliverome.org/surfaceome/v1/genes/{symbol}",
}


def check_docs_against_manifest(readme: str, description: str,
                                manifest: dict) -> list[str]:
    """Problems with the README / description given the files actually built.

    The README and description state row counts in prose, and those went
    stale before (a deposit described 2,626 PubMed rows long after there were
    14,404, and 5,130 records after the cohort grew). Every count the
    manifest records has to appear in both, and every built file has to be
    one this script uploads.
    """
    problems = []
    shipped = {p.name for p in NEW_FILES}
    for name in manifest["files"]:
        if name not in shipped:
            problems.append(f"{name} is built but not in NEW_FILES, so it would not be uploaded")
    totals = {
        "genome rows": manifest["genome_rows"],
        "benchmark rows": manifest["benchmark_rows"],
        "deep-dive records": manifest["deep_dive_records"],
    }
    for doc_name, text in (("README", readme), ("description", description)):
        for label, n in totals.items():
            if f"{n:,}" not in text:
                problems.append(f"{doc_name} does not state the {label} ({n:,})")
    # Per-run counts are listed in the README only.
    for run, n in manifest["genome_runs"].items():
        if f"{n:,}" not in readme:
            problems.append(f"README does not state {run}'s {n:,} rows")
    cells = f"{manifest['benchmark_cells']} (model × variant) cells"
    for doc_name, text in (("README", readme), ("description", description)):
        if cells not in text:
            problems.append(f"{doc_name} does not say '{cells}'")
    return problems


def _pyproject_version() -> str:
    for line in PYPROJECT.read_text().splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit(f"no version in {PYPROJECT}")


def _build_replicates_tarball() -> Path:
    """Shared deterministic builder (record_history.zenodo) — one implementation."""
    from accessible_surfaceome.cloud.record_history.zenodo import build_replicates_tarball

    return build_replicates_tarball(REPLICATES_BUNDLE, TMP_DIR)


def _build_deep_dive_tarball() -> Path:
    """Build deep_dives_all.tar.gz (one <SYMBOL>.json per published record) by
    reusing publish-archive's ``_build_deep_dives_bundle`` — one bundle
    implementation, no second copy. SLOW: fetches every /v1/genes record."""
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "publish_archive",
        str(repo_root / "scripts" / "release" / "publish-archive.py"),
    )
    pa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pa)
    return pa._build_deep_dives_bundle(_DEEP_DIVES_ENTRY, dry_run=False)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description=(
            f"Non-destructively sync files on Zenodo draft {DEPOSIT_ID}. "
            "Default: the 2 triage TSVs + README + metadata. This is the single "
            "safe entrypoint — it only touches the files it manages and never "
            "deletes anything else (e.g. the deep-dive tarball is preserved "
            "unless you pass --with-deep-dives to refresh it)."
        )
    )
    ap.add_argument("--with-deep-dives", action="store_true",
                    help="ALSO build + sync deep_dives_all.tar.gz (slow: fetches "
                         "every /v1/genes record; the tarball then carries the "
                         "Worker-attached deep_dive_tier)")
    ap.add_argument("--deep-dives-only", action="store_true",
                    help="sync ONLY the deep-dive tarball; leave TSVs / README / "
                         "metadata untouched")
    ap.add_argument("--replicates-only", action="store_true",
                    help="sync ONLY the reproducibility-replicate tarball + the "
                         "README / description that document it; leave the TSVs "
                         "and the deep-dive tarball untouched")
    ap.add_argument("--deposit-id", default=DEPOSIT_ID,
                    help="Zenodo deposition to sync (default: %(default)s). Pass the "
                         "draft id that cut_data_release.py prints when it opens a new "
                         "version: that draft starts with the previous version's files, "
                         "and this script refreshes the ones it manages.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the sync plan; issue no PUT / DELETE / metadata "
                         "write (skips the ~110 MB tarball build)")
    args = ap.parse_args(argv)
    deposit_id = args.deposit_id

    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        print("ZENODO_TOKEN env var required", file=sys.stderr)
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    include_tsvs = not (args.deep_dives_only or args.replicates_only)
    include_deep_dives = args.with_deep_dives or args.deep_dives_only
    include_replicates = not args.deep_dives_only
    # The README + description document every file, so they travel with either
    # the TSV sync or the replicate sync.
    include_docs = include_tsvs or include_replicates

    managed: list[Path] = []
    if include_replicates:
        managed.append(_build_replicates_tarball())
        print(f"→ built {REPLICATES_TARBALL} "
              f"({REPLICATES_TARBALL.stat().st_size / 1024**2:.1f} MB)")
    if args.replicates_only:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        README_PATH.write_text(_build_readme())
        print(f"→ wrote {README_PATH}")
        managed.append(README_PATH)
    if include_tsvs:
        # Verify both new TSVs exist + materialize the README.
        for p in NEW_FILES:
            if not p.exists():
                print(f"missing: {p}", file=sys.stderr)
                print("Run scripts/release/build_consolidated_deposit_tsvs.py first.",
                      file=sys.stderr)
                return 1
        README_PATH.write_text(_build_readme())
        print(f"→ wrote {README_PATH}")
        if not MANIFEST_PATH.exists():
            print(f"missing: {MANIFEST_PATH} — re-run "
                  "scripts/release/build_consolidated_deposit_tsvs.py", file=sys.stderr)
            return 1
        problems = check_docs_against_manifest(
            README_PATH.read_text(), _DESCRIPTION_HTML,
            json.loads(MANIFEST_PATH.read_text()),
        )
        if problems:
            print("README / description disagree with the built files — fix the "
                  "text before syncing:\n  - " + "\n  - ".join(problems), file=sys.stderr)
            return 1
        managed.extend([*NEW_FILES, README_PATH])

    if include_deep_dives and not args.dry_run:
        print("→ building deep_dives_all.tar.gz (fetching every /v1/genes "
              "record — slow) …")
        tarball = _build_deep_dive_tarball()
        print(f"  built {tarball} ({tarball.stat().st_size / 1024**2:.1f} MB)")
        managed.append(tarball)
    elif include_deep_dives and args.dry_run:
        print("→ [dry-run] would build + sync deep_dives_all.tar.gz "
              "(skipped the ~110 MB build)")

    with httpx.Client(timeout=900.0, headers=auth) as client:
        # 1. Fetch deposit state + bucket URL.
        r = client.get(f"{ZENODO_BASE}/deposit/depositions/{deposit_id}")
        r.raise_for_status()
        dep = r.json()
        state = dep.get("state")
        if state != "unsubmitted":
            print(f"⚠ deposit state is '{state}', not 'unsubmitted' — refusing "
                  f"to modify a published / submitted deposit", file=sys.stderr)
            return 1
        # The draft cut_data_release.py opens carries the release version;
        # syncing files for one release into a draft for another is the
        # mistake this catches (1.0.0 itself went out with no version set).
        draft_version = dep["metadata"].get("version")
        if draft_version != _pyproject_version():
            print(f"⚠ draft version is {draft_version!r} but pyproject.toml says "
                  f"{_pyproject_version()!r} — refusing; cut the release with "
                  "cut_data_release.py first", file=sys.stderr)
            return 1
        bucket = dep["links"].get("bucket")
        if not bucket:
            print("⚠ no bucket URL on deposit — older deposit API form?",
                  file=sys.stderr)
            return 1
        print(f"→ deposit {deposit_id} state=draft bucket={bucket}"
              + ("  [DRY RUN]" if args.dry_run else ""))

        # 2. Non-destructive, checksum-aware file sync.
        r = client.get(f"{ZENODO_BASE}/deposit/depositions/{deposit_id}/files")
        r.raise_for_status()
        existing = {f["filename"]: f for f in r.json()}
        managed_names = {p.name for p in managed}
        if include_deep_dives and args.dry_run:
            managed_names.add(_DEEP_DIVES_ENTRY["filename"])

        # 2a. Retire only this script's own obsolete TSV outputs (name-scoped),
        # and only when syncing the TSVs.
        if include_tsvs:
            for name in RETIRED_FILENAMES:
                f = existing.get(name)
                if not f:
                    continue
                if args.dry_run:
                    print(f"  [dry-run] would retire {name}")
                    continue
                dr = client.delete(
                    f"{ZENODO_BASE}/deposit/depositions/{deposit_id}/files/{f['id']}"
                )
                if dr.status_code not in (204, 200):
                    print(f"  ⚠ retire failed {name}: {dr.status_code} {dr.text[:200]}",
                          file=sys.stderr)
                    return 1
                print(f"  ✓ retired {name}")

        # 2b. Overwrite changed / new managed files; skip unchanged by MD5.
        uploaded = skipped = 0
        for p in managed:
            local_md5 = _md5(p)
            remote = existing.get(p.name)
            if remote is not None and _remote_checksum(remote) == local_md5:
                print(f"  = unchanged, skipped {p.name}")
                skipped += 1
                continue
            if args.dry_run:
                print(f"  [dry-run] would {'update' if remote else 'create'} {p.name}")
                continue
            data = p.read_bytes()
            ur = client.put(f"{bucket}/{p.name}", content=data)
            if ur.status_code not in (200, 201):
                print(f"  ⚠ upload failed {p.name}: {ur.status_code} {ur.text[:200]}",
                      file=sys.stderr)
                return 1
            verb = "updated" if remote is not None else "created"
            print(f"  ✓ {verb} {p.name} ({len(data) / 1024**2:.2f} MB)")
            uploaded += 1

        # 2c. Everything else on the deposit is preserved untouched.
        preserved = sorted(set(existing) - managed_names - set(RETIRED_FILENAMES))
        if preserved:
            print(f"→ preserved {len(preserved)} unmanaged file(s): "
                  f"{', '.join(preserved)}")
        print(f"→ file sync: {uploaded} uploaded, {skipped} unchanged, "
              f"{len(preserved)} preserved")

        # 3. Update description + title — only when syncing the TSVs (the
        # description documents them) and only if they actually differ.
        if include_docs and not args.dry_run:
            metadata = dep["metadata"]
            if (metadata.get("title") == "The accessible human surfaceome"
                    and metadata.get("description") == _DESCRIPTION_HTML):
                print("→ metadata already current — skipped")
            else:
                metadata["title"] = "The accessible human surfaceome"
                metadata["description"] = _DESCRIPTION_HTML
                mr = client.put(
                    f"{ZENODO_BASE}/deposit/depositions/{deposit_id}",
                    json={"metadata": metadata},
                    headers={**auth, "Content-Type": "application/json"},
                )
                if mr.status_code not in (200, 201):
                    print(f"  ⚠ metadata update failed: {mr.status_code} {mr.text[:500]}",
                          file=sys.stderr)
                    return 1
                print("→ description + title updated")

    print(f"\n✓ Draft {deposit_id} {'plan (dry-run)' if args.dry_run else 'updated'}.")
    print(f"  https://zenodo.org/deposit/{deposit_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
