"""Sync the consolidated TSVs + README + description onto a release draft.

Step 2 of the numbered-release procedure (scripts/release/README.md,
"Numbered data release"). ``cut_data_release.py --version X.Y.Z --execute``
opens a DRAFT new version of the data record (concept DOI
10.5281/zenodo.20805383) carrying ``deep_dives_X.Y.Z.tar.gz`` and the
reproducibility-replicate bundle, and prints that draft's deposition id.
The draft inherits every other file, and the description, from the previous
version, so until this script runs it describes the previous release.
After ``build_consolidated_deposit_tsvs.py`` has written the TSVs:

    uv run python scripts/release/update_zenodo_draft.py --deposit-id <id> --dry-run
    uv run python scripts/release/update_zenodo_draft.py --deposit-id <id>

There is no default deposit: ``--deposit-id`` is required for anything that
talks to Zenodo, and the draft's metadata ``version`` must equal the release
version (``--version``, default pyproject.toml). ``--dry-run`` without
``--deposit-id`` renders the README + description into ``--work-dir`` and
runs the document checks with no network calls at all.

Zenodo deposit API used (edit-in-place on an unpublished draft):

  GET  /api/deposit/depositions/{id}              — fetch state + bucket URL
  GET  /api/deposit/depositions/{id}/files        — list files + checksums
  DELETE /api/deposit/depositions/{id}/files/{fid} — delete one file
  PUT  /api/files/{bucket}/{filename}             — upload (S3-style)
  PUT  /api/deposit/depositions/{id}              — patch metadata

The sync is NON-DESTRUCTIVE and checksum-aware, and touches only the files
this script manages (the three TSVs, the replicate tarball, README.md):

  1. Managed files whose content changed (local MD5 != remote checksum)
     are overwritten in place via the bucket PUT. Unchanged ones are skipped.
  2. Files THIS script used to ship but no longer does are deleted ONLY if
     their exact names are listed in RETIRED_FILENAMES.
  3. Every other file on the draft (``deep_dives_X.Y.Z.tar.gz``, uploaded by
     cut_data_release.py) is left untouched and reported as preserved.
  4. Description + title are refreshed only if they differ.

Before any write it checks the draft against ``release_filenames``, the list
the README documents: a documented file that is neither on the draft nor
uploaded by this run is a refusal (the README would describe a file the
record lacks), as is a ``deep_dives*`` tarball for any other version; any
other undocumented file left on the draft is reported so it can be removed
in the Zenodo UI before publishing.

Environment:
  ZENODO_TOKEN — required whenever --deposit-id is given
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
# Matches build_consolidated_deposit_tsvs.py's default --out-dir.
DEFAULT_WORK_DIR = Path("/tmp/zenodo_deposit_consolidated")
# Built by build_consolidated_deposit_tsvs.py, in README order.
GENOME_TSV = "triage-runs-genome-with-reasoning.tsv"
BENCH_TSV = "triage-benchmark-with-reasoning.tsv"
PRESETS_TSV = "deep-dive-preset-membership.tsv"
TSV_FILENAMES: tuple[str, ...] = (GENOME_TSV, BENCH_TSV, PRESETS_TSV)
README_NAME = "README.md"
DESCRIPTION_NAME = "description.html"  # rendered next to the README for review
# Row counts of the built files, written by build_consolidated_deposit_tsvs.py.
MANIFEST_NAME = "deposit_manifest.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"
# Reproducibility replicates (Supplementary Figure 16): the frozen bundle, tarred
# deterministically so an unchanged bundle re-syncs as "unchanged".
REPLICATES_BUNDLE = REPO_ROOT / "data/processed/deep_dive_concordance_v1"
REPLICATES_TARBALL_NAME = "deep-dive-reproducibility-replicates-v1.tar.gz"

CONCEPT_DOI = "10.5281/zenodo.20805383"
RECORD_TITLE = "The accessible human surfaceome"
API_BASE = "https://api.deliverome.org/surfaceome/v1"
LICENSING_URL = "https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/LICENSING.md"

# Filenames THIS script used to ship but no longer does. They are deleted
# from the draft only if present — surgical and name-scoped. This is the
# ONLY path that ever issues a DELETE. Files managed by cut_data_release.py
# (deep_dives_X.Y.Z.tar.gz) must NOT appear here.
RETIRED_FILENAMES: list[str] = []

ZENODO_BASE = "https://zenodo.org/api"

_NUMBER_WORDS = {3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}


def deep_dive_tarball_name(version: str) -> str:
    """The tarball ``cloud.record_history.releases.export_release`` writes."""
    return f"deep_dives_{version}.tar.gz"


def release_filenames(version: str) -> list[str]:
    """Every file a release draft holds once this script has synced it, in
    README order. The README documents exactly these (check_docs_file_list)."""
    return [
        GENOME_TSV,
        BENCH_TSV,
        deep_dive_tarball_name(version),
        PRESETS_TSV,
        REPLICATES_TARBALL_NAME,
        README_NAME,
    ]


def _n_data_files_word(version: str) -> str:
    n = len(release_filenames(version)) - 1  # minus the README itself
    return _NUMBER_WORDS.get(n, str(n))


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
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _build_readme(version: str) -> str:
    sha = _head_sha()
    dd = deep_dive_tarball_name(version)
    n_word = _n_data_files_word(version)
    return f"""# The accessible human surfaceome — data release {version}

Data outputs from the **accessible-surfaceome** project, which reconciles which
human proteins are reachable on the outside of the cell — the "surfaceome" that
most antibody, ADC, and cell-therapy drugs act on. The main public surface
databases disagree often, so the project scores every protein-coding gene with
an LLM agent pipeline: a fast genome-wide **triage** pass, a **benchmark**
against curated ground truth, and an evidence-cited **deep dive** on the strong
candidates. This deposit holds the data those three stages produced.

**Release:** `{version}`. **Concept DOI:** `{CONCEPT_DOI}` always resolves to the
latest release of this record. Each release also gets its own version DOI
(shown on its Zenodo page), which pins exactly that release's files; cite the
version DOI to point at these bytes.

{n_word} data files + this README:

| # | File | What it is |
|---|---|---|
| 1 | `{GENOME_TSV}` | genome-wide first-pass triage, every run |
| 2 | `{BENCH_TSV}` | the 147-gene accuracy benchmark, every replicate |
| 3 | `{dd}` | the evidence-cited deep-dive records of release {version} |
| 4 | `{PRESETS_TSV}` | catalog preset membership per deep-dive gene |
| 5 | `{REPLICATES_TARBALL_NAME}` | run-to-run reproducibility study (not published records) |

Each is a flat TSV or a gzipped tarball of JSON / Markdown, readable with any
TSV reader (pandas, R) or `tar xzf` — no project code needed. Each is also
reproducible from the project's public read-only API (recipes at the end).

---

## 1. `{GENOME_TSV}` — genome-wide first-pass triage

**33,728 rows**, one per (gene × run). The triage agent is a single LLM call per
gene that reads a context block and returns a surface-accessibility verdict
(`yes` / `contextual` / `no`), a controlled-vocabulary reason, a confidence and
its free-text reasoning, with per-call token / cost / latency accounting.

Five runs, tagged by the `run_id` column:

- **`genome_full_sonnet_ncbi_v2`** — the primary sweep with NCBI gene-summary
  context: **19,324 genes**, one row each.
- Four **PubMed-context rescue lanes** — **14,404 rows covering 14,395 distinct
  genes** — which re-triage genes the primary sweep called `no` and at most one
  surface database supports, with PubMed abstracts in the prompt:
  - **`genome_full_sonnet_pubmed_ncbi_v1`** — 2,626 genes in no database whose
    `no` reason was ambiguous (endomembrane, secreted, inner leaflet, …)
  - **`genome_intracellular_pubmed_ncbi_v1`** — 10,287 genes in no database
    called cytoplasmic, nuclear or mitochondrial
  - **`genome_1db_trim_pubmed_ncbi_v1`** — 1,417 genes in exactly one database
  - **`genome_optcut_zerodb_pubmed_ncbi_v1`** — 74 genes that moved from one
    database to none under the optimized CSPA cutoff

  A re-triaged gene carries an NCBI row plus its PubMed row; every other gene
  carries one row. The lanes are disjoint except for 9 genes the 74-gene lane
  re-ran after an earlier lane, which carry a row from each (hence 14,404 rows
  but 14,395 genes). A few lane rows have `prompt_variant` = `naive`: the PubMed
  fetch failed for that gene and the call ran on the gene symbol alone.

| Column | Meaning |
|---|---|
| `run_id` | which run the row is from (see above) |
| `gene_symbol` | HGNC gene symbol |
| `uniprot_acc`, `hgnc_id`, `ensembl_gene` | stable identifiers |
| `db_uniprot`, `db_go`, `db_surfy`, `db_cspa`, `db_hpa` | 0/1 — does each of the five surface databases (UniProt, GO, SURFY, CSPA, HPA) call this gene surface? |
| `n_db_surface` | how many of the five agree (0–5) |
| `model`, `prompt_variant`, `replicate` | which model / context variant / replicate produced the row |
| `predicted_verdict` | `yes` / `contextual` / `no`; empty when `error` is set |
| `predicted_reason` | short controlled-vocabulary reason tag; empty when `error` is set |
| `predicted_confidence` | `low` / `medium` / `high` |
| token / cost / latency columns | `prompt_tokens`, `completion_tokens`, `cache_creation_tokens`, `cache_read_tokens`, `n_web_searches`, `cost_usd`, `latency_s` |
| `predicted_key_uncertainty` | optional — the agent's one-line statement of what would change its call; often blank |
| `verdict_reasoning` | the agent's free-text rationale for the verdict |
| `error` | empty for a normal call. Otherwise why the row has no verdict: `refusal` (the model's safety classifier declined), `schema mismatch after retry: …` (the verdict / reason pair was invalid twice), `could not parse JSON from response`, or another runner error message. These rows have empty `predicted_verdict` and `predicted_reason`. |

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

## 2. `{BENCH_TSV}` — the 147-gene accuracy benchmark

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

followed by the triage columns of file 1 **except `run_id`** — every row is
from the benchmark run `mainbench_canonical_v2`.

---

## 3. `{dd}` — evidence-cited per-gene records

**5,332 genes**, the members of data release {version}: each gene's deep-dive
record exactly as the public API served it when the release was cut, frozen in
the project's record history. Each gene has up to three files under `genes/`,
plus one `manifest.tsv` at the root (`tar tzf` lists them):

| File | Contents |
|---|---|
| `genes/<SYMBOL>.json` | the SurfaceomeRecord: the structured surface call, every structured attribute (the filters block and the deterministic features), and the deep-dive classification below. **Records do not embed their evidence**: the evidence ledger is split out into the next file. |
| `genes/<SYMBOL>.evidence.json` | `{{"gene", "evidence", "papers"}}` — `evidence` is the ledger (each item a claim with its verbatim, substring-anchored source quotes) and `papers` is citation metadata (title, byline, journal, year) keyed by the `source_id` each quote cites (e.g. `PMID:…`, `PMC:…`) |
| `genes/<SYMBOL>.md` | the human-readable Markdown brief |
| `manifest.tsv` | one row per gene — see below |

A gene whose evidence ledger or Markdown brief was never archived has no file
for that part, and empty manifest columns for it.

The classification on each record:

- **`deep_dive_tier`** — `canonical` (high-confidence surface) / `likely` /
  `low` / `uncertain` / `no`
- **`deep_dive_facet`** — `induced` (surface presence gained on a cell state)
  or `cell_type_restricted` (constitutively surface on specific cell types
  only), on `canonical` and `likely` genes where it applies; otherwise null

The tier uses the same rule the project's public catalog applies and is attached
to each record as served, so the classification here matches that catalog.

**`manifest.tsv` — two kinds of hash.** Use the `*_sha256` columns to verify
files; the `*_hash` columns are not file checksums.

| Column | Meaning |
|---|---|
| `gene_symbol`, `hgnc_id` | the gene |
| `revision` | the gene's record-history revision frozen in this release |
| `json_hash`, `evidence_hash`, `md_hash` | record-history **content hashes**: sha256 of a normalized form — the JSON re-serialized key-sorted without whitespace, minus fields that change on every serve without changing content (`record_generated_at`, nested `retrieved_at`); the Markdown with its "generated <timestamp>" stamp normalized. They identify the revision (`/v1/genes/<SYMBOL>/revisions` lists the same values) and will **not** match `sha256sum` of the files. |
| `json_sha256`, `evidence_sha256`, `md_sha256` | plain sha256 of the exact bytes of `genes/<SYMBOL>.json`, `.evidence.json` and `.md` in this tarball; empty where the file is absent |

```python
import csv, hashlib
parts = {{"json_sha256": ".json", "evidence_sha256": ".evidence.json", "md_sha256": ".md"}}
for row in csv.DictReader(open("manifest.tsv"), delimiter="\\t"):
    for col, ext in parts.items():
        if row[col]:
            data = open(f"genes/{{row['gene_symbol']}}{{ext}}", "rb").read()
            assert hashlib.sha256(data).hexdigest() == row[col], (row["gene_symbol"], col)
```

The same bytes are served per gene at
`{API_BASE}/releases/{version}/genes/<SYMBOL>` (record), `…/<SYMBOL>/evidence`
and `…/<SYMBOL>.md`. `/v1/genes/<SYMBOL>` serves the *current* record, which
may have changed since this release.

---

## 4. `{PRESETS_TSV}` — catalog preset membership per deep-dive gene

One row per gene with a deep-dive record. The `in_*` columns (1/0) say whether
the gene falls in each of the public catalog's presets (`canonical`, `likely`,
`induced`, `cell_type_restricted`), computed with the same predicates the
catalog uses (`accessible_surfaceome.release.catalog_presets`). The
`induction_*` columns split `induced` by trigger, and the remaining columns are
the record fields those predicates read, so any preset can be re-derived
locally.

---

## 5. `{REPLICATES_TARBALL_NAME}` — run-to-run reproducibility

**Not published records.** 50 deep-dive genes drawn at random (two disjoint
batches of 25) and re-analyzed to measure reproducibility (Supplementary
Figure 16 of the manuscript). Three record sets, one line per gene in each
(`{{"hgnc_symbol", "sample_batch", "record"}}`, `record` a full SurfaceomeRecord
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
`{API_BASE}/` (no credentials). The triage exports need `&with_reasoning=1`:
without it they omit `predicted_key_uncertainty` and `verdict_reasoning`.

```
# File 1 — the five genome runs (prefix each row with its run_id, then concatenate)
curl '{API_BASE}/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v2&with_reasoning=1'
curl '{API_BASE}/triage/export.tsv?run_id=genome_full_sonnet_pubmed_ncbi_v1&with_reasoning=1'
curl '{API_BASE}/triage/export.tsv?run_id=genome_intracellular_pubmed_ncbi_v1&with_reasoning=1'
curl '{API_BASE}/triage/export.tsv?run_id=genome_1db_trim_pubmed_ncbi_v1&with_reasoning=1'
curl '{API_BASE}/triage/export.tsv?run_id=genome_optcut_zerodb_pubmed_ncbi_v1&with_reasoning=1'

# File 2 — benchmark predictions + curated truth (join on gene_symbol)
curl '{API_BASE}/triage/export.tsv?run_id=mainbench_canonical_v2&with_reasoning=1'
curl '{API_BASE}/benchmark'

# File 3 — release {version}'s deep-dive records, byte-identical to the tarball
curl '{API_BASE}/releases/{version}'                       # members: every gene + its revision
curl '{API_BASE}/releases/{version}/genes/EGFR'            # genes/EGFR.json
curl '{API_BASE}/releases/{version}/genes/EGFR/evidence'   # genes/EGFR.evidence.json
curl '{API_BASE}/releases/{version}/genes/EGFR.md'         # genes/EGFR.md

# File 4 — preset membership: each deep-dive gene's `ddf` block on the catalog,
# run through accessible_surfaceome.release.catalog_presets
curl '{API_BASE}/catalog'

# File 5 — the reproducibility replicates (NOT published records)
curl '{API_BASE}/replicates'                 # study + gene index
curl '{API_BASE}/genes/M6PR/replicates'      # one gene's replicates
curl '{API_BASE}/genes/M6PR/replicates/deep_dive_concordance_v1/full_rerun'
```

## License

The data in this deposit is released under CC BY 4.0. It is derived from public
sources that keep their own terms; the per-source table is in the project's
[LICENSING.md]({LICENSING_URL}). In brief: UniProt, GO, the Human Protein
Atlas, JensenLab COMPARTMENTS, AlphaFold DB, the Schweke homo-oligomer atlas and
the SURFACE-Bind prediction dataset are CC BY 4.0 (the SURFACE-Bind code is
BSD-3-Clause); CSPA is CC0; SURFY's prediction table is published for open
download with no stated reuse terms; OpenCell is CC BY-SA 4.0 (share-alike);
DeepTMHMM runs under DTU Health Tech's academic licence, and only its derived
topology predictions are included here, not the tool. The files carry derived
values (flags, scores, identifiers, coded reasons, model-written reasoning) and
the short source quotes in the evidence ledgers, not upstream data files.

## Source

Produced by the accessible-surfaceome project
(<https://github.com/Deliverome-Project/accessible-surfaceome>, commit
`{sha[:12]}`). The manuscript is deposited as a separate Zenodo record under its
bioRxiv DOI, not in this record.
"""


def _description_html(version: str) -> str:
    dd = html.escape(deep_dive_tarball_name(version))
    n_word = _n_data_files_word(version).lower()
    return (
        f"Data release {version} of the accessible-surfaceome project: "
        "benchmark, triage, and deep-dive data outputs. The concept DOI "
        f"{CONCEPT_DOI} resolves to the latest release; this version's own DOI "
        f"pins these files. This version ships {n_word} data files plus an "
        "in-deposit README documenting every file and column and how to "
        "rebuild each from the public API.<br><br>"
        f"<b>{GENOME_TSV}</b> — 33,728-row "
        "long-format TSV, with each call's verdict, reason, confidence and "
        "free-text reasoning, consolidating the genome-wide Sonnet+NCBI sweep "
        "(19,324 genes × 1 rep) AND the four PubMed-context rescue "
        "lanes (14,404 rows, 14,395 distinct genes) that re-triage the genes "
        "it called no with at most one supporting database. A `run_id` column "
        "tags every row so the lanes can be split or merged at read time; each "
        "re-run gene has an NCBI row plus its PubMed row(s). The "
        "read-side reconciliation rule (prefer PubMed when it is more "
        "inclusive than NCBI) is documented in the README and applied "
        "server-side by the live /v1/catalog endpoint.<br><br>"
        f"<b>{BENCH_TSV}</b> — 7,938-row long-format "
        "multi-replicate TSV covering the 147-gene curated benchmark across 8 "
        "models with uneven prompt-variant coverage (Haiku 4.5 + Sonnet 4.6: "
        "all 4 variants; Opus 4.8, Haiku 5.5, Sonnet 5.5: naive + ncbi; Sonnet 5, "
        "Opus 5: ncbi; Opus 5.5: ncbi + ncbi at low reasoning effort) — 18 "
        "(model × variant) cells × 3 replicates × 147 genes — with each "
        "call's free-text reasoning and the curated truth verdict / signal / "
        "reason / class joined onto every row.<br><br>"
        f"<b>{dd}</b> — the 5,332 deep-dive records of release {version}, "
        "frozen from the project's record history. Per gene: "
        "genes/&lt;SYMBOL&gt;.json (the SurfaceomeRecord with every structured "
        "attribute and the deep-dive classification, deep_dive_tier + "
        "deep_dive_facet; records do not embed their evidence), "
        "genes/&lt;SYMBOL&gt;.evidence.json (the evidence ledger with "
        "per-claim verbatim quotes, plus citation metadata for every cited "
        "paper) and genes/&lt;SYMBOL&gt;.md (the Markdown brief); manifest.tsv "
        "lists each gene's revision with record-history content hashes and the "
        "plain sha256 of every file. The same bytes are served at "
        f"/v1/releases/{version}/genes/{{symbol}}.<br><br>"
        f"<b>{PRESETS_TSV}</b> — one row per deep-dive gene "
        "with 1/0 membership in each public-catalog preset (canonical, likely, "
        "induced, cell-type restricted) and the record fields the presets "
        "read.<br><br>"
        f"<b>{REPLICATES_TARBALL_NAME}</b> — run-to-run "
        "reproducibility replicates, NOT published records: for 50 randomly "
        "sampled deep-dive genes, the published record as served when the "
        "study ran, a full from-scratch re-run with the same prompts, and a "
        "fixed-evidence replay (builders + synthesizer only). Source data for "
        "Supplementary Figure 16; also queryable at /v1/replicates.<br><br>"
        f"All data files are reproducible from the public read-only API at "
        f"{API_BASE}/ (no credentials). License: CC BY 4.0; upstream "
        "sources keep their own terms (see LICENSING.md in the project "
        "repository)."
    )


# Section headings name the deposit files: "## 1. `file` — …".
_README_FILE_HEADING = re.compile(r"^## \d+\. `([^`]+)`", re.MULTILINE)


def check_docs_file_list(readme: str, description: str, version: str) -> list[str]:
    """The README / description describe exactly the files the draft will hold.

    Every data file in ``release_filenames`` must have a numbered section in
    the README and be named in the description; every numbered README
    section must name a file in that list; the stated file count must match.
    This is what caught the README still documenting ``deep_dives_all.tar.gz``
    after releases switched to ``deep_dives_X.Y.Z.tar.gz``.
    """
    problems = []
    data_files = [n for n in release_filenames(version) if n != README_NAME]
    described = _README_FILE_HEADING.findall(readme)
    for name in data_files:
        if name not in described:
            problems.append(f"README has no section for {name}, which the draft will hold")
        if name not in html.unescape(description):
            problems.append(f"description does not name {name}")
    for name in described:
        if name not in data_files:
            problems.append(f"README documents {name}, which the draft will not hold")
    if len(described) != len(set(described)):
        problems.append("README documents a file in more than one section")
    word = _n_data_files_word(version)
    if f"{word} data files" not in readme:
        problems.append(f"README does not say '{word} data files'")
    if f"{word.lower()} data files" not in description:
        problems.append(f"description does not say '{word.lower()} data files'")
    if version not in readme or version not in description:
        problems.append(f"README / description do not state release {version}")
    return problems


def check_docs_against_manifest(readme: str, description: str,
                                manifest: dict, version: str) -> list[str]:
    """Problems with the README / description given the files actually built.

    The README and description state row counts in prose, and those went
    stale before (a deposit described 2,626 PubMed rows long after there were
    14,404, and 5,130 records after the cohort grew). Every count the
    manifest records has to appear in both, every built file has to be one
    this script uploads, and the file list has to match the draft's
    (check_docs_file_list).
    """
    problems = check_docs_file_list(readme, description, version)
    for name in manifest["files"]:
        if name not in TSV_FILENAMES:
            problems.append(f"{name} is built but not in TSV_FILENAMES, so it would not be uploaded")
    totals = {
        "genome rows": manifest["genome_rows"],
        "benchmark rows": manifest["benchmark_rows"],
        "deep-dive records": manifest["deep_dive_records"],
    }
    # Written by builds since the PubMed lanes overlapped; older manifests lack them.
    for key, label in (("genome_pubmed_rows", "PubMed-lane rows"),
                       ("genome_pubmed_genes", "PubMed-lane distinct genes")):
        if key in manifest:
            totals[label] = manifest[key]
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


def check_draft_files(existing: set[str], uploading: set[str], version: str) -> tuple[list[str], list[str]]:
    """(problems, undocumented) for the draft's file set before any write.

    ``problems`` refuse the sync: a file the README documents that would
    still be missing afterwards, or a deep-dive tarball for another version.
    ``undocumented`` are other files that would remain on the draft without a
    README section (inherited from an earlier version); they are reported so
    they can be removed in the Zenodo UI before publishing.
    """
    expected = set(release_filenames(version))
    after = (existing - set(RETIRED_FILENAMES)) | uploading
    problems = []
    for name in sorted(expected - after):
        hint = (" — cut_data_release.py uploads it; re-run it with --resume"
                if name == deep_dive_tarball_name(version) else "")
        problems.append(f"{name} is documented in the README but would not be on the draft{hint}")
    for name in sorted(after - expected):
        if name.startswith("deep_dives"):
            problems.append(
                f"{name} is on the draft next to {deep_dive_tarball_name(version)} — a release "
                "draft holds only its own version's deep-dive tarball; delete it in the Zenodo UI"
            )
    undocumented = sorted(n for n in after - expected if not n.startswith("deep_dives"))
    return problems, undocumented


def _pyproject_version() -> str:
    return tomllib.loads(PYPROJECT.read_text())["project"]["version"]


def _build_replicates_tarball(work_dir: Path) -> Path:
    """Shared deterministic builder (record_history.zenodo) — one implementation."""
    from accessible_surfaceome.cloud.record_history.zenodo import build_replicates_tarball

    return build_replicates_tarball(REPLICATES_BUNDLE, work_dir)


def _render_docs(work_dir: Path, version: str) -> tuple[Path, str]:
    """Write README.md + description.html into ``work_dir``; return (readme path, description)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    readme_path = work_dir / README_NAME
    readme_path.write_text(_build_readme(version))
    description = _description_html(version)
    (work_dir / DESCRIPTION_NAME).write_text(description + "\n")
    print(f"→ wrote {readme_path} and {work_dir / DESCRIPTION_NAME}")
    return readme_path, description


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description=(
            "Non-destructively sync the consolidated TSVs, the replicate tarball, "
            "README and description onto a release draft opened by "
            "cut_data_release.py. Only the files it manages are touched; "
            "deep_dives_X.Y.Z.tar.gz (uploaded by cut_data_release.py) is preserved."
        )
    )
    ap.add_argument("--replicates-only", action="store_true",
                    help="sync ONLY the reproducibility-replicate tarball + the "
                         "README / description that document it; leave the TSVs "
                         "untouched")
    ap.add_argument("--deposit-id",
                    help="Zenodo deposition to sync: the draft id cut_data_release.py "
                         "prints when it opens a new version. Required except with "
                         "--dry-run, where omitting it renders the README + "
                         "description and runs the document checks offline.")
    ap.add_argument("--version", dest="release_version", default=None,
                    help="release version the README describes and the draft must "
                         "carry (default: pyproject.toml's version)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR,
                    help="where the built TSVs + deposit_manifest.json are read from and "
                         "README.md / description.html / the replicate tarball are "
                         "written (default: %(default)s, build_consolidated_deposit_tsvs.py's "
                         "default --out-dir)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the sync plan; issue no PUT / DELETE / metadata write")
    args = ap.parse_args(argv)
    deposit_id = args.deposit_id
    version = args.release_version or _pyproject_version()
    work_dir: Path = args.work_dir

    if not deposit_id and not args.dry_run:
        print("--deposit-id is required (the draft id cut_data_release.py printed); "
              "there is deliberately no default deposit", file=sys.stderr)
        return 1

    include_tsvs = not args.replicates_only

    readme_path, description = _render_docs(work_dir, version)
    readme = readme_path.read_text()
    problems = check_docs_file_list(readme, description, version)

    tsv_paths = [work_dir / n for n in TSV_FILENAMES]
    manifest_path = work_dir / MANIFEST_NAME
    if include_tsvs:
        missing = [p for p in tsv_paths if not p.exists()]
        if not manifest_path.exists():
            missing.append(manifest_path)
        if missing:
            msg = ("missing: " + ", ".join(str(p) for p in missing)
                   + " — run scripts/release/build_consolidated_deposit_tsvs.py "
                   f"--out-dir {work_dir} first")
            if deposit_id:
                print(msg, file=sys.stderr)
                return 1
            print(f"→ [dry-run] {msg}; skipped the row-count check")
        else:
            problems = check_docs_against_manifest(
                readme, description, json.loads(manifest_path.read_text()), version,
            )
    if problems:
        print("README / description disagree with the release — fix the text before "
              "syncing:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1
    print(f"→ README / description checks passed for release {version}")

    if not deposit_id:
        print("→ [dry-run] no --deposit-id: rendered + checked the docs only; "
              "no Zenodo calls made")
        return 0

    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        print("ZENODO_TOKEN env var required", file=sys.stderr)
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    managed: list[Path] = [_build_replicates_tarball(work_dir)]
    print(f"→ built {managed[0]} ({managed[0].stat().st_size / 1024**2:.1f} MB)")
    if include_tsvs:
        managed.extend(tsv_paths)
    managed.append(readme_path)

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
        if draft_version != version:
            print(f"⚠ draft version is {draft_version!r} but this sync is for "
                  f"{version!r} — refusing; cut the release with "
                  "cut_data_release.py first", file=sys.stderr)
            return 1
        bucket = dep["links"].get("bucket")
        if not bucket:
            print("⚠ no bucket URL on deposit — older deposit API form?",
                  file=sys.stderr)
            return 1
        print(f"→ deposit {deposit_id} state=draft version={version} bucket={bucket}"
              + ("  [DRY RUN]" if args.dry_run else ""))

        r = client.get(f"{ZENODO_BASE}/deposit/depositions/{deposit_id}/files")
        r.raise_for_status()
        existing = {f["filename"]: f for f in r.json()}
        managed_names = {p.name for p in managed}

        # 2. The draft must end up holding exactly what the README documents.
        if include_tsvs:
            file_problems, undocumented = check_draft_files(set(existing), managed_names, version)
            if file_problems:
                print("draft files disagree with the README — refusing:\n  - "
                      + "\n  - ".join(file_problems), file=sys.stderr)
                return 1
            if undocumented:
                print(f"⚠ {len(undocumented)} file(s) on the draft have no README section "
                      f"(inherited from an earlier version?): {', '.join(undocumented)} — "
                      "delete them in the Zenodo UI before publishing, or add them to "
                      "release_filenames + the README")

        # 3a. Retire only this script's own obsolete outputs (name-scoped),
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

        # 3b. Overwrite changed / new managed files; skip unchanged by MD5.
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

        # 3c. Everything else on the deposit is preserved untouched.
        preserved = sorted(set(existing) - managed_names - set(RETIRED_FILENAMES))
        if preserved:
            print(f"→ preserved {len(preserved)} unmanaged file(s): "
                  f"{', '.join(preserved)}")
        print(f"→ file sync: {uploaded} uploaded, {skipped} unchanged, "
              f"{len(preserved)} preserved")

        # 4. Update description + title, only if they actually differ.
        metadata = dep["metadata"]
        if (metadata.get("title") == RECORD_TITLE
                and metadata.get("description") == description):
            print("→ metadata already current — skipped")
        elif args.dry_run:
            print("  [dry-run] would update description + title")
        else:
            metadata["title"] = RECORD_TITLE
            metadata["description"] = description
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
    if not args.dry_run:
        print("  Next: review the draft and click Publish, then\n"
              f"    uv run python scripts/release/cut_data_release.py --set-doi {version} "
              "10.5281/zenodo.<version-record-id>\n"
              f"    gh release create v{version} --generate-notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
