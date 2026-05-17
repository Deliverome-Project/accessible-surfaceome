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
     scripts/embed_figure_gist_metadata.py).
  3. Polls SWH until each archive succeeds, prints the resulting SWHIDs.
  4. Audits every managed figure's embedded provenance (defers to
     tests/test_figure_provenance.py).
  5. Snapshots the repo as a tar.gz at HEAD.
  6. Creates a DRAFT Zenodo deposit (nothing is published) containing:
        - the repo tarball
        - extra heavy data files listed in EXTRA_FILES below
     The deposit is private until you click "Publish" in the Zenodo UI.

After publication in the Zenodo UI, you populate `doi` in
scripts/embed_figure_gist_metadata.py's FIGURE_PROVENANCE, re-run that
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
# FIGURE_PROVENANCE in scripts/embed_figure_gist_metadata.py — keep in
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
# tar.gz; no nested JSON for analytics:
#
#   1. triage-runs-with-reasoning.tsv  →  "what did Sonnet say about
#      every gene in the candidate universe, with reasoning + cost?"
#      Long format, one row per (gene × variant × replicate). Pinned
#      to run_id=genome_full_sonnet_ncbi_v1 (Sonnet on ~19k genes).
#      Augmented at deposit time with: uniprot_acc + per-source DB
#      votes (uniprot/go/surfy/cspa/hpa) joined from /v1/catalog. The
#      headline figures pull from here.
#
#   2. triage-benchmark-with-reasoning.tsv  →  "for each of the 147
#      bench genes, what does every model variant say (Haiku / Sonnet /
#      Opus × naive / ncbi / web_ncbi / pubmed_ncbi), with reasoning?
#      And what does the curated truth say?"  Long format, one row per
#      (bench gene × model × variant × replicate). Pinned to
#      run_id=mainbench_canonical_v1 (the multi-model bench sweep).
#      Augmented at deposit time with: uniprot_acc + DB votes (same as
#      #1) + truth_verdict + truth_signal + truth_reason joined from
#      /v1/benchmark/export.tsv. Haiku and Opus only appear here — the
#      broad triage in #1 is Sonnet-only.
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
EXTRA_FILES: list[str | dict[str, Any]] = [
    {
        "enriched_triage": True,
        "filename": "triage-runs-with-reasoning.tsv",
        "run_id": "genome_full_sonnet_ncbi_v1",
        "join_truth": False,
    },
    {
        "enriched_triage": True,
        "filename": "triage-benchmark-with-reasoning.tsv",
        "run_id": "mainbench_canonical_v1",
        "join_truth": True,
    },
    {
        "deep_dives_bundle": True,
        "filename": "deep_dives_all.tar.gz",
        "index_url": "https://api.deliverome.org/surfaceome/v1/genes",
        "gene_url_template": "https://api.deliverome.org/surfaceome/v1/genes/{symbol}",
    },
    {
        # In-deposit README — documents every column of every file
        # above, the source-join recipe used to construct them, and
        # the live-API endpoints that reproduce them. Travels WITH
        # the data on Zenodo so the bytes are self-explanatory.
        "deposit_readme": True,
        "filename": "README.md",
    },
]

# Seed metadata for the Zenodo deposit. The Zenodo UI lets you edit
# every field before publishing — these are sensible defaults.
SEED_METADATA = {
    "metadata": {
        "upload_type": "dataset",
        "title": "accessible-surfaceome — auxiliary data outputs",
        "description": (
            "Auxiliary data outputs for the accessible-surfaceome "
            "project — files too large or too operational to live in "
            "the repository directly. Three data files plus an in-"
            "deposit README that documents every column and the source-"
            "join recipe used to construct each file:<br><br>"
            "<b>triage-runs-with-reasoning.tsv</b> — Sonnet 4.6 verdicts "
            "with full reasoning across the ~19k-gene M1 candidate "
            "universe, joined with per-source DB votes (UniProt / GO / "
            "SURFY / CSPA / HPA) from the catalog.<br><br>"
            "<b>triage-benchmark-with-reasoning.tsv</b> — Haiku 4.5 / "
            "Sonnet 4.6 / Opus 4.7 verdicts (4 prompt variants each) on "
            "the 147-gene curated benchmark, joined with the same DB "
            "votes plus curated truth labels.<br><br>"
            "<b>deep_dives_all.tar.gz</b> — every published per-gene "
            "SurfaceomeRecord with full evidence chain and per-claim "
            "verbatim quotes.<br><br>"
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
        # Fill in concept DOI(s) once the auto-archive has produced its
        # first release; the link makes the relationship explicit in
        # CrossRef/DataCite and Zenodo's UI.
        "related_identifiers": [
            # {
            #     "identifier": "10.5281/zenodo.<CODE-CONCEPT-DOI>",
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
) -> tuple[Path, bool] | None:
    """Resolve one EXTRA_FILES entry to a (local_path, cleanup) pair.

    Five input shapes:

      - bare HTTP(S) URL: fetched to a tempfile, returned with
        cleanup=True so the caller deletes it after upload. Destination
        name is the URL's last path segment.

      - {"url": "...", "filename": "..."} dict: same fetch behaviour
        but destination name is the explicit filename.

      - {"enriched_triage": True, "filename": "...", "run_id": "...",
        "join_truth": bool}: fetches /v1/triage/export.tsv for the
        given run_id, joins per-source DB votes from /v1/catalog, and
        (if join_truth) joins curated truth_verdict/signal/reason from
        /v1/benchmark/export.tsv. Writes one enriched TSV locally.

      - {"deep_dives_bundle": True, "filename": "...", "index_url":
        "...", "gene_url_template": "..."}: special-case resolver that
        fetches the gene index from `index_url`, then for each entry
        fetches `gene_url_template.format(symbol=...)`, then tars all
        per-gene JSONs into a single gzipped archive.

      - other string: treated as a path relative to REPO_ROOT. If the
        local file doesn't exist, warns and returns None.

    Raises on fetch errors so the caller can decide whether to skip.
    """
    # Bare URL
    if isinstance(entry, str) and entry.startswith(("http://", "https://")):
        return _download_to_tempfile(entry, filename=None, dry_run=dry_run), True

    # Dict forms
    if isinstance(entry, dict):
        if entry.get("deep_dives_bundle"):
            return _build_deep_dives_bundle(entry, dry_run=dry_run), True
        if entry.get("enriched_triage"):
            return _build_enriched_triage(entry, dry_run=dry_run), True
        if entry.get("deposit_readme"):
            return _build_deposit_readme(entry, dry_run=dry_run), True
        url = entry.get("url")
        filename = entry.get("filename")
        if not url:
            raise ValueError("dict entry missing 'url'")
        return _download_to_tempfile(url, filename=filename, dry_run=dry_run), True

    # Local path
    if isinstance(entry, str):
        path = REPO_ROOT / entry
        if not path.exists():
            warn(f"  - missing local file (will skip): {entry}")
            return None
        return path, False

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


def _build_enriched_triage(
    entry: dict[str, Any], *, dry_run: bool,
) -> Path:
    """Fetch /v1/triage/export.tsv for run_id, join DB votes from
    /v1/catalog, optionally join truth labels from
    /v1/benchmark/export.tsv. Emit one enriched TSV.

    Why join client-side instead of changing the Worker: the public
    triage endpoint stays a thin telemetry view, and the enrichment
    cost only happens at deposit time. The resulting TSV is fully
    self-contained — readers don't need to JOIN three URLs to get a
    usable analysis frame.

    Column order in the output:
      gene_symbol, uniprot_acc,
      db_uniprot, db_go, db_surfy, db_cspa, db_hpa, n_db_surface,
      [truth_verdict, truth_signal, truth_reason]    ← if join_truth
      model, prompt_variant, replicate,
      predicted_verdict, predicted_reason, predicted_confidence,
      prompt_tokens, completion_tokens, cache_creation_tokens,
      cache_read_tokens, n_web_searches, cost_usd, latency_s
    """
    filename = entry["filename"]
    run_id = entry["run_id"]
    join_truth = bool(entry.get("join_truth"))

    api_base = "https://api.deliverome.org/surfaceome/v1"
    triage_url = f"{api_base}/triage/export.tsv?run_id={run_id}"
    catalog_url = f"{api_base}/catalog"
    truth_url = f"{api_base}/benchmark/export.tsv"

    tmp_root = REPO_ROOT / "_extra-download"

    if dry_run:
        msg = (
            f"[dry-run] would fetch {triage_url} + {catalog_url}"
            + (f" + {truth_url}" if join_truth else "")
            + f" → join client-side → {filename}"
        )
        ok(msg)
        return tmp_root / filename

    tmp_root.mkdir(exist_ok=True)

    # 1. Fetch the triage TSV (with retry — the genome-wide export
    # can 503 on a cold cache).
    triage_resp = _http_get_with_retry(triage_url, timeout=300)
    triage_text = triage_resp.text
    triage_lines = triage_text.rstrip("\n").split("\n")
    if len(triage_lines) < 2:
        raise ValueError(f"triage export at {triage_url} returned no rows")
    triage_header = triage_lines[0].split("\t")
    if triage_header[0] != "gene_symbol":
        raise ValueError(
            f"unexpected first column in triage export: {triage_header[0]!r}"
        )
    ok(f"fetched triage export ({len(triage_lines) - 1:,} rows, run_id={run_id})")

    # 2. Fetch the catalog (for DB votes + uniprot_acc).
    catalog_resp = _http_get_with_retry(catalog_url, timeout=120)
    catalog = catalog_resp.json()
    db_keys = catalog.get("db_keys") or ["uniprot", "go", "surfy", "cspa", "hpa"]
    # Build {symbol → (uniprot_acc, db_bitmask)} index.
    cat_by_sym: dict[str, tuple[str, int]] = {}
    for row in catalog.get("rows", []):
        sym = row.get("symbol")
        if not sym:
            continue
        cat_by_sym[sym] = (row.get("uniprot") or "", int(row.get("db") or 0))
    ok(f"fetched catalog ({len(cat_by_sym):,} symbols, db_keys={db_keys})")

    # 3. Optionally fetch truth labels.
    truth_by_sym: dict[str, tuple[str, str, str]] = {}
    if join_truth:
        truth_resp = _http_get_with_retry(truth_url, timeout=60)
        truth_lines = truth_resp.text.rstrip("\n").split("\n")
        truth_header = truth_lines[0].split("\t")
        # /v1/benchmark/export.tsv shape:
        # gene gene_symbol uniprot class ground_truth_verdict
        # ground_truth_signal ground_truth_reason rationale
        idx = {name: i for i, name in enumerate(truth_header)}
        sym_col: int | None = idx.get("gene_symbol", idx.get("gene"))
        if sym_col is None:
            raise ValueError(
                f"truth export at {truth_url} has neither "
                f"'gene_symbol' nor 'gene' column; got {truth_header}"
            )
        v_col = idx["ground_truth_verdict"]
        s_col = idx["ground_truth_signal"]
        r_col = idx["ground_truth_reason"]
        for line in truth_lines[1:]:
            cells = line.split("\t")
            truth_by_sym[cells[sym_col]] = (cells[v_col], cells[s_col], cells[r_col])
        ok(f"fetched truth labels ({len(truth_by_sym):,} bench genes)")

    # 4. Compose enriched TSV. Column order: identity → DB votes →
    # truth (optional) → model output telemetry.
    db_cols = [f"db_{k}" for k in db_keys]
    truth_cols = ["truth_verdict", "truth_signal", "truth_reason"] if join_truth else []
    new_header = (
        ["gene_symbol", "uniprot_acc"]
        + db_cols
        + ["n_db_surface"]
        + truth_cols
        + triage_header[1:]  # drop the original gene_symbol; everything after
    )

    out_path = tmp_root / filename
    with out_path.open("w") as fh:
        fh.write("\t".join(new_header) + "\n")
        n_joined_db = 0
        n_joined_truth = 0
        for line in triage_lines[1:]:
            cells = line.split("\t")
            sym = cells[0]
            uniprot_acc, db_mask = cat_by_sym.get(sym, ("", 0))
            if sym in cat_by_sym:
                n_joined_db += 1
            db_votes = [str((db_mask >> i) & 1) for i in range(len(db_keys))]
            n_db = sum(int(v) for v in db_votes)
            prefix = [sym, uniprot_acc, *db_votes, str(n_db)]
            if join_truth:
                tv, ts, tr = truth_by_sym.get(sym, ("", "", ""))
                if sym in truth_by_sym:
                    n_joined_truth += 1
                prefix += [tv, ts, tr]
            fh.write("\t".join(prefix + cells[1:]) + "\n")

    size_mb = out_path.stat().st_size / 1024 / 1024
    msg = (
        f"built {out_path.name} ({size_mb:.1f} MB, "
        f"{len(triage_lines) - 1:,} rows, db-joined={n_joined_db:,}"
    )
    if join_truth:
        msg += f", truth-joined={n_joined_truth:,}"
    ok(msg + ")")
    return out_path


def _build_deposit_readme(
    entry: dict[str, Any], *, dry_run: bool,
) -> Path:
    """Generate the in-deposit README.md that documents every file's
    columns, the source-join recipe used to construct each enriched
    TSV, and the live-API endpoints that reproduce them.

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

This deposit contains the auxiliary data outputs for the
[accessible-surfaceome](https://github.com/Deliverome-Project/accessible-surfaceome)
project — files too large or too operational to live in the
repository directly. The repository code itself is archived separately
(GitHub-Zenodo auto-archive + Software Heritage continuous crawl).

All three data files were assembled at deposit time by the
[`scripts/release/publish-archive.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{head_sha}/scripts/release/publish-archive.py)
script in the repo at commit `{head_sha[:12]}`. Anyone can regenerate
them from the public read-only API documented below.

## Files

### 1. `triage-runs-with-reasoning.tsv`

Long-format TSV, one row per (gene × prompt variant × replicate),
covering Sonnet 4.6 inference across the **~19k-gene M1 candidate
universe**. The single source of truth for the cost-vs-accuracy and
db-correctness figures in the project.

| Column | Source | Meaning |
|---|---|---|
| `gene_symbol` | triage export | HGNC gene symbol |
| `uniprot_acc` | catalog join | UniProt accession (canonical isoform) |
| `db_uniprot`, `db_go`, `db_surfy`, `db_cspa`, `db_hpa` | catalog join | 0/1 — does each surface-DB source vote "surface" for this gene? |
| `n_db_surface` | derived | sum of the 5 DB votes (0–5) |
| `model` | triage export | Anthropic model identifier (Sonnet only in this file) |
| `prompt_variant` | triage export | which prompt variant was used (`ncbi` only in this file) |
| `replicate` | triage export | replicate index within the sweep |
| `predicted_verdict` | triage export | model verdict: `yes` / `contextual` / `no` |
| `predicted_reason` | triage export | short controlled-vocab reason tag |
| `predicted_confidence` | triage export | `low` / `medium` / `high` |
| `prompt_tokens`, `completion_tokens`, `cache_creation_tokens`, `cache_read_tokens` | triage export | per-call token counts |
| `n_web_searches` | triage export | number of web tool calls in this run |
| `cost_usd` | triage export | computed dollar cost of this call |
| `latency_s` | triage export | wall-clock seconds for this call |

**Construction (source-join recipe):**

```bash
# 1. The model output (long format, one row per call):
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=genome_full_sonnet_ncbi_v1' > triage.tsv

# 2. The DB-vote panel (per-gene 5-bit bitmask + uniprot_acc):
curl 'https://api.deliverome.org/surfaceome/v1/catalog' > catalog.json
#    catalog.rows[i].db is a 5-bit int; catalog.db_keys lists the bit order.

# 3. LEFT JOIN catalog into triage on gene_symbol; decode the bitmask
#    into 5 separate db_<source> columns plus n_db_surface = popcount(db).
```

### 2. `triage-benchmark-with-reasoning.tsv`

Long-format TSV, one row per (bench gene × model × prompt variant ×
replicate), covering the **147-gene curated benchmark** across all 3
production models (Haiku 4.5, Sonnet 4.6, Opus 4.7) and all 4 prompt
variants (`naive`, `ncbi`, `web_ncbi`, `pubmed_ncbi`). Haiku and Opus
only appear in this file — the broad triage in #1 is Sonnet-only.

Same columns as #1, **plus** three truth-label columns joined from the
curated bench:

| Column | Source | Meaning |
|---|---|---|
| `truth_verdict` | bench export join | curated truth: `yes` / `contextual` / `no` |
| `truth_signal` | bench export join | curated signal: `likely_accessible` / `unlikely` / etc. |
| `truth_reason` | bench export join | curated reason tag (controlled vocab) |

**Construction:**

```bash
# 1. Bench-restricted multi-model sweep:
curl 'https://api.deliverome.org/surfaceome/v1/triage/export.tsv?run_id=mainbench_canonical_v1' > triage_bench.tsv

# 2. Same catalog as #1 above.
# 3. Curated truth labels (7 cols: gene/uniprot/class/ground_truth_*):
curl 'https://api.deliverome.org/surfaceome/v1/benchmark/export.tsv' > truth.tsv

# 4. LEFT JOIN catalog and truth into triage_bench on gene_symbol.
```

### 3. `deep_dives_all.tar.gz`

Gzipped tarball, one `<SYMBOL>.json` member per published deep-dive
`SurfaceomeRecord`. Members are flat (no parent directory); `tar -tf`
doubles as the index.

Each per-gene JSON is the full `SurfaceomeRecord` v0.5.0+ as described
in
[`src/accessible_surfaceome/tools/_shared/models.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/{head_sha}/src/accessible_surfaceome/tools/_shared/models.py)
— surface_evidence, biological_context, accessibility_risks, evidence
chain with verbatim quotes + char offsets, search_log, confidence
reasoning.

**Construction:**

```bash
# 1. List published deep-dives:
curl 'https://api.deliverome.org/surfaceome/v1/genes' | jq -r '.genes[].gene_symbol'

# 2. For each symbol, fetch the full record:
curl 'https://api.deliverome.org/surfaceome/v1/genes/<SYMBOL>' > <SYMBOL>.json

# 3. tar -czf deep_dives_all.tar.gz *.json   (flat layout)
```

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
        warn("consider re-running scripts/embed_figure_gist_metadata.py before Zenodo")
        return False


def phase_audit_data_inputs() -> None:
    """Surface every data input referenced by a managed figure's
    provenance, so the operator can decide which to include in the
    Zenodo deposit.

    Reads ``FIGURE_PROVENANCE`` from ``scripts/embed_figure_gist_metadata.py``
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
        if resolved is None:
            continue  # already warned (missing local file)
        local_path, cleanup = resolved
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
        "in scripts/embed_figure_gist_metadata.py and re-run that script"
    )
    print()


def phase_update_figure_swhids(
    swhid_results: dict[str, str | None], *, dry_run: bool,
) -> None:
    """Bake the newly-minted gist SWHIDs back into the figures.

    Two side effects:

      1. Edits ``scripts/embed_figure_gist_metadata.py`` in place,
         replacing each managed figure's top-level ``"swhid"`` field
         in FIGURE_PROVENANCE with the SWHID just minted by SWH for
         that figure's gist. (Idempotent — same SWHID = no-op.)

      2. Re-runs ``scripts/embed_figure_gist_metadata.py`` to refresh
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
            ["uv", "run", "python", "scripts/embed_figure_gist_metadata.py"],
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
            "scripts/embed_figure_gist_metadata.py to set the new "
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
