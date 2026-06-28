"""Update an existing Zenodo draft deposit in place.

The ``publish-archive.py`` script always creates a NEW draft (mints a
new reserved DOI). When we want to keep the same DOI but replace the
files / description, the Zenodo API supports edit-in-place on draft
deposits:

  GET  /api/deposit/depositions/{id}              — fetch state + bucket URL
  GET  /api/deposit/depositions/{id}/files        — list files
  DELETE /api/deposit/depositions/{id}/files/{fid} — delete one file
  PUT  /api/files/{bucket}/{filename}             — upload (S3-style)
  PUT  /api/deposit/depositions/{id}              — patch metadata

This script targets deposit 20805384 (the benchmarking + triage data
deposit) and replaces:

  1. Old files (3 separate TSVs + README) → deleted
  2. New files (2 consolidated TSVs + README) → uploaded
  3. Description text → refreshed to match the new file structure

Run after ``scripts/release/build_consolidated_deposit_tsvs.py``
produces the new TSVs at /tmp/zenodo_deposit_consolidated/.

Environment:
  ZENODO_TOKEN — required (same scope as publish-archive.py)
"""
from __future__ import annotations

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
]
README_PATH = TMP_DIR / "README.md"

ZENODO_BASE = "https://zenodo.org/api"


def _head_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _build_readme() -> str:
    sha = _head_sha()
    return f"""# accessible-surfaceome — Zenodo deposit (benchmark, triage + deep-dive data outputs)

This deposit contains the data outputs for the
[accessible-surfaceome](https://github.com/Deliverome-Project/accessible-surfaceome)
project. The repository code itself is archived separately (GitHub-
Zenodo auto-archive + Software Heritage continuous crawl).

**Reserved DOI:** `10.5281/zenodo.20805384` — preserved across draft
updates; activates on publish.

**Scope of this record snapshot:** the **triage** (genome-wide Sonnet
sweep + PubMed-augmented rescue lane) and **benchmark** (147-gene
multi-replicate) data files below. Additional content listed in the
"Coming in subsequent draft updates" section will be added in
place — the reserved DOI does not change.

All data files were assembled at deposit time by
[`scripts/release/build_consolidated_deposit_tsvs.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{sha}/scripts/release/build_consolidated_deposit_tsvs.py)
in the repo at commit `{sha[:12]}`. Anyone can regenerate them from the
public read-only API documented below.

## Coming in subsequent draft updates (before publish)

These are the publication-workflow items that the
[`scripts/release/`](https://github.com/Deliverome-Project/accessible-surfaceome/tree/{sha}/scripts/release/)
pipeline expects to ship alongside the data — placeholders are wired
in the source script but the artifacts themselves are still in
iteration. Marked as checkboxes for tracking:

- [ ] **`deep_dives_all.tar.gz`** — gzipped tarball, one `<SYMBOL>.json`
  per published `SurfaceomeRecord` (full evidence chain + per-claim
  verbatim quotes). Held back until the deep-dive prompt + schema
  iteration converges; corresponds to the commented-out
  `{{"deep_dives_bundle": True, ...}}` entry in
  [`publish-archive.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{sha}/scripts/release/publish-archive.py)'s
  `EXTRA_FILES`.
- [ ] **`manuscript.pdf`** + **`manuscript.xml`** — the publication
  PDF (built upstream from `.docx` / `.tex` / `.md`) and a
  pandoc-generated JATS XML representation for PMC indexing +
  downstream text-mining. Held back until the manuscript is ready;
  corresponds to the commented-out `{{"manuscript": True, ...}}`
  entry in `EXTRA_FILES`.
- [ ] **`related_identifiers`** linking this record to the
  **code-record concept DOI** (auto-archived from the next tagged
  GitHub Release). The link will be added by editing
  `publish-archive.py`'s `SEED_METADATA.related_identifiers` once the
  first code release ships.

Already shipping in this draft:

- [x] `triage-runs-genome-with-reasoning.tsv` (consolidated ncbi + pubmed)
- [x] `triage-benchmark-with-reasoning.tsv` (multi-replicate, truth-joined)
- [x] `deep-dive-preset-membership.tsv` — per-gene boolean membership
  in each of the four catalog presets (Canonical / Likely / Cell-
  state induced / Cell-type restricted) plus the three induction sub-
  axes (Disease / Stress / Immune). Predicates mirror the viewer
  toolbar at [`viewer/lib/catalog-presets.ts`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{sha}/viewer/lib/catalog-presets.ts);
  the Python mirror at [`src/accessible_surfaceome/release/catalog_presets.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{sha}/src/accessible_surfaceome/release/catalog_presets.py)
  is the deposit's source of truth. Drift between the two surfaces
  is caught by a test (`tests/test_catalog_presets_mirror.py`).
  Audit columns (`induction_trigger`, `surface_call_reason`,
  `state_dependence`, `evidence_grade`, `surface_specificity`,
  `ecd_accessibility_class`, `confidence`, `evidence_density`,
  `surface_accessibility`) carry the raw input fields the predicates
  read so a reader can re-derive any preset locally without re-
  fetching the full `annotation_json`.
- [x] In-deposit `README.md` (this file)
- [x] Reserved DOI wired into [`scripts/figures/embed_figure_gist_metadata.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{sha}/scripts/figures/embed_figure_gist_metadata.py)'s
  `ZENODO_DATA_DOI` so figure PDF/PNG metadata can pre-bake the citation.

## Files

### 1. `triage-runs-genome-with-reasoning.tsv`

Long-format TSV, **21,950 rows** total, covering every genome-wide
Sonnet 4.6 inference call: the canonical NCBI-context sweep
(`genome_full_sonnet_ncbi_v2`, 19,324 rows = 1 rep per gene across the
M1 candidate universe) PLUS the PubMed-augmented rescue lane
(`genome_full_sonnet_pubmed_ncbi_v1`, 2,626 rows = the
ambiguous-reason zero-DB Sonnet-no slice that we re-ran with PubMed
evidence). A `run_id` column at position 1 tags every row so a reader
can split or filter by lane.

For the 2,624 genes in the rescue slice this means **2 rows per gene**
(one NCBI, one PubMed); for the remaining ~16,700 genes it's a single
NCBI row.

| Column | Meaning |
|---|---|
| `run_id` | `genome_full_sonnet_ncbi_v2` (canonical) or `genome_full_sonnet_pubmed_ncbi_v1` (PubMed rescue) |
| `gene_symbol` | HGNC gene symbol |
| `uniprot_acc` | UniProt accession (canonical isoform) |
| `hgnc_id`, `ensembl_gene` | additional stable IDs |
| `db_uniprot`, `db_go`, `db_surfy`, `db_cspa`, `db_hpa` | 0/1 — does each surface-DB source vote "surface" for this gene? |
| `n_db_surface` | sum of the 5 DB votes (0–5) |
| `model` | Anthropic model identifier (`claude-sonnet-4-6` only in this file) |
| `prompt_variant` | `ncbi` or `pubmed_ncbi` |
| `replicate` | replicate index within the sweep (always `1` for both run_ids) |
| `predicted_verdict` | model verdict: `yes` / `contextual` / `no` |
| `predicted_reason` | short controlled-vocab reason tag |
| `predicted_confidence` | `low` / `medium` / `high` |
| `prompt_tokens`, `completion_tokens`, `cache_creation_tokens`, `cache_read_tokens` | per-call token counts |
| `n_web_searches` | number of web tool calls in this run |
| `cost_usd`, `latency_s` | computed dollar cost + wall-clock seconds |

**Read-side reconciliation rule.** When the same gene has both an
NCBI and a PubMed row, downstream analyses prefer the PubMed verdict
when it is MORE INCLUSIVE than NCBI's (i.e. PubMed says
`yes`/`contextual` while NCBI says `no`). PubMed `no` never overrides
an NCBI `yes`/`contextual` — `no` from PubMed doesn't constitute
evidence of absence. The live `/v1/catalog` endpoint applies this rule
server-side.

**Reproducible from two endpoints + a concat:**

```bash
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v2'        | sed '1!{{/^run_id\\t/d;}}' | awk -F'\\t' 'BEGIN{{OFS="\\t"}} NR==1{{print "run_id",$0}} NR>1{{print "genome_full_sonnet_ncbi_v2",$0}}'        > genome.tsv
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_pubmed_ncbi_v1' | tail -n +2 | awk -F'\\t' 'BEGIN{{OFS="\\t"}}{{print "genome_full_sonnet_pubmed_ncbi_v1",$0}}'       >> genome.tsv
```

### 2. `triage-benchmark-with-reasoning.tsv`

Long-format **multi-replicate** TSV, **4,410 rows**, covering the
147-gene curated benchmark across all 3 production models (Haiku 4.5,
Sonnet 4.6, Opus 4.8) and 4 prompt variants (`naive`, `ncbi`,
`web_ncbi`, `pubmed_ncbi`). Each `(gene × model × variant)` cell
appears as **3 rows** — one per replicate — so a reader can see
per-rep variability instead of a pre-aggregated majority view.

Same columns as the previous version's bench file PLUS the curated
truth label triple AND a `truth_class` column carrying the bench's
disagreement bucket (e.g. `disagreement_rich_positive`,
`wrong_side_borderline`, `induced_borderline`).

| Extra columns (vs. genome file) | Meaning |
|---|---|
| `truth_verdict` | curated truth: `yes` / `contextual` / `no` |
| `truth_signal` | curated signal: `likely_accessible` / `possibly_accessible` / `unlikely` / etc. |
| `truth_reason` | curated reason tag (controlled vocab) |
| `truth_class` | disagreement-bucket label for the bench gene |

**Reproducible from two endpoints + a client-side join:**

```bash
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v2' \\
    > bench_predictions.tsv      # multi-rep predictions
curl 'https://api.deliverome.org/surfaceome/v1/benchmark' \\
    > bench_truth.json           # curated truth + class per gene
# then join on gene_symbol; see build_consolidated_deposit_tsvs.py
```

## Reconciliation rule, in code

```python
def reconciled_verdict(ncbi: str, pubmed: str | None) -> str:
    # If pubmed is more inclusive than ncbi, prefer pubmed.
    if pubmed in ('yes', 'contextual') and ncbi == 'no':
        return pubmed
    return ncbi
```

## Repository, code archive, related identifiers

- **Source code:** <https://github.com/Deliverome-Project/accessible-surfaceome>
- **Pinned to commit:** `{sha}`
- **Code release archive:** the GitHub-Zenodo auto-archive mints one
  DOI per tagged release; the latest is linked from this record's
  *Related identifiers*.
- **Continuous source archive:** Software Heritage. The repo's SWHID
  is in this record's *Related identifiers* (relation `isSupplementTo`).

## License

CC-BY-4.0 for the data in this deposit. Same as the upstream
constituent sources (UniProt, GO, HPA — all CC-BY; HPA is CC-BY-4.0).
SURFY and CSPA are published academic resources used under their
respective terms; see the upstream papers.
"""


_DESCRIPTION_HTML = (
    "Benchmark, triage, and deep-dive data outputs for the "
    "accessible-surfaceome project. The current draft snapshot ships "
    "two consolidated data files (triage + benchmark) plus an "
    "in-deposit README documenting every column and the source-join "
    "recipe. <b>Deep-dive `SurfaceomeRecord` JSONs and the manuscript "
    "bundle (PDF + JATS XML) are placeholder slots</b> — they'll be "
    "added in subsequent draft updates as that work finishes, against "
    "the same reserved DOI (10.5281/zenodo.20805384). See the in-"
    "deposit README's \"Coming in subsequent draft updates\" section "
    "for the full list and provenance of items pending.<br><br>"
    "<b>triage-runs-genome-with-reasoning.tsv</b> — 21,950-row "
    "long-format TSV consolidating the canonical NCBI-context sweep "
    "(19,324 genes × 1 rep, ~19k-gene M1 candidate universe) AND the "
    "PubMed-augmented rescue lane (2,626 genes × 1 rep, the "
    "ambiguous-reason zero-DB Sonnet-no slice). A `run_id` column "
    "tags every row so the lanes can be split or merged at read time. "
    "For the 2,624 rescued-slice genes this means two rows per gene "
    "(one NCBI, one PubMed); for the other ~16,700 it's a single NCBI "
    "row. The read-side reconciliation rule (prefer PubMed when it is "
    "more inclusive than NCBI) is documented in the README and is "
    "applied server-side by the live /v1/catalog endpoint.<br><br>"
    "<b>triage-benchmark-with-reasoning.tsv</b> — 4,410-row "
    "long-format multi-replicate TSV covering the 147-gene curated "
    "benchmark across Haiku 4.5, Sonnet 4.6, and Opus 4.8 under 4 "
    "prompt variants each. Each (gene × model × variant) cell appears "
    "as 3 replicate rows so a reader can see per-rep variability "
    "directly. Curated truth verdict / signal / reason / class are "
    "joined in per gene.<br><br>"
    "All files are reproducible end-to-end from the public read-only "
    "API at https://api.deliverome.org/surfaceome/v1/ ; the included "
    "README.md documents the exact endpoint joins. The repository "
    "code itself is archived separately via the GitHub-Zenodo "
    "auto-archive (one DOI per tagged release) and via Software "
    "Heritage (continuous crawl, content-addressed SWHIDs). This "
    "record is the supplementary data layer; the related-identifiers "
    "field links the two."
)


def main() -> int:
    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        print("ZENODO_TOKEN env var required", file=sys.stderr)
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    # Verify both new TSVs exist.
    for p in NEW_FILES:
        if not p.exists():
            print(f"missing: {p}", file=sys.stderr)
            print("Run scripts/release/build_consolidated_deposit_tsvs.py first.",
                  file=sys.stderr)
            return 1

    # Materialize the README at the standard path.
    README_PATH.write_text(_build_readme())
    print(f"→ wrote {README_PATH}")

    with httpx.Client(timeout=300.0, headers=auth) as client:
        # 1. Fetch deposit state + bucket URL.
        r = client.get(f"{ZENODO_BASE}/deposit/depositions/{DEPOSIT_ID}")
        r.raise_for_status()
        dep = r.json()
        state = dep.get("state")
        if state != "unsubmitted":
            print(f"⚠ deposit state is '{state}', not 'unsubmitted' — refusing "
                  f"to modify a published / submitted deposit", file=sys.stderr)
            return 1
        bucket = dep["links"].get("bucket")
        if not bucket:
            print("⚠ no bucket URL on deposit — older deposit API form?",
                  file=sys.stderr)
            return 1
        print(f"→ deposit {DEPOSIT_ID} state=draft bucket={bucket}")

        # 2. List + delete existing files.
        r = client.get(f"{ZENODO_BASE}/deposit/depositions/{DEPOSIT_ID}/files")
        r.raise_for_status()
        existing = r.json()
        print(f"→ deleting {len(existing)} existing files")
        for f in existing:
            fid = f["id"]
            fname = f["filename"]
            dr = client.delete(
                f"{ZENODO_BASE}/deposit/depositions/{DEPOSIT_ID}/files/{fid}"
            )
            if dr.status_code not in (204, 200):
                print(f"  ⚠ delete failed {fname}: {dr.status_code} {dr.text[:200]}",
                      file=sys.stderr)
                return 1
            print(f"  ✓ deleted {fname}")

        # 3. Upload new files via the S3-style bucket API.
        files_to_upload = [*NEW_FILES, README_PATH]
        print(f"→ uploading {len(files_to_upload)} files")
        for p in files_to_upload:
            data = p.read_bytes()
            ur = client.put(f"{bucket}/{p.name}", content=data)
            if ur.status_code not in (200, 201):
                print(f"  ⚠ upload failed {p.name}: {ur.status_code} {ur.text[:200]}",
                      file=sys.stderr)
                return 1
            print(f"  ✓ uploaded {p.name} ({len(data) / 1024**2:.2f} MB)")

        # 4. Update description.
        metadata = dep["metadata"]
        metadata["title"] = (
            "accessible-surfaceome — benchmark, triage, and deep-dive "
            "data outputs"
        )
        metadata["description"] = _DESCRIPTION_HTML
        mr = client.put(
            f"{ZENODO_BASE}/deposit/depositions/{DEPOSIT_ID}",
            json={"metadata": metadata},
            headers={**auth, "Content-Type": "application/json"},
        )
        if mr.status_code not in (200, 201):
            print(f"  ⚠ metadata update failed: {mr.status_code} {mr.text[:500]}",
                  file=sys.stderr)
            return 1
        print("→ description + title updated")

    print(f"\n✓ Draft {DEPOSIT_ID} updated.")
    print(f"  https://zenodo.org/deposit/{DEPOSIT_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
