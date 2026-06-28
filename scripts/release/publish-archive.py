#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Publish accessible-surfaceome to Software Heritage + Zenodo.

A manual, run-when-ready release ritual. Each invocation:

  1. Submits this repo to Software Heritage Save Code Now (free,
     durable, content-addressed; gives you a snapshot SWHID).
  2. Submits each per-figure gist to Software Heritage (one SWHID per
     figure, all populated from FIGURE_PROVENANCE in
     scripts/figures/embed_figure_gist_metadata.py).
  3. Polls SWH until each archive succeeds, prints the resulting SWHIDs.
  4. Audits every managed figure's embedded provenance (defers to
     tests/test_figure_provenance.py).
  5. Snapshots the repo as a tar.gz at HEAD.
  6. Creates a DRAFT Zenodo deposit (nothing is published) containing:
        - the repo tarball
        - extra heavy data files listed in EXTRA_FILES below
     The deposit is private until you click "Publish" in the Zenodo UI.

After publication in the Zenodo UI, you populate `doi` in
scripts/figures/embed_figure_gist_metadata.py's FIGURE_PROVENANCE, re-run that
script to refresh embedded metadata, and commit. The figures then claim
durability via BOTH SWHID (per-figure) and Zenodo DOI (per-bundle).

Usage:
    # Dry run — describe what would happen, no API calls:
    ./scripts/release/publish-archive.py --dry-run

    # SWH only — submit + poll, no Zenodo activity:
    ./scripts/release/publish-archive.py --skip-zenodo

    # Full run (requires ZENODO_TOKEN):
    ZENODO_TOKEN='...' ./scripts/release/publish-archive.py

Environment:
    ZENODO_TOKEN     Required for the Zenodo phase. Generate at
                     https://zenodo.org/account/settings/applications/tokens/new/
                     with scope `deposit:write` (and `deposit:actions`
                     if you ever want to publish via API).

    ZENODO_SANDBOX   Set to "true" to use sandbox.zenodo.org instead of
                     zenodo.org. Fake DOIs (10.5072/zenodo.X), no
                     DataCite registration — safe for testing the
                     script end-to-end before doing it for real.

Safety:
    - SWH submissions are append-only — irreversible but never lossy.
      Software Heritage's mission is permanent archival; once your
      content is in, you can't take it out.
    - Zenodo deposits start as drafts. Drafts can be deleted from the
      UI before publishing. After publishing, the bytes are immutable
      (you can edit metadata, but not files).
    - --dry-run prints the planned actions and makes no API calls.

Single-record-with-everything model:
    This script bundles the repo tarball + extra heavy data files
    (triage runs with reasoning, benchmark runs with reasoning, deep
    dives) into ONE Zenodo record. One DOI covers everything.

    Alternative: enable the GitHub-release auto-archive feature on
    accessible-surfaceome and you get a SEPARATE record series for
    routine releases of just the repo (no heavy data). Then this
    script becomes "the heavy-data bundle" deposit, a second record
    series. Two DOIs.

    Pick one or the other. The single-record model (this script's
    default) is simpler.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

# ── Configuration ──────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]

# Repo origin to archive on Software Heritage.
REPO_ORIGIN = "https://github.com/Deliverome-Project/accessible-surfaceome"

# Per-figure gists to archive on Software Heritage. Mirrors
# FIGURE_PROVENANCE in scripts/figures/embed_figure_gist_metadata.py — keep in
# sync as new figure gists are minted.
GIST_ORIGINS = [
    "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa",  # db_overlap_venn
    # add more figure gists here as they're built and gain a slot in
    # FIGURE_PROVENANCE
]

# Heavy data outputs to include in the Zenodo deposit alongside the
# repo tarball. Each entry is either:
#
#   - a string starting with "https://" or "http://" — fetched from
#     the URL at upload time; saved into the Zenodo deposit as the
#     URL's basename (the last path segment)
#
#   - a dict {"url": "https://...", "filename": "name.ext"} — fetched
#     from the URL, saved into the Zenodo deposit under the explicit
#     filename. Use this when the URL doesn't end with a meaningful
#     filename (e.g., an API path) or when you want a different
#     destination name.
#
#   - any other string — treated as a path relative to REPO_ROOT;
#     read from the local filesystem
#
# The defaults below are the served-from-D1 endpoints of the surfaceome
# public API (cloudflare/workers/surfaceome_api/src/index.js), routed
# under `api.deliverome.org/surfaceome/v1/*`. Each entry below is a
# dict with an explicit destination filename so the resulting Zenodo
# record has readable file names instead of API path basenames.
#
# Comment out entries you don't want in a given deposit, or add local
# paths (relative to REPO_ROOT) for files that don't live behind the API.
# Three files, each answering a distinct reader question. All TSV or
# tar.gz; no nested JSON for analytics. Every join happens server-
# side in the Cloudflare Worker — the publish script just fetches
# pre-joined endpoints, so the deposit bytes are atomic snapshots
# rather than client-side stitched approximations.
#
#   1. triage-runs-with-reasoning.tsv  →  "what did Sonnet say about
#      every gene in the candidate universe, with reasoning + cost?"
#      Long format, one row per (gene × variant × replicate). Pinned
#      to run_id=genome_full_sonnet_ncbi_v1 (Sonnet on ~19k genes).
#      Server endpoint: /v1/triage/export.tsv — LEFT JOIN against
#      the latest candidate_universe_public for uniprot_acc + 5 DB
#      votes + n_db_surface, one SQL round-trip. The headline figures
#      pull from here.
#
#   2. triage-benchmark-with-reasoning.tsv  →  "for each of the 147
#      bench genes, what does every model variant say (Haiku / Sonnet /
#      Opus × naive / ncbi / web_ncbi / pubmed_ncbi), with reasoning?
#      And what does the curated truth say?"  Long format, one row per
#      (bench gene × model × variant). Server endpoint:
#      /v1/benchmark/export.tsv — bench-scoped, JOINs truth labels
#      from benchmark_version + DB votes from candidate_universe_public
#      + latest replicate per cell from triage_run_public. Haiku and
#      Opus only appear here — the broad triage in #1 is Sonnet-only.
#
#   3. deep_dives_all.tar.gz  →  "every published SurfaceomeRecord
#      with full evidence + reasoning."  Built at deposit time by
#      fetching the gene index + every per-gene endpoint and tarring
#      them. ~24 MB projected at 6k-gene full scale (GPR75 ~16 KB ×
#      ~6k, gzipped); ~120 MB even at 5× per-record growth. Tarball
#      members are <SYMBOL>.json so `tar -tf` doubles as the index.
#
# What's deliberately NOT here:
#   - the catalog (/v1/catalog): fully derivable from candidate_universe.tsv
#     (in-repo, augmented with sonnet_verdict + deep-dive flag + stable
#     IDs in PR #29) ∪ #1 above ∪ #3 above. Live API serves it for the
#     viewer.
#   - the matrix JSON: dropped in favour of #2's long TSV (same data,
#     consistent format with #1, no nested objects).
#   - the truth-labels-only TSV: every truth column is in #2 above
#     denormalized into each row.
#
# IMPORTANT: the enriched endpoints used by #1 and #2 must be deployed
# to the Worker BEFORE running this script. See scripts/release/README.md
# for the deploy step.
# Reserved DOI for the current data record on Zenodo. This is the
# RESERVED DOI — preserved across draft updates, activated on publish.
# Used to pre-populate FIGURE_PROVENANCE entries + cross-link
# downstream artifacts (gist READMEs, embedded figure metadata) BEFORE
# the record goes live. Update only on a fresh draft, not on edit.
ZENODO_DATA_DOI = "10.5281/zenodo.20805384"

# The CODE record DOI is minted by GitHub-Zenodo auto-archive on the
# next tagged release; until that happens, the related-identifiers
# link is a placeholder.
ZENODO_CODE_CONCEPT_DOI: str | None = None  # TODO populate after first release

EXTRA_FILES: list[str | dict[str, Any]] = [
    # The active path today uses build_consolidated_deposit_tsvs.py +
    # update_zenodo_draft.py to produce a single consolidated genome-wide
    # TSV (ncbi + pubmed merged with a run_id column) and a multi-rep
    # benchmark TSV with truth labels joined. The entries below describe
    # the SAME files at the URL-per-file granularity for fresh-draft
    # creation; the consolidator builds the consolidated shape from
    # these two URLs + the benchmark endpoint. Keep both paths in sync.
    {
        # Canonical genome-wide Sonnet+ncbi sweep (~19k cells).
        "url": "https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v2",
        "filename": "triage-runs-genome-ncbi-with-reasoning.tsv",
    },
    {
        # Sonnet+pubmed_ncbi rescue sweep on the ambiguous-reason
        # zero-DB Sonnet-no slice (~2,626 cells). Flips 177 ncbi-no
        # to yes/contextual (KLK2 et al). Read-side reconciliation
        # rule: prefer pubmed when verdict is more inclusive.
        "url": "https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_pubmed_ncbi_v1",
        "filename": "triage-runs-genome-pubmed-rescue-with-reasoning.tsv",
    },
    {
        # 147-gene mainbench: Haiku/Sonnet/Opus × 4 prompt variants,
        # joined with curated truth labels + 5-DB votes.
        "url": "https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv",
        "filename": "triage-benchmark-with-reasoning.tsv",
    },
    # ── PUBLICATION-WORKFLOW PLACEHOLDERS (per scripts/release/README.md) ──
    # Each is a known artifact that the publication ritual expects in
    # this Zenodo data record but isn't ready yet. Uncomment the
    # corresponding entry when its source is ready and re-run
    # update_zenodo_draft.py to push to the existing reserved DOI.
    #
    # 1. Deep dives bundle — every published SurfaceomeRecord, gzipped.
    #    Held back until deep-dive prompt + schema iteration converges.
    # {
    #     "deep_dives_bundle": True,
    #     "filename": "deep_dives_all.tar.gz",
    #     "index_url": "https://api.deliverome.org/surfaceome/v1/genes",
    #     "gene_url_template": "https://api.deliverome.org/surfaceome/v1/genes/{symbol}",
    # },
    #
    # 2. Manuscript bundle — pre-built PDF + pandoc-generated JATS XML.
    #    Held back until manuscript is ready; see publish-archive.py's
    #    inline docs above EXTRA_FILES for the full pandoc recipe.
    # {
    #     "manuscript": True,
    #     "source": "paper/manuscript.docx",  # or .tex / .md
    #     "pdf_path": "paper/build/manuscript.pdf",
    #     "jats_filename": "manuscript.xml",
    #     "extra_pandoc_args": [],
    # },
    {
        # In-deposit README — documents every column of every file
        # above and the live-API endpoint that produces them.
        # Travels WITH the data on Zenodo so the bytes are self-
        # explanatory.
        "deposit_readme": True,
        "filename": "README.md",
    },
    # ── Manuscript bundle ─────────────────────────────────────────────
    # OFF BY DEFAULT. Uncomment + edit when you're ready to deposit the
    # paper alongside the data. Produces TWO files in the deposit:
    #   (a) the pre-built PDF you point at via `pdf_path` (verbatim copy)
    #   (b) JATS XML derived from `source` via pandoc — for PMC indexing,
    #       reference managers, and downstream text-mining
    #
    # `source` must be a pandoc-readable manuscript — markdown (`.md`),
    # LaTeX (`.tex`), or Word (`.docx`). Pandoc detects format by
    # extension. JATS conversion needs nothing beyond `pandoc` on PATH;
    # PDF rendering would need a LaTeX engine and gets skipped — the
    # PDF in the deposit is whatever you've already built (`pdf_path`),
    # so the deposit matches what readers actually citation-link.
    #
    # **Word (.docx) manuscripts** are well-supported by pandoc's JATS
    # writer — heading levels, lists, tables, and inline italic/bold
    # come through cleanly, and pandoc's `--citeproc` honors a
    # standalone `.bib` file even when the .docx uses Word's own
    # bibliography manager. Common pre-flight checklist for a .docx
    # → JATS run:
    #   - structure headings with Word's heading styles (H1/H2/H3),
    #     not bold-italic body text — pandoc maps styles to <sec>
    #     nesting
    #   - figure captions written as Word-style "Figure 1. <caption>"
    #     paragraphs render to <fig>/<caption>
    #   - tables can stay as native Word tables; pandoc emits
    #     <table-wrap>
    #   - inline gene-name italics from the .docx survive as <italic>
    #     in JATS — exactly the JATS convention
    #
    # `extra_pandoc_args` is empty in the default below. The script
    # always passes `--standalone --to jats`; you only need extras for
    # specific transformations (e.g. `--metadata title="…"` override).
    #
    # **Citations note** — if you're using Zotero in Word, leave
    # `extra_pandoc_args` empty. Zotero already bakes the formatted
    # citations + bibliography into the `.docx` as text, and pandoc
    # carries that through into the JATS XML verbatim. References
    # land as plain text (not structured `<ref>` elements), which is
    # plenty for a Zenodo deposit. Switching to pandoc-managed
    # citations would require exporting a `.bib` from Zotero AND
    # toggling the Zotero Word plugin from "Word fields" mode to
    # "BibTeX cite keys" mode in Document Preferences — only worth
    # doing if you specifically need structured-reference JATS.
    #
    # Tooling install:
    #   macOS:   brew install pandoc
    #   Linux:   apt install pandoc   (or download from pandoc.org)
    # {
    #     "manuscript": True,
    #     "source": "paper/manuscript.docx",
    #     "pdf_path": "paper/build/manuscript.pdf",
    #     "jats_filename": "manuscript.xml",
    #     "extra_pandoc_args": [],
    # },
]

# Seed metadata for the Zenodo deposit. The Zenodo UI lets you edit
# every field before publishing — these are sensible defaults.
SEED_METADATA = {
    "metadata": {
        "upload_type": "dataset",
        "title": "accessible-surfaceome — benchmark + triage data outputs",
        "description": (
            "Triage + benchmark data outputs for the accessible-surfaceome "
            "project. Three data files plus an in-deposit README that "
            "documents every column and the source-join recipe used to "
            "construct each file. Deep-dive SurfaceomeRecords are NOT "
            "included in this deposit — they remain in active iteration "
            "and will be added in a subsequent record.<br><br>"
            "<b>triage-runs-genome-ncbi-with-reasoning.tsv</b> — Sonnet "
            "4.6 verdicts with full reasoning across the ~19k-gene M1 "
            "candidate universe under the canonical NCBI-context prompt, "
            "joined with per-source DB votes (UniProt / GO / SURFY / "
            "CSPA / HPA) from the catalog.<br><br>"
            "<b>triage-runs-genome-pubmed-rescue-with-reasoning.tsv</b> — "
            "Sonnet 4.6 verdicts under the PubMed-augmented prompt for "
            "the 2,626-gene ambiguous-reason zero-DB Sonnet-no slice (the "
            "rescue lane). Flips 177 ncbi-no calls to yes/contextual; the "
            "read-side reconciliation rule prefers the PubMed verdict when "
            "it is more inclusive than the NCBI verdict.<br><br>"
            "<b>triage-benchmark-with-reasoning.tsv</b> — Haiku 4.5 / "
            "Sonnet 4.6 / Opus 4.7 verdicts (4 prompt variants each) on "
            "the 147-gene curated benchmark, joined with the same DB "
            "votes plus curated truth labels.<br><br>"
            "All files are reproducible end-to-end from the public read-"
            "only API at https://api.deliverome.org/surfaceome/v1/ ; "
            "the included README.md documents the exact endpoint joins. "
            "The repository code itself is archived separately via the "
            "GitHub-Zenodo auto-archive (one DOI per tagged release) "
            "and via Software Heritage (continuous crawl, content-"
            "addressed SWHIDs). This record is the supplementary data "
            "layer; the related-identifiers field links the two."
        ),
        "creators": [
            {"name": "Carlson, Rebecca"},
            {"name": "Smallegan, Michael"},
        ],
        "access_right": "open",
        "license": "cc-by-4.0",
        "keywords": [
            "surface proteome",
            "drug delivery",
            "reproducible figures",
            "open data",
        ],
        # Link this data record to the auto-archived code record(s).
        # The code-record concept DOI is minted by the GitHub-Zenodo
        # auto-archive on the FIRST tagged release (none exists yet —
        # see ZENODO_CODE_CONCEPT_DOI at the top of this file). When
        # that DOI is known, set ZENODO_CODE_CONCEPT_DOI and uncomment
        # the placeholder below; the link makes the relationship
        # explicit in CrossRef/DataCite and Zenodo's UI.
        "related_identifiers": [
            # PUBLICATION-WORKFLOW PLACEHOLDER — populate after the
            # first code-record release. See ZENODO_CODE_CONCEPT_DOI.
            # {
            #     "identifier": f"10.5281/zenodo.{ZENODO_CODE_CONCEPT_DOI}",
            #     "relation": "isSupplementTo",
            #     "scheme": "doi",
            # },
        ],
    },
}

SWH_BASE = "https://archive.softwareheritage.org/api/1"


# ── Output helpers ─────────────────────────────────────────────────────

def announce(msg: str) -> None:
    print(f"\n→ {msg}")


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠ {msg}")


def bail(msg: str) -> None:
    print(f"\nerror: {msg}", file=sys.stderr)
    sys.exit(1)


# ── Software Heritage ──────────────────────────────────────────────────

def _swh_url_encoded(origin: str) -> str:
    return urllib.parse.quote(origin, safe="")


def submit_save_code_now(origin: str, *, dry_run: bool) -> dict[str, Any] | None:
    if dry_run:
        ok(f"[dry-run] would POST Save Code Now for {origin}")
        return None
    url = f"{SWH_BASE}/origin/save/git/url/{_swh_url_encoded(origin)}/"
    r = httpx.post(url, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def poll_swh_until_done(origin: str, *, max_wait_s: int = 1200) -> str | None:
    """Poll SWH until the most recent save_request for `origin` finishes.

    Returns the snapshot SWHID on success, or None on timeout/failure.
    """
    encoded = _swh_url_encoded(origin)
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        r = httpx.get(
            f"{SWH_BASE}/origin/save/git/url/{encoded}/",
            timeout=30,
        )
        if r.status_code != 200:
            time.sleep(30)
            continue
        data = r.json()
        entries = data if isinstance(data, list) else [data]
        latest = entries[-1]
        status = latest.get("save_task_status")
        if status == "succeeded":
            snp = latest.get("snapshot_swhid")
            if snp:
                return snp
            # Fall back: query the latest visit for this origin
            visits = httpx.get(
                f"{SWH_BASE}/origin/{encoded}/visits/latest/", timeout=30,
            ).json()
            if visits.get("snapshot"):
                return f"swh:1:snp:{visits['snapshot']}"
            return None
        if status == "failed":
            return None
        print(f"    {origin}: status={status}, waiting 30s …")
        time.sleep(30)
    return None


# ── Repo snapshot ──────────────────────────────────────────────────────

def _resolve_extra_file(
    entry: str | dict[str, Any], *, dry_run: bool,
) -> list[tuple[Path, bool]] | None:
    """Resolve one EXTRA_FILES entry to a list of (local_path, cleanup) pairs.

    Most entry shapes resolve to exactly one file; the list-returning
    contract is so the manuscript bundle can yield BOTH a PDF and a
    JATS XML from a single config entry without callers needing to
    know that. ``cleanup=True`` tells the upload loop to delete the
    local file after the upload succeeds (used for tempfiles + scratch
    builds); ``False`` is for in-repo files we mustn't touch.

    Five input shapes:

      - bare HTTP(S) URL: fetched to a tempfile, returned with
        cleanup=True so the caller deletes it after upload. Destination
        name is the URL's last path segment.

      - {"url": "...", "filename": "..."} dict: same fetch behaviour
        but destination name is the explicit filename. The triage
        TSVs use this form pointing at the Worker's
        `/v1/triage/export.tsv` and `/v1/benchmark/export.tsv`
        endpoints — all joins happen server-side, atomic snapshot
        per round-trip.

      - {"deep_dives_bundle": True, "filename": "...", "index_url":
        "...", "gene_url_template": "..."}: special-case resolver that
        fetches the gene index from `index_url`, then for each entry
        fetches `gene_url_template.format(symbol=...)`, then tars all
        per-gene JSONs into a single gzipped archive.

      - {"deposit_readme": True, "filename": "..."}: special-case
        resolver that generates an in-deposit README at deposit time
        documenting every file's columns + reproduction recipe.

      - {"manuscript": True, "source": "paper/manuscript.md",
        "pdf_path": "paper/build/manuscript.pdf",
        "jats_filename": "manuscript.xml", ...}: pandoc-converts
        ``source`` (a markdown / latex / docx manuscript) to JATS
        XML and yields it alongside a verbatim copy of the pre-built
        PDF at ``pdf_path``. See ``_build_manuscript_bundle`` for the
        full contract.

      - other string: treated as a path relative to REPO_ROOT. If the
        local file doesn't exist, warns and returns None.

    Raises on fetch errors so the caller can decide whether to skip.
    """
    # Bare URL
    if isinstance(entry, str) and entry.startswith(("http://", "https://")):
        return [(_download_to_tempfile(entry, filename=None, dry_run=dry_run), True)]

    # Dict forms
    if isinstance(entry, dict):
        if entry.get("deep_dives_bundle"):
            return [(_build_deep_dives_bundle(entry, dry_run=dry_run), True)]
        if entry.get("deposit_readme"):
            return [(_build_deposit_readme(entry, dry_run=dry_run), True)]
        if entry.get("manuscript"):
            return _build_manuscript_bundle(entry, dry_run=dry_run)
        url = entry.get("url")
        filename = entry.get("filename")
        if not url:
            raise ValueError("dict entry missing 'url'")
        return [(_download_to_tempfile(url, filename=filename, dry_run=dry_run), True)]

    # Local path
    if isinstance(entry, str):
        path = REPO_ROOT / entry
        if not path.exists():
            warn(f"  - missing local file (will skip): {entry}")
            return None
        return [(path, False)]

    raise ValueError(f"unsupported entry type: {type(entry).__name__}")


def _http_get_with_retry(
    url: str, *, timeout: float = 120, attempts: int = 4,
) -> httpx.Response:
    """GET with exponential backoff on 5xx. The Worker can return
    transient 503s when a query warms a cold cache (especially the
    ~19k-row genome_full triage export); retrying after a short pause
    almost always succeeds.
    """
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=True)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500 or i == attempts - 1:
                raise
            last_err = e
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            if i == attempts - 1:
                raise
            last_err = e
        wait = 2 ** i  # 1s, 2s, 4s, 8s
        warn(f"  retrying {url} after {wait}s ({last_err})")
        time.sleep(wait)
    raise RuntimeError(f"unreachable: exhausted retries for {url}")



def _build_deposit_readme(
    entry: dict[str, Any], *, dry_run: bool,
) -> Path:
    """Generate the in-deposit README.md that documents every file's
    columns and the live-API endpoint that reproduces it.

    This is what a Zenodo downloader sees alongside the data. It's
    the canonical user-facing description of what the bytes are —
    the inline docstrings in this script are for maintainers; this
    README is for readers.
    """
    filename = entry["filename"]
    tmp_root = REPO_ROOT / "_extra-download"

    if dry_run:
        ok(f"[dry-run] would generate in-deposit {filename}")
        return tmp_root / filename

    tmp_root.mkdir(exist_ok=True)
    out_path = tmp_root / filename

    # Capture the repo commit so this README pins itself to a specific
    # version of publish-archive.py + the EXTRA_FILES list.
    try:
        head_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        ).decode().strip()
    except subprocess.CalledProcessError:
        head_sha = "(unknown)"

    body = f"""# accessible-surfaceome — Zenodo deposit

This deposit contains the benchmark + triage data outputs for the
[accessible-surfaceome](https://github.com/Deliverome-Project/accessible-surfaceome)
project. The repository code itself is archived separately (GitHub-
Zenodo auto-archive + Software Heritage continuous crawl). Per-gene
deep-dive `SurfaceomeRecord` JSONs are NOT in this deposit — they
remain in active iteration and will appear in a subsequent record.

All data files were assembled at deposit time by the
[`scripts/release/publish-archive.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{head_sha}/scripts/release/publish-archive.py)
script in the repo at commit `{head_sha[:12]}`. Anyone can regenerate
them from the public read-only API documented below.

## Files

### 1. `triage-runs-genome-ncbi-with-reasoning.tsv`

Long-format TSV, one row per (gene × prompt variant × replicate),
covering Sonnet 4.6 inference under the canonical NCBI-context prompt
across the **~19k-gene M1 candidate universe**. The single source of
truth for the cost-vs-accuracy and db-correctness figures in the project.

| Column | Meaning |
|---|---|
| `gene_symbol` | HGNC gene symbol |
| `uniprot_acc` | UniProt accession (canonical isoform) |
| `db_uniprot`, `db_go`, `db_surfy`, `db_cspa`, `db_hpa` | 0/1 — does each surface-DB source vote "surface" for this gene? |
| `n_db_surface` | sum of the 5 DB votes (0–5) |
| `model` | Anthropic model identifier (Sonnet only in this file) |
| `prompt_variant` | which prompt variant was used (`ncbi` only in this file) |
| `replicate` | replicate index within the sweep |
| `predicted_verdict` | model verdict: `yes` / `contextual` / `no` |
| `predicted_reason` | short controlled-vocab reason tag |
| `predicted_confidence` | `low` / `medium` / `high` |
| `prompt_tokens`, `completion_tokens`, `cache_creation_tokens`, `cache_read_tokens` | per-call token counts |
| `n_web_searches` | number of web tool calls in this run |
| `cost_usd` | computed dollar cost of this call |
| `latency_s` | wall-clock seconds for this call |

**Reproducible from one endpoint** — the JOIN happens server-side in a
single SQL round-trip, so the bytes are an atomic snapshot:

```bash
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v2' \\
    > triage-runs-genome-ncbi-with-reasoning.tsv
```

Source tables behind that endpoint: `triage_run_public` (the model
output) `LEFT JOIN candidate_universe_public` (DB votes +
`uniprot_acc`) on `gene_symbol`, filtered to the latest
`universe_version`.

### 2. `triage-runs-genome-pubmed-rescue-with-reasoning.tsv`

Long-format TSV, same column layout as file 1, covering the **2,626-
gene pubmed-augmented rescue lane**: every gene where file 1's
Sonnet+NCBI verdict was `no` AND no surface DB flagged the gene AND
the `no`-reason fell into an ambiguous bucket (`secreted_only`,
`endomembrane_resident`, `inner_leaflet_anchored`,
`pmhc_only_intracellular`, `nuclear_envelope`, `other`). PubMed
evidence rescued 177 of these calls (158 → contextual, 19 → yes),
including KLK2 (prostate kallikrein with documented tumor-cell
surface display).

The **read-side reconciliation rule** used in downstream analyses:
when this file's verdict is yes/contextual and file 1's is no,
prefer this file's verdict. PubMed never overrides a `yes`/
`contextual` from file 1 — `no` from this file doesn't constitute
evidence of absence.

```bash
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_pubmed_ncbi_v1' \\
    > triage-runs-genome-pubmed-rescue-with-reasoning.tsv
```

### 3. `triage-benchmark-with-reasoning.tsv`

Long-format TSV, one row per (bench gene × model × prompt variant ×
replicate), covering the **147-gene curated benchmark** across all 3
production models (Haiku 4.5, Sonnet 4.6, Opus 4.7) and all 4 prompt
variants (`naive`, `ncbi`, `web_ncbi`, `pubmed_ncbi`). Haiku and Opus
only appear in this file — the broad triage in #1 is Sonnet-only.

Same columns as #1, **plus** three curated truth-label columns:

| Column | Meaning |
|---|---|
| `truth_verdict` | curated truth: `yes` / `contextual` / `no` |
| `truth_signal` | curated signal: `likely_accessible` / `unlikely` / etc. |
| `truth_reason` | curated reason tag (controlled vocab) |

**Reproducible from one endpoint** — same atomic-snapshot guarantee
as #1:

```bash
curl 'https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv' \\
    > triage-benchmark-with-reasoning.tsv
```

Source tables behind that endpoint: `triage_run_public` (latest
replicate per `gene × model × variant` cell via SQL window function)
`INNER JOIN benchmark_version` (truth labels + `uniprot_acc`, scoped
to the canonical curated `bench_version`) `LEFT JOIN
candidate_universe_public` (DB votes), with the bench restriction
filtering to ~1.7k rows before the join — well inside the Worker's
CPU budget.

## Repository, code archive, related identifiers

- **Source code:** <https://github.com/Deliverome-Project/accessible-surfaceome>
- **Pinned to commit:** `{head_sha}`
- **Code release archive:** the GitHub-Zenodo auto-archive mints one
  DOI per tagged release; the latest is linked from this record's
  *Related identifiers*.
- **Continuous source archive:** Software Heritage. The repo's SWHID
  is in this record's *Related identifiers* (relation `isSupplementTo`).

## License

CC-BY-4.0 for the data in this deposit. Same as the upstream
constituent sources (UniProt, GO, HPA — all CC-BY; HPA is CC-BY-SA).
SURFY and CSPA are published academic resources used under their
respective terms; see the upstream papers.
"""

    out_path.write_text(body)
    size_kb = out_path.stat().st_size / 1024
    ok(f"generated {out_path.name} ({size_kb:.1f} KB, pinned to {head_sha[:12]})")
    return out_path


def _build_deep_dives_bundle(
    entry: dict[str, Any], *, dry_run: bool,
) -> Path:
    """Fetch the gene index, fetch each per-gene record, tar.gz them all.

    Each tar member is named ``<SYMBOL>.json`` so ``tar -tf`` doubles as
    the index. The gzipped tarball is written under the same temp dir
    `_download_to_tempfile` uses so cleanup is symmetric.
    """
    filename = entry["filename"]
    index_url = entry["index_url"]
    gene_url_template = entry["gene_url_template"]

    tmp_root = REPO_ROOT / "_extra-download"

    if dry_run:
        ok(
            f"[dry-run] would fetch {index_url}, then per-gene "
            f"records via {gene_url_template}, then tar.gz → {filename}"
        )
        return tmp_root / filename

    tmp_root.mkdir(exist_ok=True)

    # 1. Fetch the index.
    idx_resp = _http_get_with_retry(index_url, timeout=60)
    idx = idx_resp.json()
    genes = idx.get("genes") if isinstance(idx, dict) else idx
    if not isinstance(genes, list):
        raise ValueError(
            f"deep-dives index at {index_url} did not return a list "
            f"of genes (got {type(genes).__name__})"
        )
    symbols = [g["gene_symbol"] for g in genes if isinstance(g, dict) and g.get("gene_symbol")]
    if not symbols:
        raise ValueError(f"deep-dives index at {index_url} is empty")

    ok(f"deep-dives bundle: index has {len(symbols)} gene(s)")

    # 2. Fetch each per-gene record into a staging dir, then tar it.
    out_path = tmp_root / filename
    with tempfile.TemporaryDirectory(prefix="deep_dives_", dir=tmp_root) as stage_dir:
        stage = Path(stage_dir)
        for i, sym in enumerate(symbols, 1):
            gene_url = gene_url_template.format(symbol=sym)
            r = _http_get_with_retry(gene_url, timeout=120)
            (stage / f"{sym}.json").write_bytes(r.content)
            if i % 100 == 0 or i == len(symbols):
                ok(f"  fetched {i}/{len(symbols)} deep-dive records")

        # 3. tar.gz the staging dir contents (flat layout — no parent dir).
        with tarfile.open(out_path, "w:gz") as tar:
            for json_path in sorted(stage.glob("*.json")):
                tar.add(json_path, arcname=json_path.name)

    size_mb = out_path.stat().st_size / 1024 / 1024
    ok(f"built {out_path.name} ({size_mb:.1f} MB, {len(symbols)} records)")
    return out_path


def _build_manuscript_bundle(
    entry: dict[str, Any], *, dry_run: bool,
) -> list[tuple[Path, bool]]:
    """Produce a (PDF, JATS XML) pair for the deposit from a manuscript
    source.

    Two outputs land in the deposit:

      * **PDF**: verbatim copy of ``entry["pdf_path"]`` (relative to
        ``REPO_ROOT``). The script never re-renders the PDF — whatever
        you've built upstream (LaTeX in Overleaf, Word export, Pandoc
        + a LaTeX engine, Typst, etc.) is what reviewers will cite, so
        the deposit should match it byte-for-byte. Cleanup=False on this
        entry — the file lives in your repo, we don't touch it.

      * **JATS XML**: pandoc-converted from ``entry["source"]`` (any
        pandoc-readable manuscript: ``.md`` / ``.tex`` / ``.docx``).
        Written under ``_extra-download/`` and uploaded with
        cleanup=True so it doesn't litter the working tree.

    Pandoc invocation is:

        pandoc <source> --standalone --to jats -o <jats_filename>
               <...entry["extra_pandoc_args"]>

    ``--standalone`` is required for pandoc's JATS writer (without it
    pandoc emits a fragment, not a full ``<article>``). The caller can
    add ``--citeproc --bibliography=refs.bib --csl=…`` etc. via
    ``extra_pandoc_args`` for citation processing.

    Why we don't auto-render the PDF too: a real paper needs a LaTeX
    engine + class files + bibliography styles + (often) journal-
    specific templates. Pandoc CAN produce PDFs, but the output rarely
    matches what reviewers actually see. We make the JATS conversion
    fully automatic (it's plain XML, no engine needed) and require the
    PDF to be supplied as-is.

    Validation note: the resulting JATS XML is ``--standalone``
    pandoc output, which is well-formed but is NOT guaranteed to pass
    the PMC JATS DTD's tighter constraints (e.g. ``article-meta``
    structural requirements). Run it through JATS4R's validator
    (https://www.jats4r.org/) or ``xmllint --dtdvalid …`` if you need
    PMC-grade validation; for deposit-with-the-data purposes the
    standalone XML is usually sufficient.

    Pre-conditions checked:
      - ``pandoc`` is installed and on ``PATH``. We shell out to it as
        a binary — no Python ``pandoc-python`` dep (that wrapper is
        thinly maintained and not worth the supply-chain).
      - ``source`` exists at the declared path.
      - ``pdf_path`` exists (when set).
    """
    source = REPO_ROOT / entry["source"]
    jats_filename = entry.get("jats_filename") or (source.stem + ".xml")
    pdf_path_str = entry.get("pdf_path")
    extra_args = list(entry.get("extra_pandoc_args") or [])

    outputs: list[tuple[Path, bool]] = []

    # PDF: verbatim copy of the user's pre-built file. Cleanup=False,
    # since the file lives in the repo.
    if pdf_path_str:
        pdf_path = REPO_ROOT / pdf_path_str
        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"manuscript bundle: pdf_path={pdf_path_str} not found "
                f"(resolved to {pdf_path})"
            )
        outputs.append((pdf_path, False))
        ok(f"manuscript PDF: {pdf_path.relative_to(REPO_ROOT)} (verbatim)")

    # JATS XML: pandoc convert. Skipped if the entry opts out by
    # setting jats_filename to None / empty / False explicitly.
    if jats_filename:
        if not source.is_file():
            raise FileNotFoundError(
                f"manuscript bundle: source={entry['source']} not found "
                f"(resolved to {source})"
            )
        tmp_root = REPO_ROOT / "_extra-download"
        out_path = tmp_root / jats_filename

        if dry_run:
            ok(
                f"[dry-run] would pandoc-convert {source.relative_to(REPO_ROOT)} "
                f"→ {jats_filename} (JATS, with args: {extra_args})"
            )
            outputs.append((out_path, True))
        else:
            # Refuse cleanly if pandoc isn't on PATH — better than the
            # bare FileNotFoundError on subprocess invocation, since
            # the failure mode tells the operator exactly what to fix.
            from shutil import which
            if which("pandoc") is None:
                raise RuntimeError(
                    "manuscript bundle needs `pandoc` on PATH but it "
                    "isn't installed. Install with `brew install "
                    "pandoc` (macOS) or `apt install pandoc` (Linux), "
                    "or remove the manuscript entry from EXTRA_FILES."
                )
            tmp_root.mkdir(exist_ok=True)
            cmd = [
                "pandoc",
                str(source),
                "--standalone",
                "--to", "jats",
                "-o", str(out_path),
                *extra_args,
            ]
            try:
                subprocess.run(cmd, check=True, cwd=REPO_ROOT)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"pandoc JATS conversion failed (exit {exc.returncode}). "
                    f"Command: {' '.join(cmd)}"
                ) from exc
            size_kb = out_path.stat().st_size / 1024
            ok(f"built {out_path.name} ({size_kb:.1f} KB) via pandoc")
            outputs.append((out_path, True))

    if not outputs:
        raise ValueError(
            "manuscript bundle entry produced no outputs — set "
            "`pdf_path` and/or `jats_filename`"
        )
    return outputs


def _download_to_tempfile(
    url: str, *, filename: str | None, dry_run: bool,
) -> Path:
    """Fetch `url` to a tempfile and return the local path.

    `filename` overrides the destination name (otherwise derived from
    the URL's last path segment). In dry-run mode, returns a fake Path
    of length 0 without making any HTTP request.
    """
    name = filename or urllib.parse.unquote(
        urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    ) or "download.bin"
    if not name:
        raise ValueError(f"could not derive filename from URL: {url}")

    tmp_root = Path(REPO_ROOT) / "_extra-download"
    if dry_run:
        ok(f"[dry-run] would fetch {url}  → upload as {name}")
        # Return a fake path; the upload step also dry-runs.
        return tmp_root / name
    tmp_root.mkdir(exist_ok=True)
    out = tmp_root / name
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
        r.raise_for_status()
        with out.open("wb") as fh:
            for chunk in r.iter_bytes(chunk_size=1 << 20):  # 1 MiB
                fh.write(chunk)
    size_mb = out.stat().st_size / 1024 / 1024
    ok(f"fetched {url} ({size_mb:.1f} MB) → {out.name}")
    return out


def git_archive_repo(out_path: Path, *, dry_run: bool) -> str:
    """Snapshot the repo at HEAD as a tar.gz. Returns the HEAD commit SHA."""
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
    ).decode().strip()
    if dry_run:
        ok(f"[dry-run] would `git archive` HEAD ({head_sha[:7]}) → {out_path.name}")
        return head_sha
    subprocess.run(
        [
            "git", "archive", "--format=tar.gz",
            f"--prefix=accessible-surfaceome-{head_sha[:7]}/",
            f"--output={out_path}", "HEAD",
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    return head_sha


# ── Zenodo ─────────────────────────────────────────────────────────────

def zenodo_base() -> str:
    if os.environ.get("ZENODO_SANDBOX", "").lower() == "true":
        return "https://sandbox.zenodo.org/api"
    return "https://zenodo.org/api"


def zenodo_create_deposit(token: str, metadata: dict, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        ok("[dry-run] would create Zenodo draft with metadata:")
        for line in json.dumps(metadata["metadata"], indent=2).splitlines():
            print(f"    {line}")
        return {
            "id": "<dry-run>",
            "links": {
                "html": "<dry-run-edit-url>",
                "bucket": "<dry-run-bucket>",
                "self": "<dry-run-self>",
            },
            "metadata": {"prereserve_doi": {"doi": "<dry-run-doi>"}},
        }
    r = httpx.post(
        f"{zenodo_base()}/deposit/depositions",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=metadata,
        timeout=60,
    )
    if not r.is_success:
        bail(f"Zenodo create-deposit failed: HTTP {r.status_code}: {r.text}")
    return r.json()


def zenodo_upload_file(
    bucket_url: str, token: str, local_path: Path, *, dry_run: bool,
    destination_name: str | None = None,
) -> None:
    dest = destination_name or local_path.name
    if dry_run:
        size_str = (
            f"{local_path.stat().st_size / 1024 / 1024:.1f} MB"
            if local_path.exists()
            else "size unknown — file not yet created"
        )
        ok(f"[dry-run] would upload {local_path.name} ({size_str}) → {bucket_url}/{dest}")
        return
    size_mb = local_path.stat().st_size / 1024 / 1024
    ok(f"uploading {local_path.name} ({size_mb:.1f} MB) → {bucket_url}/{dest}")
    with local_path.open("rb") as fh:
        r = httpx.put(
            f"{bucket_url}/{dest}",
            content=fh.read(),
            headers={"Authorization": f"Bearer {token}"},
            timeout=900,  # 15 min for large files
        )
    if not r.is_success:
        bail(f"Zenodo upload of {local_path.name} failed: HTTP {r.status_code}: {r.text}")


# ── Phases ─────────────────────────────────────────────────────────────

def phase_swh(*, dry_run: bool) -> dict[str, str | None]:
    """Submit repo + all figure gists to SWH; poll for SWHIDs."""
    announce("PHASE 1 — Software Heritage: submit repo + figure gists")

    origins = [REPO_ORIGIN, *GIST_ORIGINS]
    for origin in origins:
        resp = submit_save_code_now(origin, dry_run=dry_run)
        if resp is not None:
            ok(
                f"submitted {origin} (request id={resp.get('id')}, "
                f"status={resp.get('save_task_status')})"
            )

    if dry_run:
        return {origin: None for origin in origins}

    announce("Polling SWH for each archive (1–15 min each)…")
    results: dict[str, str | None] = {}
    for origin in origins:
        print(f"  ↻ {origin}")
        swhid = poll_swh_until_done(origin)
        results[origin] = swhid
        if swhid:
            ok(f"SWHID: {swhid}")
        else:
            warn(f"timed out / failed: {origin}")
    return results


def phase_audit_figures(*, dry_run: bool) -> bool:
    """Run the figure-provenance test suite. Returns True if pass."""
    announce("PHASE 2 — Audit every figure's embedded provenance")
    if dry_run:
        ok("[dry-run] would run: uv run pytest tests/test_figure_provenance.py")
        return True
    try:
        subprocess.run(
            ["uv", "run", "pytest", "tests/test_figure_provenance.py", "-q"],
            cwd=REPO_ROOT,
            check=True,
        )
        ok("all figure provenance checks pass")
        return True
    except subprocess.CalledProcessError:
        warn("figure provenance audit failed — see pytest output above")
        warn("consider re-running scripts/figures/embed_figure_gist_metadata.py before Zenodo")
        return False


def phase_audit_data_inputs() -> None:
    """Surface every data input referenced by a managed figure's
    provenance, so the operator can decide which to include in the
    Zenodo deposit.

    Reads ``FIGURE_PROVENANCE`` from ``scripts/figures/embed_figure_gist_metadata.py``
    (the source of truth for which data sources back which figures).
    For each ``data[]`` entry:

    * If the URL is already on a durable archive (Zenodo, Figshare,
      OSF, archive.softwareheritage.org), report it as already-deposited.
    * If the URL is on a mutable host (raw.githubusercontent.com without
      a pinned commit SHA, etc.), flag it as a candidate for deposit.
    * If a ``swhid`` or ``doi`` is already set on the entry, treat it
      as durably referenced and skip.

    This phase doesn't ADD anything to EXTRA_FILES — it just
    surfaces a checklist for the operator. Adding to the deposit is a
    deliberate human step.
    """
    announce("PHASE 2.5 — Audit data inputs referenced by figure gists")

    # Read FIGURE_PROVENANCE from the project venv via subprocess, so this
    # PEP 723 script's isolated venv (which doesn't know about the
    # accessible_surfaceome package) can still see the canonical
    # registry of which data inputs back which figures.
    try:
        out = subprocess.check_output(
            [
                "uv", "run", "--project", str(REPO_ROOT), "python", "-c",
                "import json, sys; "
                "sys.path.insert(0, 'scripts'); "
                "from embed_figure_gist_metadata import FIGURE_PROVENANCE; "
                "print(json.dumps(FIGURE_PROVENANCE))",
            ],
            cwd=REPO_ROOT,
            text=True,
        )
        FIGURE_PROVENANCE: dict[str, dict[str, Any]] = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        warn(f"could not load FIGURE_PROVENANCE for audit: {exc}")
        return

    durable_hosts = {
        "zenodo.org",
        "sandbox.zenodo.org",
        "figshare.com",
        "ndownloader.figshare.com",
        "osf.io",
        "datadryad.org",
        "archive.softwareheritage.org",
    }

    rows: list[tuple[str, str, str, str]] = []  # (slug, url, status, note)
    for slug, prov in FIGURE_PROVENANCE.items():
        for i, entry in enumerate(prov.get("data") or []):
            url = entry.get("url") or ""
            sha = entry.get("sha256") or ""
            swhid = entry.get("swhid") or ""
            doi = entry.get("doi") or ""
            try:
                host = urllib.parse.urlparse(url).hostname or ""
            except Exception:
                host = ""
            if doi:
                rows.append((slug, url, "DOI",
                             f"deposited (doi={doi})"))
            elif swhid:
                rows.append((slug, url, "SWHID",
                             f"archived (swhid={swhid[:24]}…)"))
            elif host in durable_hosts:
                rows.append((slug, url, "durable host", host))
            elif "raw.githubusercontent.com" in host and "/main/" not in url:
                # Pinned to a commit SHA — content-verifiable but storage-fragile.
                rows.append((slug, f"data[{i}]: {url}", "review",
                             f"pinned to commit SHA; sha256={'set' if sha else 'MISSING'}; "
                             "consider Zenodo deposit"))
            else:
                rows.append((slug, f"data[{i}]: {url}", "review",
                             "mutable URL — needs Zenodo deposit"))

    if not rows:
        warn("FIGURE_PROVENANCE has no data[] entries — nothing to audit")
        return

    print()
    print("  Data inputs referenced by figure gists:")
    print()
    for slug, url, status, note in rows:
        flag = "  ✓" if status in {"DOI", "SWHID", "durable host"} else "  ⚠"
        print(f"  {flag} [{slug}] {status}: {note}")
        print(f"      url: {url[:96]}…" if len(url) > 96 else f"      url: {url}")
    print()
    print(
        "  Review: any '⚠ review' rows above should probably be added to "
        "EXTRA_FILES (or deposited separately) before publishing.\n"
        "  Edit the top of this script and re-run."
    )
    print()


def phase_zenodo(*, dry_run: bool, token: str | None, include_repo_tarball: bool) -> None:
    """Create Zenodo draft and upload artifacts.

    By default this is a HEAVY-DATA deposit: just the files in
    EXTRA_FILES. The repo tarball is omitted because the
    GitHub-Zenodo auto-archive handles routine code-release deposits
    in a separate record series.

    Pass --include-repo-tarball if you've DISABLED auto-archive and
    want this script to be the single bundled record (code + data).
    """
    announce("PHASE 3 — Zenodo: create draft deposit + upload artifacts")

    if not token and not dry_run:
        bail("ZENODO_TOKEN env var required for the Zenodo phase (or pass --dry-run)")

    tarball: Path | None = None
    head_sha: str | None = None
    if include_repo_tarball:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        tarball = REPO_ROOT / f"_release-snapshot-{timestamp}.tar.gz"
        head_sha = git_archive_repo(tarball, dry_run=dry_run)
        ok(f"repo tarball: {tarball.name} @ HEAD={head_sha[:12]}")
    else:
        ok(
            "skipping repo tarball (auto-archive handles code-release "
            "deposits — pass --include-repo-tarball to override)"
        )

    deposit = zenodo_create_deposit(token or "", SEED_METADATA, dry_run=dry_run)
    deposit_id = deposit["id"]
    bucket = deposit.get("links", {}).get("bucket", "")
    edit_url = deposit.get("links", {}).get("html", "")
    reserved_doi = (
        deposit.get("metadata", {}).get("prereserve_doi", {}).get("doi")
        or "(no DOI reserved)"
    )

    ok(f"draft created: id={deposit_id} doi={reserved_doi}")

    # Upload repo tarball if requested
    if include_repo_tarball and tarball is not None:
        announce(f"Uploading repo tarball to deposit {deposit_id}")
        zenodo_upload_file(bucket, token or "", tarball, dry_run=dry_run)

    # Upload extra heavy data files. Each entry in EXTRA_FILES is
    # either a local path, a bare URL, or a {url, filename} dict.
    announce("Uploading heavy data files (EXTRA_FILES)")
    if not EXTRA_FILES:
        warn(
            "EXTRA_FILES is empty — uncomment / add entries in the "
            "config block at the top of this script to bundle heavy data."
        )
    for entry in EXTRA_FILES:
        try:
            resolved = _resolve_extra_file(entry, dry_run=dry_run)
        except Exception as exc:
            warn(f"skipping entry {entry!r}: {exc}")
            continue
        if not resolved:
            continue  # already warned (missing local file)
        # `resolved` is a list so one entry (e.g. the manuscript bundle)
        # can yield multiple files — PDF + JATS XML — from a single
        # config block.
        for local_path, cleanup in resolved:
            try:
                zenodo_upload_file(
                    bucket, token or "", local_path,
                    dry_run=dry_run, destination_name=local_path.name,
                )
            finally:
                if cleanup:
                    try:
                        local_path.unlink()
                    except FileNotFoundError:
                        pass

    # Cleanup local tarball (if we created one)
    if tarball is not None and not dry_run and tarball.exists():
        tarball.unlink()
        ok(f"removed local snapshot {tarball.name}")

    # Summary
    announce("Zenodo phase complete")
    print()
    print(f"  Zenodo draft URL:   {edit_url}")
    print(f"  Reserved DOI:       {reserved_doi}")
    print(f"  Deposit ID:         {deposit_id}")
    print()
    print("  Next steps:")
    print("    1. Open the draft in the Zenodo UI to review metadata + files")
    print("    2. Add ORCID IDs, affiliations, related identifiers, etc.")
    print("    3. When ready, click Publish")
    print(
        "    4. After publishing, populate `doi` in FIGURE_PROVENANCE "
        "in scripts/figures/embed_figure_gist_metadata.py and re-run that script"
    )
    print()


def phase_update_figure_swhids(
    swhid_results: dict[str, str | None], *, dry_run: bool,
) -> None:
    """Bake the newly-minted gist SWHIDs back into the figures.

    Two side effects:

      1. Edits ``scripts/figures/embed_figure_gist_metadata.py`` in place,
         replacing each managed figure's top-level ``"swhid"`` field
         in FIGURE_PROVENANCE with the SWHID just minted by SWH for
         that figure's gist. (Idempotent — same SWHID = no-op.)

      2. Re-runs ``scripts/figures/embed_figure_gist_metadata.py`` to refresh
         the embedded ``provenance`` JSON in every managed figure's
         PNG/PDF. This DOES NOT regenerate the figure pixels — only
         the metadata chunks change (PIL/pikepdf opens, swaps the
         chunk, writes back).

    Skips silently if no gist URL in swhid_results matches a figure
    in FIGURE_PROVENANCE.
    """
    announce("PHASE 1.5 — Bake new SWHIDs back into figure metadata")

    target = REPO_ROOT / "scripts" / "embed_figure_gist_metadata.py"
    if not target.is_file():
        warn(f"can't find {target}; skipping")
        return

    source = target.read_text()
    new_source = source
    updates: list[tuple[str, str, str]] = []  # (gist_url, old, new)

    for origin, new_swhid in swhid_results.items():
        if not new_swhid:
            continue
        if not origin.startswith("https://gist.github.com/"):
            continue  # repo SWHID isn't in FIGURE_PROVENANCE per-figure

        # Locate the figure entry whose gist_url matches this origin.
        url_pattern = re.escape(origin)
        url_match = re.search(rf'"gist_url":\s*"{url_pattern}"', new_source)
        if not url_match:
            warn(f"  no FIGURE_PROVENANCE entry with gist_url = {origin}")
            continue

        # From the gist_url line, scan forward for the next "swhid":
        # line within the same figure's entry. The pattern matches
        # either `None` (no SWHID yet) or `"swh:..."` (existing SWHID).
        after = new_source[url_match.end():]
        swhid_match = re.search(r'("swhid":\s*)(None|"[^"]*")', after)
        if not swhid_match:
            warn(f"  found gist_url but no swhid field nearby for {origin}")
            continue

        old_literal = swhid_match.group(2)
        new_literal = f'"{new_swhid}"'
        if old_literal == new_literal:
            ok(f"  swhid already up to date for {origin[:64]}…")
            continue

        # Splice in the new value at the absolute offset.
        start = url_match.end() + swhid_match.start()
        end = url_match.end() + swhid_match.end()
        new_source = (
            new_source[:start]
            + swhid_match.group(1) + new_literal
            + new_source[end:]
        )
        updates.append((origin, old_literal, new_swhid))

    if not updates:
        ok("no FIGURE_PROVENANCE swhid changes needed")
        return

    print()
    print("  Updates to FIGURE_PROVENANCE.swhid:")
    for origin, old, new in updates:
        gist_id = origin.rsplit("/", 1)[-1]
        print(f"    {gist_id}: {old}  →  \"{new}\"")
    print()

    if dry_run:
        ok("[dry-run] would write the updated source file + re-embed")
        return

    target.write_text(new_source)
    ok(f"wrote {target.relative_to(REPO_ROOT)} ({len(updates)} figure(s) updated)")

    # Re-run the embed script to refresh PNG/PDF metadata chunks. This
    # doesn't re-render the figures; PIL/pikepdf only modify the
    # metadata chunks of the existing files.
    announce("Re-running embed_figure_gist_metadata.py to refresh PNG/PDF metadata")
    try:
        subprocess.run(
            ["uv", "run", "python", "scripts/figures/embed_figure_gist_metadata.py"],
            cwd=REPO_ROOT,
            check=True,
        )
        ok("PNG/PDF metadata refreshed")
    except subprocess.CalledProcessError as exc:
        warn(f"embed re-run failed: {exc}")


def phase_github_release(tag: str, *, dry_run: bool) -> None:
    """Tag HEAD, push the tag, and create a GitHub Release.

    Once the GitHub Release is published, the Zenodo GitHub-archive
    integration (assumed enabled) auto-deposits the repo tarball at
    that tag as a new version in the code record series.

    Pre-conditions checked:
      - working tree is clean (or in dry-run mode)
      - `gh` CLI is authenticated
      - tag doesn't already exist locally (refuse to overwrite)
    """
    announce(f"PHASE 4 — Tag + GitHub Release: {tag}")

    if dry_run:
        ok(f"[dry-run] would run: git tag -a {tag} -m '<auto-generated>'")
        ok(f"[dry-run] would run: git push origin {tag}")
        ok(f"[dry-run] would run: gh release create {tag} --generate-notes")
        ok("[dry-run] Zenodo auto-archive would fire on the release event")
        return

    # Working tree must be clean — refuse to tag on top of dirty state
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
    ).decode().strip()
    if status:
        bail(
            f"working tree not clean — refusing to tag.\n"
            f"  modified: {status.splitlines()[:5]}"
        )

    # Tag must not already exist
    existing = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=REPO_ROOT, capture_output=True,
    )
    if existing.returncode == 0:
        bail(
            f"tag {tag} already exists locally — refusing to overwrite.\n"
            f"  delete it first with `git tag -d {tag}` if intentional."
        )

    # gh must be authed
    gh_auth = subprocess.run(
        ["gh", "auth", "status"], cwd=REPO_ROOT, capture_output=True,
    )
    if gh_auth.returncode != 0:
        bail(
            "`gh` CLI is not authenticated — run `gh auth login` first."
        )

    # Tag and push
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag}"],
        cwd=REPO_ROOT, check=True,
    )
    ok(f"tagged {tag}")
    subprocess.run(
        ["git", "push", "origin", tag], cwd=REPO_ROOT, check=True,
    )
    ok(f"pushed {tag} to origin")

    # Create the GitHub Release with auto-generated notes
    subprocess.run(
        ["gh", "release", "create", tag, "--generate-notes"],
        cwd=REPO_ROOT, check=True,
    )
    ok(f"created GitHub Release {tag}")
    print()
    print(
        "  Zenodo GitHub-archive integration should fire within a few "
        "minutes. Visit https://zenodo.org/account/settings/github/ "
        "to confirm, or watch for the new code-record DOI."
    )
    print()


def _print_release_hint() -> None:
    """If --gh-release wasn't passed, remind the operator how to do it."""
    announce("Next step (optional): GitHub Release → Zenodo code-record")
    print()
    print(
        "  To refresh the code-record DOI series, tag a release in this repo.\n"
        "  Zenodo's GitHub-archive integration (must be enabled) auto-deposits.\n"
    )
    print("    git tag -a vX.Y.Z -m 'Release vX.Y.Z'")
    print("    git push origin vX.Y.Z")
    print("    gh release create vX.Y.Z --generate-notes")
    print()
    print(
        "  Or re-run this script with --gh-release vX.Y.Z to do it automatically."
    )
    print()


# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publish accessible-surfaceome to Software Heritage + Zenodo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="describe what would happen without making API calls",
    )
    ap.add_argument(
        "--skip-zenodo",
        action="store_true",
        help="run SWH phase only (no deposit / draft created)",
    )
    ap.add_argument(
        "--skip-swh",
        action="store_true",
        help="skip Software Heritage submissions; only run audit + Zenodo phases",
    )
    ap.add_argument(
        "--include-repo-tarball",
        action="store_true",
        help=(
            "snapshot the repo at HEAD as a tar.gz and include it in the Zenodo "
            "deposit. OFF by default: assumes GitHub-Zenodo auto-archive handles "
            "code-release deposits in a separate record series. Pass this flag "
            "if you've disabled auto-archive and want one bundled record."
        ),
    )
    ap.add_argument(
        "--gh-release",
        metavar="TAG",
        help=(
            "after the Zenodo phase finishes, tag HEAD as TAG (e.g. v1.2.0), "
            "push the tag, and create a GitHub Release with auto-generated notes. "
            "Triggers the GitHub-Zenodo auto-archive to mint a code-record DOI. "
            "OFF by default — the script prints the commands instead and lets "
            "you decide when to tag."
        ),
    )
    ap.add_argument(
        "--update-figures",
        action="store_true",
        help=(
            "after Phase 1 mints SWHIDs, edit FIGURE_PROVENANCE in "
            "scripts/figures/embed_figure_gist_metadata.py to set the new "
            "swhid for each managed figure's gist, then re-run that "
            "script to refresh the PNG/PDF provenance metadata in "
            "place. No figure pixels are re-rendered. OFF by default "
            "(idempotent — same SWHID = no-op anyway)."
        ),
    )
    args = ap.parse_args()

    swh_results: dict[str, str | None] = {}
    if not args.skip_swh:
        swh_results = phase_swh(dry_run=args.dry_run)
    else:
        warn("--skip-swh: skipping Software Heritage submissions")

    if args.update_figures and swh_results:
        phase_update_figure_swhids(swh_results, dry_run=args.dry_run)

    phase_audit_figures(dry_run=args.dry_run)
    phase_audit_data_inputs()

    if not args.skip_zenodo:
        phase_zenodo(
            dry_run=args.dry_run,
            token=os.environ.get("ZENODO_TOKEN"),
            include_repo_tarball=args.include_repo_tarball,
        )
    else:
        warn("--skip-zenodo: skipping Zenodo deposit")

    if args.gh_release:
        phase_github_release(args.gh_release, dry_run=args.dry_run)
    else:
        _print_release_hint()

    # Final summary
    announce("DONE")
    if swh_results:
        print()
        print("  SWHIDs minted:")
        for origin, swhid in swh_results.items():
            label = origin.split("/")[-1] or origin
            status = (
                swhid
                if swhid
                else ("(dry-run)" if args.dry_run else "(failed / pending)")
            )
            print(f"    {label:48s} {status}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
