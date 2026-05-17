"""Run the full topology + paralog sweep, multithreaded, with checkpointing.

Stages:
    1. Load the candidate accession set (built by build_topology_candidate_set.py).
    2. Resolve per-cohort accessions:
         human_canonical → the candidate UniProt accessions
         human_isoforms  → AFDB-modeled isoforms of those accessions (resolved
                           via UniProt isoform query — see _resolve_human_isoforms)
         mouse_ortholog  → one2one_highconf mouse orthologs from the existing
                           Compara CSV (no refresh — the orchestrator assumes
                           it is up-to-date; refresh via ensembl_compara
                           download separately)
         cyno_ortholog   → same, cyno
    3. Fetch FASTAs for every accession to disk cache (ThreadPoolExecutor).
    4. Per cohort: assemble batch FASTAs, run DeepTMHMM in a ProcessPoolExecutor,
       parse .3line into rich records, write topology_records.jsonl.
    5. Pull Compara paralogs once for the candidate set, compute ECD identity
       against the human_canonical topology, write paralog_records.jsonl.
    6. Upload to D1 (private + public) via upload_topology_to_d1.py and
       upload_paralogs_to_d1.py.

Per-batch checkpoint: existence of ``predicted_topologies.3line`` for a batch
under the run dir → skip that batch on resume. The orchestrator can be
``Ctrl-C``'d at any point and re-invoked with the same ``--topology-version``
to pick up where it left off.

Usage::

    uv run python scripts/run_topology_sweep.py \\
        --topology-version topo_2026_05_16 \\
        --cohorts human_canonical,human_isoforms,mouse_ortholog,cyno_ortholog \\
        --max-workers 6

For a 3-protein dry run::

    uv run python scripts/run_topology_sweep.py \\
        --topology-version topo_test \\
        --candidate-set data/processed/topology_run_topo_test/candidate_accessions.tsv \\
        --cohorts human_canonical \\
        --max-workers 2 \\
        --skip-paralogs \\
        --skip-upload
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.sources.deeptmhmm import (
    DEEPTMHMM_MAX_SEQUENCE_LENGTH,
    DEEPTMHMM_TOOL_VERSION,
    SEQUENCE_CACHE_DIR,
    assemble_batch_fasta,
    fetch_uniprot_fastas_to_cache,
    parse_3line,
    run_deeptmhmm_batch,
)

logger = logging.getLogger(__name__)

VALID_COHORTS = {"human_canonical", "human_isoforms", "mouse_ortholog", "cyno_ortholog"}
SPECIES_BY_COHORT = {
    "human_canonical": "human",
    "human_isoforms": "human",
    "mouse_ortholog": "mouse",
    "cyno_ortholog": "cynomolgus",
}

DEFAULT_BATCH_SIZE = 50
DEFAULT_COMPARA_VERSION = "Compara r112"

# Where the existing Compara ortholog CSV lives — produced by
# ensembl_compara.py download. The orchestrator reads it for mouse/cyno
# accessions; it does NOT refresh it (refresh is a manual prereq step
# documented in CLAUDE.md / the plan).
COMPARA_ORTHOLOG_CSV = (
    REPO_ROOT / "data" / "external" / "ensembl_compara_surfaceome_expressed"
    / "compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"
)
COMPARA_PARALOG_BY_GENE_CSV = (
    REPO_ROOT / "data" / "external" / "ensembl_compara_paralogs"
    / "compara_paralogs_by_gene.csv"
)


# ---------------------------------------------------------------------------
# Stage 1 — load candidate accessions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One candidate row — HGNC-ID-keyed, stable IDs from gene_identifier.

    ``hgnc_id`` is the canonical join key; ``uniprot_acc`` and ``ensembl_gene``
    are the resolved stable IDs the orchestrator hands to UniProt (FASTA
    fetch) and BioMart (paralog/ortholog pulls) respectively.
    ``cohort_symbol`` is the only symbol kept on the dataclass — it joins
    against legacy symbol-keyed sources (``triage_run.gene_symbol``, the
    Compara orthologs CSV's ``input_gene_symbol``) and is the resolver's
    snapshot of the cohort symbol at build time, NOT a free-text symbol
    lookup. ``hgnc_symbol`` lives in the TSV for human reading but isn't
    threaded as a Python attribute to avoid accidental use as a join key.
    """

    hgnc_id: str
    cohort_symbol: str
    uniprot_acc: str
    ensembl_gene: str | None
    ncbi_gene_id: int | None
    selection_reason: str       # db_only | triage_only | both | override
    triage_verdict: str | None  # yes | contextual | None


def load_candidate_set(path: Path) -> list[Candidate]:
    """Read the HGNC-keyed candidate accessions TSV emitted by
    ``scripts/build_topology_candidate_set.py``.

    Hard-fails on rows that are missing ``hgnc_id`` or ``uniprot_acc`` —
    the symbol-fallback codepath was deliberately removed after PR #30
    landed. Every candidate must be resolved through ``gene_identifier``
    upstream; the orchestrator never re-resolves from a free-text symbol.
    """
    if not path.exists():
        raise SystemExit(
            f"candidate set not found at {path}; "
            f"run scripts/build_topology_candidate_set.py first"
        )
    rows: list[Candidate] = []
    with path.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            hgnc_id = (r.get("hgnc_id") or "").strip()
            acc = (r.get("uniprot_acc") or "").strip().upper()
            if not hgnc_id:
                raise SystemExit(
                    f"candidate row missing hgnc_id in {path}; rebuild with "
                    f"the HGNC-first scripts/build_topology_candidate_set.py"
                )
            if not acc:
                continue  # gene_identifier didn't resolve a uniprot_acc — drop, not a bug
            ncbi_raw = (r.get("ncbi_gene_id") or "").strip()
            try:
                ncbi = int(ncbi_raw) if ncbi_raw else None
            except ValueError:
                ncbi = None
            rows.append(
                Candidate(
                    hgnc_id=hgnc_id,
                    cohort_symbol=(r.get("cohort_symbol") or "").strip(),
                    uniprot_acc=acc,
                    ensembl_gene=(r.get("ensembl_gene") or None) or None,
                    ncbi_gene_id=ncbi,
                    selection_reason=(r.get("selection_reason") or "").strip(),
                    triage_verdict=(r.get("triage_verdict") or None) or None,
                )
            )
    return rows


# ---------------------------------------------------------------------------
# Stage 2 — per-cohort accession resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrthologTarget:
    """One ortholog target: ``(human_hgnc_id, ortholog_ensembl_gene)``.

    The human HGNC ID is the join key that lets every ortholog topology
    row link back to the human gene the prediction was triggered by.
    Stamped onto the ortholog topology_public rows so a consumer can do
    ``SELECT * FROM topology_public WHERE cohort='mouse_ortholog' AND
    hgnc_id='HGNC:4526'`` to get GPR75's mouse ortholog topology.
    """

    human_hgnc_id: str
    human_ensembl_gene: str
    ortholog_ensembl_gene: str
    ortholog_gene_symbol: str
    species_taxon_id: int            # 10090=mouse, 9544=cynomolgus
    percent_identity: float | None


# Cohort → (D1 compara_ortholog.species value, UniProt organism_id).
# NCBI taxon IDs:
#   * Mus musculus (mouse) = 10090
#   * Macaca fascicularis (cynomolgus, crab-eating macaque) = 9541
#     NOT 9544 — that's Macaca mulatta (rhesus). Compara's "cynomolgus"
#     species value refers to M. fascicularis (ENSMFAG Ensembl IDs).
ORTHOLOG_SPECIES: dict[str, tuple[str, int]] = {
    "mouse_ortholog": ("mouse", 10090),
    "cyno_ortholog": ("cynomolgus", 9541),
}


def _resolve_ortholog_targets_from_d1(
    candidates: list[Candidate], *, species_key: str
) -> list[OrthologTarget]:
    """Query ``compara_ortholog`` (private D1) for orthologs of the candidate set.

    The public D1's compara_ortholog is populated (~9k rows, mouse+cyno,
    release ``ensembl_compara_2026_05_12``); the private D1 carries the
    same data. Filters to ``orthology_type='ortholog_one2one' AND
    is_high_confidence=1`` and joins to the candidate set on
    ``human_ensembl_gene`` (resolved via gene_identifier — the legitimate
    stable-ID join).

    Returns one ``OrthologTarget`` per (human_hgnc_id, ortholog_ensembl_gene);
    no symbol-keyed paths.
    """
    import os
    import httpx

    species, taxon_id = ORTHOLOG_SPECIES[species_key]

    # Build a {human_ensembl_gene → human_hgnc_id} map from the candidate set —
    # the only thing we need to project HGNC IDs onto the ortholog rows.
    ensg_to_hgnc: dict[str, str] = {}
    for c in candidates:
        if c.ensembl_gene and c.hgnc_id:
            ensg_to_hgnc[c.ensembl_gene.upper()] = c.hgnc_id
    if not ensg_to_hgnc:
        logger.warning(
            "no candidates have ensembl_gene → %s cohort will be empty", species_key
        )
        return []

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    if not (account and token and db):
        logger.warning(
            "D1 env vars missing → %s cohort will be empty", species_key
        )
        return []

    # D1 has no IN-list size cap but per-statement payload is bounded; chunk to
    # keep each request small. 500 IDs per chunk is well under SQLite/D1 limits.
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query"
    ensg_list = sorted(ensg_to_hgnc)
    out: list[OrthologTarget] = []
    seen: set[tuple[str, str]] = set()
    chunk_size = 500
    with httpx.Client(timeout=120) as client:
        for start in range(0, len(ensg_list), chunk_size):
            chunk = ensg_list[start : start + chunk_size]
            quoted = ",".join(f"'{e}'" for e in chunk)
            sql = (
                "SELECT human_ensembl_gene, ortholog_ensembl_gene, "
                "ortholog_gene_symbol, percent_identity FROM compara_ortholog "
                f"WHERE species = '{species}' AND orthology_type = 'ortholog_one2one' "
                f"AND is_high_confidence = 1 AND human_ensembl_gene IN ({quoted})"
            )
            resp = client.post(
                url, json={"sql": sql}, headers={"Authorization": f"Bearer {token}"}
            )
            body = resp.json()
            if not body.get("success"):
                logger.warning("D1 compara_ortholog query failed: %s", body)
                continue
            result = body.get("result") or []
            if isinstance(result, dict):
                result = [result]
            for r in result:
                for row in r.get("results") or []:
                    h_ensg = (row.get("human_ensembl_gene") or "").upper()
                    o_ensg = (row.get("ortholog_ensembl_gene") or "").upper()
                    if not h_ensg or not o_ensg:
                        continue
                    h_hgnc = ensg_to_hgnc.get(h_ensg)
                    if not h_hgnc:
                        continue
                    key = (h_hgnc, o_ensg)
                    if key in seen:
                        continue
                    seen.add(key)
                    pct_raw = row.get("percent_identity")
                    pct = float(pct_raw) if pct_raw is not None else None
                    out.append(
                        OrthologTarget(
                            human_hgnc_id=h_hgnc,
                            human_ensembl_gene=h_ensg,
                            ortholog_ensembl_gene=o_ensg,
                            ortholog_gene_symbol=(row.get("ortholog_gene_symbol") or "").strip(),
                            species_taxon_id=taxon_id,
                            percent_identity=pct,
                        )
                    )
    logger.info(
        "compara_ortholog: %d %s targets for %d candidate Ensembl genes",
        len(out), species_key, len(ensg_list),
    )
    return out


def _resolve_ortholog_uniprots(
    targets: list[OrthologTarget],
    *,
    cache_path: Path,
    max_workers: int = 4,
) -> dict[str, str]:
    """Resolve ortholog Ensembl gene IDs to UniProt accessions via UniProt search.

    The ``compara_ortholog`` D1 table has ``ortholog_uniprot_acc IS NULL``
    everywhere — Compara only carries Ensembl xrefs. We resolve on demand
    by hitting UniProt's REST search with ``xref:ensembl-<ensg>+AND+organism_id:<taxon>``.

    Cached to disk at ``cache_path`` (TSV: ``ensembl_gene\\ttaxon_id\\tuniprot_acc``)
    so repeated runs don't re-hit UniProt for the same orthologs. Cache is
    keyed (ensembl_gene, taxon_id) so a follow-up run with a different
    species doesn't clobber an existing resolution.
    """
    from accessible_surfaceome.sources.deeptmhmm import resolve_uniprot_by_ensembl_gene

    cache: dict[tuple[str, int], str] = {}
    if cache_path.exists():
        with cache_path.open() as f:
            reader = csv.DictReader(f, delimiter="\t")
            for r in reader:
                ensg = (r.get("ensembl_gene") or "").strip().upper()
                taxon_raw = (r.get("taxon_id") or "").strip()
                acc = (r.get("uniprot_acc") or "").strip().upper()
                if ensg and taxon_raw and acc:
                    cache[(ensg, int(taxon_raw))] = acc
    logger.info("ortholog UniProt cache: %d hits already on disk", len(cache))

    needed = [t for t in targets if (t.ortholog_ensembl_gene, t.species_taxon_id) not in cache]
    if not needed:
        return {t.ortholog_ensembl_gene: cache[(t.ortholog_ensembl_gene, t.species_taxon_id)] for t in targets if (t.ortholog_ensembl_gene, t.species_taxon_id) in cache}

    logger.info(
        "resolving %d ortholog Ensembl gene IDs → UniProt accs via REST", len(needed)
    )
    n_resolved = 0
    n_unresolved = 0

    def worker(target: OrthologTarget) -> tuple[OrthologTarget, str | None]:
        acc = resolve_uniprot_by_ensembl_gene(
            target.ortholog_ensembl_gene,
            organism_taxon_id=target.species_taxon_id,
            ortholog_gene_symbol=target.ortholog_gene_symbol,
        )
        return target, acc

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # Append-mode write — preserves previously-resolved entries across cohorts/runs.
    write_header = not cache_path.exists()
    with cache_path.open("a", encoding="utf-8") as f:
        if write_header:
            f.write("ensembl_gene\ttaxon_id\tuniprot_acc\n")
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for target, acc in pool.map(worker, needed):
                if acc:
                    cache[(target.ortholog_ensembl_gene, target.species_taxon_id)] = acc
                    f.write(f"{target.ortholog_ensembl_gene}\t{target.species_taxon_id}\t{acc}\n")
                    n_resolved += 1
                else:
                    n_unresolved += 1
                if (n_resolved + n_unresolved) % 100 == 0:
                    f.flush()
    logger.info(
        "ortholog UniProt resolution: %d new resolved, %d unresolved", n_resolved, n_unresolved
    )

    return {
        t.ortholog_ensembl_gene: cache.get((t.ortholog_ensembl_gene, t.species_taxon_id), "")
        for t in targets
    }


def _existing_canonical_predictions() -> set[str]:
    """Set of uniprot_accession_full strings already predicted (human canonical)."""
    src = (
        REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
        / "human_canonical_non_hla" / "predicted_topologies.3line"
    )
    if not src.exists():
        return set()
    try:
        recs = parse_3line(src)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not parse existing canonical .3line: %s", exc)
        return set()
    return {r["uniprot_accession_full"] for r in recs}


# ---------------------------------------------------------------------------
# Stage 3 — sequence fetch
# ---------------------------------------------------------------------------


def fetch_sequences_for_accessions(
    accessions: list[str],
    *,
    cache_dir: Path,
    max_workers: int,
) -> dict[str, Path]:
    if not accessions:
        return {}
    logger.info("fetching %d FASTAs (cache=%s, workers=%d)",
                len(accessions), cache_dir, max_workers)

    n_done = 0

    def progress(kind: str, acc: str, info: Any) -> None:
        nonlocal n_done
        if kind == "fetch_progress":
            n_done = int(str(info).split("/")[0])
            logger.info("  progress: %s", info)
        elif kind == "fetch_error":
            logger.warning("  fetch failed for %s: %s", acc, info)

    paths = fetch_uniprot_fastas_to_cache(
        accessions,
        cache_dir=cache_dir,
        max_workers=max_workers,
        on_progress=progress,
    )
    logger.info("  fetched %d/%d sequences successfully", len(paths), len(accessions))
    return paths


# ---------------------------------------------------------------------------
# Stage 4 — DeepTMHMM run + parse
# ---------------------------------------------------------------------------


def _run_one_batch(args: tuple[Path, Path]) -> tuple[Path, str | None]:
    """ProcessPoolExecutor entry point. Returns (output_3line, error).

    The worker reads ``DEEPTMHMM_ROOT`` from the env (inherited from the
    parent process), so the orchestrator's ``--deeptmhmm-root`` arg has
    to be promoted to that env var before the pool fans out.
    """
    from accessible_surfaceome.sources.deeptmhmm import resolve_deeptmhmm_paths

    input_fasta, output_dir = args
    package_dir, venv_dir = resolve_deeptmhmm_paths()
    try:
        out_path = run_deeptmhmm_batch(
            input_fasta, output_dir=output_dir,
            package_dir=package_dir, venv_dir=venv_dir,
        )
        return out_path, None
    except Exception as exc:  # noqa: BLE001
        return output_dir / "predicted_topologies.3line", str(exc)


def run_cohort_deeptmhmm(
    *,
    cohort: str,
    cohort_dir: Path,
    fasta_paths: list[Path],
    max_workers: int,
    batch_size: int,
) -> tuple[list[Path], list[str]]:
    """Assemble batch FASTAs, run DeepTMHMM in parallel, return .3line paths + skips."""
    cohort_dir.mkdir(parents=True, exist_ok=True)
    skipped_too_long: list[str] = []

    # Build batch FASTAs (deterministic chunking by sorted path). Each batch
    # produces a pair (input_fasta_path, output_dir). The input FASTA lives
    # OUTSIDE output_dir so DeepTMHMM's predict.py can wipe + re-create
    # output_dir without nuking the input.
    inputs_dir = cohort_dir / "_inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    fasta_paths_sorted = sorted(fasta_paths)
    batches: list[tuple[Path, Path]] = []
    for batch_idx in range(0, len(fasta_paths_sorted), batch_size):
        batch_files = fasta_paths_sorted[batch_idx : batch_idx + batch_size]
        batch_n = batch_idx // batch_size
        batch_fasta = inputs_dir / f"batch_{batch_n:04d}.fasta"
        output_dir = cohort_dir / f"batch_{batch_n:04d}"
        n_written, batch_skips = assemble_batch_fasta(
            batch_files, batch_path=batch_fasta, max_seq_length=DEEPTMHMM_MAX_SEQUENCE_LENGTH,
        )
        skipped_too_long.extend(batch_skips)
        if n_written == 0:
            continue
        batches.append((batch_fasta, output_dir))

    logger.info("  %s: %d batches", cohort, len(batches))

    # Identify batches that already have output (resume).
    to_run = [(fa, od) for fa, od in batches
              if not (od / "predicted_topologies.3line").exists()]
    if len(to_run) < len(batches):
        logger.info("  %s: skipping %d already-done batches (resume)",
                    cohort, len(batches) - len(to_run))

    outputs: list[Path] = []
    errors: list[str] = []

    if to_run:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_one_batch, item): item for item in to_run}
            n_total = len(futures)
            for i, fut in enumerate(as_completed(futures), 1):
                out_path, err = fut.result()
                if err:
                    errors.append(f"{out_path.parent.name}: {err}")
                    logger.warning("  %s: batch %s FAILED: %s",
                                   cohort, out_path.parent.name, err)
                else:
                    outputs.append(out_path)
                    logger.info("  %s: batch %s done (%d/%d)",
                                cohort, out_path.parent.name, i, n_total)

    # Collect all batches' outputs (run + previously-cached).
    final_outputs = [od / "predicted_topologies.3line" for _, od in batches
                     if (od / "predicted_topologies.3line").exists()]
    return final_outputs, skipped_too_long


def parse_cohort_to_jsonl(
    *,
    cohort: str,
    output_3line_paths: list[Path],
    cohort_dir: Path,
    topology_version: str,
    candidate_by_acc: dict[str, Candidate],
    ortholog_human_hgnc_by_acc: dict[str, str] | None = None,
) -> Path:
    """Parse all .3line outputs into one topology_records.jsonl for the cohort.

    Stable-ID stamping per cohort type:

      * **Human cohorts** (``human_canonical``, ``human_isoforms``) — filter
        records to those whose base UniProt accession is a candidate; stamp
        ``hgnc_id`` from the candidate's gene_identifier-resolved HGNC ID.
        The legacy .3line is reused for accessions where DeepTMHMM has
        already run; pre-PR-30 mis-resolutions get filtered out implicitly
        because the candidate set was built from gene_identifier.

      * **Ortholog cohorts** (``mouse_ortholog``, ``cyno_ortholog``) — filter
        to records whose base UniProt accession is in
        ``ortholog_human_hgnc_by_acc`` (the mouse/cyno UniProt accs resolved
        via compara_ortholog joined to the candidate set's human Ensembl
        genes). Stamp ``hgnc_id`` with the HUMAN HGNC ID that triggered
        this ortholog's inclusion. Consumers join
        ``WHERE cohort='mouse_ortholog' AND hgnc_id='HGNC:4526'`` to get
        GPR75's mouse ortholog topology.
    """
    species = SPECIES_BY_COHORT[cohort]
    is_human_cohort = cohort in {"human_canonical", "human_isoforms"}
    is_ortholog_cohort = cohort in {"mouse_ortholog", "cyno_ortholog"}
    out_path = cohort_dir / "topology_records.jsonl"
    cohort_dir.mkdir(parents=True, exist_ok=True)
    n_written = 0
    n_filtered_out = 0
    seen_full_accs: set[str] = set()
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with out_path.open("w", encoding="utf-8") as f:
        for src in output_3line_paths:
            for rec in parse_3line(src):
                base = rec["uniprot_accession"]
                # Cohort-specific filter
                if is_human_cohort and candidate_by_acc and base not in candidate_by_acc:
                    n_filtered_out += 1
                    continue
                if is_ortholog_cohort and ortholog_human_hgnc_by_acc is not None:
                    if base not in ortholog_human_hgnc_by_acc:
                        n_filtered_out += 1
                        continue
                # Dedupe across multiple legacy + fresh .3line files.
                full = rec["uniprot_accession_full"]
                if full in seen_full_accs:
                    continue
                seen_full_accs.add(full)
                rec["topology_version"] = topology_version
                rec["cohort"] = cohort
                rec["species"] = species
                rec["isoform_id"] = rec["uniprot_accession_full"]
                rec["is_canonical"] = int(cohort == "human_canonical"
                                          or rec["uniprot_accession_full"].endswith("-1")
                                          or "-" not in rec["uniprot_accession_full"])
                # Stable IDs from gene_identifier (via the candidate set or the
                # ortholog→human map). hgnc_id is the canonical join key; on
                # ortholog rows it's the HUMAN gene's HGNC ID.
                if is_human_cohort:
                    cand = candidate_by_acc.get(base)
                    rec["hgnc_id"] = cand.hgnc_id if cand else None
                    rec["gene_symbol"] = cand.cohort_symbol if cand else ""
                elif is_ortholog_cohort and ortholog_human_hgnc_by_acc is not None:
                    rec["hgnc_id"] = ortholog_human_hgnc_by_acc.get(base)
                    # The ortholog's own symbol comes from the .3line header
                    # (e.g., 'GPR75_MOUSE' → 'Gpr75'); preserve via uniprot_entry_name.
                    rec["gene_symbol"] = rec.get("uniprot_entry_name", "")
                else:
                    rec["hgnc_id"] = None
                    rec["gene_symbol"] = rec.get("uniprot_entry_name", "")
                rec["tool_version"] = DEEPTMHMM_TOOL_VERSION
                rec["retrieved_at"] = retrieved_at
                f.write(json.dumps(rec, sort_keys=True) + "\n")
                n_written += 1
    logger.info("  %s: wrote %d records (filtered out %d non-candidate) to %s",
                cohort, n_written, n_filtered_out,
                out_path.relative_to(REPO_ROOT))
    return out_path


# ---------------------------------------------------------------------------
# Stage 5 — paralog fetch + ECD identity
# ---------------------------------------------------------------------------


def _expand_candidates_with_paralogs(
    candidates: list[Candidate],
    paralog_csv: Path,
) -> list[Candidate]:
    """Augment the candidate list with paralog UniProt accs not already in it.

    Drives the "Option A" coverage decision: every distinct paralog from the
    BioMart pull gets DeepTMHMM topology so ECD identity is computable for
    every (human, paralog) pair, regardless of full-length percent_identity
    (which is the wrong metric to threshold on for surface proteins anyway).

    Pipeline:
      1. Read paralog_ensembl_gene values from the Compara CSV
      2. Resolve each via ``gene_identifier`` (D1) → (hgnc_id, uniprot_acc,
         ensembl_gene, ncbi_gene_id) — the same stable-ID flow as the
         human_canonical cohort
      3. Filter to UniProt accs not already in the candidate set
      4. Append as virtual Candidate rows with ``selection_reason='paralog'``
         and ``triage_verdict=None``

    The returned list is the augmented set; the original ``candidates`` is
    NOT mutated. ``parse_cohort_to_jsonl`` looks up each new entry via
    ``candidate_by_acc[paralog_uniprot]`` and stamps the paralog's OWN
    HGNC ID (not the human's), so topology_public has a row per protein.
    """
    import os
    import httpx

    existing_uniprots = {c.uniprot_acc for c in candidates}
    existing_hgnc_ids = {c.hgnc_id for c in candidates}

    # Read all distinct paralog Ensembl genes from the BioMart CSV.
    paralog_ensgs: set[str] = set()
    if not paralog_csv.exists():
        logger.warning("paralog CSV missing at %s; no expansion possible", paralog_csv)
        return candidates
    with paralog_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            ensg = (row.get("paralog_ensembl_gene") or "").strip().upper()
            if ensg:
                paralog_ensgs.add(ensg)
    if not paralog_ensgs:
        return candidates
    logger.info(
        "paralog expansion: %d distinct paralog Ensembl genes in BioMart CSV",
        len(paralog_ensgs),
    )

    # Bulk-resolve via gene_identifier (D1, private agents DB).
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    if not (account and token and db):
        logger.warning(
            "D1 env missing → paralog expansion skipped (rows will land with NULL ecd_pct_identity for non-candidate paralogs)"
        )
        return candidates
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query"
    ensg_list = sorted(paralog_ensgs)
    gi_by_ensg: dict[str, dict[str, Any]] = {}
    chunk_size = 500
    with httpx.Client(timeout=120) as client:
        for start in range(0, len(ensg_list), chunk_size):
            chunk = ensg_list[start : start + chunk_size]
            quoted = ",".join(f"'{e}'" for e in chunk)
            sql = (
                "SELECT hgnc_id, hgnc_symbol, cohort_symbol, uniprot_acc, "
                "ncbi_gene_id, ensembl_gene FROM gene_identifier "
                f"WHERE ensembl_gene IN ({quoted}) AND uniprot_acc IS NOT NULL "
                "AND uniprot_acc != ''"
            )
            resp = client.post(
                url, json={"sql": sql}, headers={"Authorization": f"Bearer {token}"}
            )
            body = resp.json()
            if not body.get("success"):
                logger.warning("gene_identifier expansion query failed: %s", body)
                continue
            result = body.get("result") or []
            if isinstance(result, dict):
                result = [result]
            for r in result:
                for row in r.get("results") or []:
                    ensg = (row.get("ensembl_gene") or "").strip().upper()
                    if ensg:
                        gi_by_ensg[ensg] = row

    # Build virtual Candidate rows for paralogs not already in the set.
    new_candidates: list[Candidate] = []
    seen_uniprots: set[str] = set()
    n_already_in_set = 0
    n_no_gi_entry = 0
    for ensg in ensg_list:
        gi = gi_by_ensg.get(ensg)
        if gi is None:
            n_no_gi_entry += 1
            continue
        hgnc_id = (gi.get("hgnc_id") or "").strip()
        uniprot_acc = (gi.get("uniprot_acc") or "").strip().upper()
        if not hgnc_id or not uniprot_acc:
            n_no_gi_entry += 1
            continue
        if uniprot_acc in existing_uniprots or hgnc_id in existing_hgnc_ids:
            n_already_in_set += 1
            continue
        if uniprot_acc in seen_uniprots:
            continue
        seen_uniprots.add(uniprot_acc)
        ncbi_raw = gi.get("ncbi_gene_id")
        new_candidates.append(
            Candidate(
                hgnc_id=hgnc_id,
                cohort_symbol=(gi.get("cohort_symbol") or gi.get("hgnc_symbol") or ""),
                uniprot_acc=uniprot_acc,
                ensembl_gene=(gi.get("ensembl_gene") or None) or None,
                ncbi_gene_id=(int(ncbi_raw) if ncbi_raw else None),
                selection_reason="paralog",
                triage_verdict=None,
            )
        )
    logger.info(
        "paralog expansion: %d new candidates added (skipped %d already in set, "
        "%d no gene_identifier entry)",
        len(new_candidates), n_already_in_set, n_no_gi_entry,
    )
    return list(candidates) + new_candidates


def maybe_pull_paralogs(*, override_ensembl_ids: list[str]) -> Path | None:
    """Pull paralogs from BioMart, reusing the cached CSV only if it covers
    all requested Ensembl IDs.

    Coverage check: read the cached CSV's ``query_ensembl_gene`` column;
    if every override_ensembl_id appears as a query in that CSV, the
    cache is valid (same or bigger input set). Otherwise wipe the
    cached output dir and re-pull fresh. Prevents the "cached from a
    smaller dry-run input" failure mode where the orchestrator would
    happily reuse a 3-protein paralog CSV for a 6,415-protein sweep.

    The downstream ``ensembl_compara_paralogs.download_main`` understands
    ``--override-ensembl-ids`` and bypasses the HGNC TSV path entirely.
    """
    if COMPARA_PARALOG_BY_GENE_CSV.exists() and override_ensembl_ids:
        cached_ensgs: set[str] = set()
        try:
            with COMPARA_PARALOG_BY_GENE_CSV.open() as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ensg = (row.get("query_ensembl_gene") or "").strip().upper()
                    if ensg:
                        cached_ensgs.add(ensg)
        except OSError as exc:
            logger.warning("could not read cached paralog CSV: %s", exc)
            cached_ensgs = set()
        wanted = {e.upper() for e in override_ensembl_ids if e}
        missing = wanted - cached_ensgs
        if not missing:
            logger.info(
                "paralog CSV cache valid (%d / %d requested ENSGs present); reusing",
                len(wanted & cached_ensgs), len(wanted),
            )
            return COMPARA_PARALOG_BY_GENE_CSV
        logger.info(
            "paralog CSV cache STALE — %d of %d requested ENSGs missing "
            "(e.g. %s); wiping and re-pulling",
            len(missing), len(wanted), sorted(missing)[:5],
        )
        import shutil
        shutil.rmtree(COMPARA_PARALOG_BY_GENE_CSV.parent)
    elif COMPARA_PARALOG_BY_GENE_CSV.exists():
        # No override list passed → trust the cache.
        return COMPARA_PARALOG_BY_GENE_CSV

    logger.info("running ensembl_compara_paralogs download (%d Ensembl IDs)",
                len(override_ensembl_ids))
    from accessible_surfaceome.sources.ensembl_compara_paralogs import download_main
    args: list[str] = []
    if override_ensembl_ids:
        args += ["--override-ensembl-ids", ",".join(override_ensembl_ids)]
    download_main(args)
    if not COMPARA_PARALOG_BY_GENE_CSV.exists():
        logger.warning("paralog CSV still missing after download attempt")
        return None
    return COMPARA_PARALOG_BY_GENE_CSV


def _load_gene_identifier_for_paralog_lookup() -> dict[str, dict[str, Any]]:
    """Index ``gene_identifier`` by Ensembl gene for paralog-side lookup.

    Both sides of a Compara paralog pair come back keyed on Ensembl gene IDs;
    we need to map those to (hgnc_id, uniprot_acc) to (a) stamp paralog_hgnc_id
    on every output row and (b) find the paralog's DeepTMHMM topology via
    its UniProt accession.
    """
    import os
    import httpx

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    if not (account and token and db):
        logger.warning(
            "gene_identifier lookup unavailable (missing D1 env vars); "
            "paralog_hgnc_id columns will be NULL"
        )
        return {}
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query"
    out: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            url,
            json={
                "sql": "SELECT hgnc_id, hgnc_symbol, uniprot_acc, ensembl_gene, "
                       "ncbi_gene_id FROM gene_identifier "
                       "WHERE ensembl_gene IS NOT NULL AND ensembl_gene != ''",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        if not body.get("success"):
            logger.warning("gene_identifier query failed: %s", body)
            return {}
        result = body.get("result") or []
        if isinstance(result, dict):
            result = [result]
        for r in result:
            for row in r.get("results") or []:
                ensg = (row.get("ensembl_gene") or "").strip().upper()
                if ensg:
                    out[ensg] = row
    return out


def compute_paralog_records(
    *,
    paralog_csv: Path,
    canonical_topology_jsonl: Path,
    paralog_version: str,
    compara_version: str,
) -> list[dict[str, Any]]:
    """Compute ECD identity for every (human, paralog) pair in the CSV.

    Pipeline (HGNC-keyed end to end):

      * The Compara CSV gives us paralog Ensembl gene IDs (the BioMart key).
      * ``gene_identifier`` resolves each Ensembl ID → (hgnc_id, uniprot_acc).
      * Topology lookup goes through ``topology_records.jsonl`` indexed by
        UniProt accession (stable across resolver versions).
      * Output rows carry both ``human_hgnc_id`` and ``paralog_hgnc_id`` —
        the stable join keys for the public mirror.

    For v1 we DON'T re-run DeepTMHMM on paralogs that aren't in our candidate
    universe — ``ecd_pct_identity`` is NULL for those and consumers rank
    by ``biomart_percent_identity`` instead. The orchestrator assumes the
    cohort sweep has already covered the universe's canonical isoforms.
    """
    from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

    # 1. Topology index — keyed by base UniProt accession (the stable ID,
    #    not gene_symbol, since the resolver fix is the whole point of this PR).
    topo_by_acc: dict[str, dict[str, Any]] = {}
    with canonical_topology_jsonl.open() as f:
        for line in f:
            rec = json.loads(line)
            topo_by_acc[rec["uniprot_accession"]] = rec

    # 2. gene_identifier index — keyed by Ensembl gene (the join key on the
    #    BioMart side). Lets us turn paralog_ensembl_gene → hgnc_id +
    #    uniprot_acc without re-resolving from symbol.
    gi_by_ensg = _load_gene_identifier_for_paralog_lookup()
    logger.info(
        "gene_identifier loaded for paralog ENSG-resolution: %d rows", len(gi_by_ensg)
    )

    out: list[dict[str, Any]] = []
    by_human_gene: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with paralog_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Compara CSV (output of ensembl_compara_paralogs.download_main)
            human_ensg = (row.get("query_ensembl_gene") or "").strip().upper()
            paralog_ensg = (row.get("paralog_ensembl_gene") or "").strip().upper()
            family_id = (row.get("family_id") or "").strip()
            paralogy_type = (row.get("paralogy_type") or "").strip()
            biomart_pct_raw = (row.get("percent_identity") or "").strip()
            biomart_pct = float(biomart_pct_raw) if biomart_pct_raw else None
            is_high_conf = int((row.get("is_high_confidence") or "0").strip() or "0")

            # Stable-ID lookup via gene_identifier (HGNC-keyed). Symbol
            # fallbacks to the Compara CSV were removed after PR #30 landed
            # — if gene_identifier doesn't resolve an Ensembl gene, the row
            # ends up with NULL stable IDs and gets dropped downstream by
            # the upload script. That's correct: pre-PR-30 symbol fallbacks
            # were a known mis-resolution vector.
            human_gi = gi_by_ensg.get(human_ensg) or {}
            paralog_gi = gi_by_ensg.get(paralog_ensg) or {}

            human_hgnc_id = (human_gi.get("hgnc_id") or "").strip() or None
            human_uniprot = (human_gi.get("uniprot_acc") or "").strip().upper() or None
            human_sym = (human_gi.get("hgnc_symbol") or "").strip() or None

            paralog_hgnc_id = (paralog_gi.get("hgnc_id") or "").strip() or None
            paralog_uniprot = (paralog_gi.get("uniprot_acc") or "").strip().upper() or None
            paralog_sym = (paralog_gi.get("hgnc_symbol") or "").strip() or None

            human_record = topo_by_acc.get(human_uniprot) if human_uniprot else None
            paralog_record = (
                topo_by_acc.get(paralog_uniprot) if paralog_uniprot else None
            )

            ecd_result = None
            if human_record is not None and paralog_record is not None:
                ecd_result = compute_ecd_identity(
                    human_topology=human_record["per_residue_topology"],
                    human_sequence=human_record["sequence"],
                    paralog_topology=paralog_record["per_residue_topology"],
                    paralog_sequence=paralog_record["sequence"],
                )

            row_out = {
                "paralog_version": paralog_version,
                "human_hgnc_id": human_hgnc_id,
                "human_ensembl_gene": human_ensg,
                "human_uniprot_acc": human_uniprot or None,
                "human_gene_symbol": human_sym or None,
                "paralog_hgnc_id": paralog_hgnc_id,
                "paralog_ensembl_gene": paralog_ensg,
                "paralog_uniprot_acc": paralog_uniprot or None,
                "paralog_gene_symbol": paralog_sym or None,
                "family_id": family_id or None,
                "biomart_percent_identity": biomart_pct,
                "ecd_pct_identity": ecd_result.ecd_pct_identity if ecd_result else None,
                "n_ecd_loops_compared": ecd_result.n_ecd_loops_compared if ecd_result else 0,
                "paralogy_type": paralogy_type or None,
                "is_high_confidence": is_high_conf,
                "compara_version": compara_version,
            }
            out.append(row_out)
            by_human_gene[human_ensg].append(row_out)

    # Assign rank_by_ecd_identity per human gene (1 = closest; NULLs last).
    for human_ensg, group in by_human_gene.items():
        ranked = sorted(
            group,
            key=lambda r: (
                r["ecd_pct_identity"] is None,  # False (has value) sorts first
                -(r["ecd_pct_identity"] or 0.0),
            ),
        )
        for i, r in enumerate(ranked, 1):
            r["rank_by_ecd_identity"] = i if r["ecd_pct_identity"] is not None else None
    return out


def compute_ortholog_ecd_records(
    *,
    candidates: list[Candidate],
    cohort_jsonl_paths: dict[str, Path],
    ortholog_human_hgnc_maps: dict[str, dict[str, str]],
    ortholog_ecd_version: str,
    compara_release: str,
) -> list[dict[str, Any]]:
    """Compute per-loop BLOSUM62 ECD identity between each human canonical
    and its mouse/cyno one2one ortholog.

    Mirrors ``compute_paralog_records`` — same per-loop alignment algorithm,
    same length-weighted aggregation. Input here is the cross-species join
    rather than the within-species paralog pairs:

      * human topology+sequence from cohort_jsonl_paths['human_canonical']
        (keyed by uniprot_acc)
      * ortholog topology+sequence from cohort_jsonl_paths[<ortholog_cohort>]
        (keyed by uniprot_acc)
      * ortholog→human mapping from ``ortholog_human_hgnc_maps`` (the
        same dict the parser uses to stamp hgnc_id on ortholog topology rows)

    Returns one row per (human_hgnc_id, species, ortholog_uniprot_acc). The
    biomart_percent_identity column is left NULL here — that value lives
    in the existing ``compara_ortholog`` row and can be joined on
    (species, human_ensembl_gene, ortholog_ensembl_gene) at query time.
    Storing it here would duplicate Compara state without adding info.
    """
    from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

    # Build human topology index keyed by uniprot_acc.
    human_topo: dict[str, dict[str, Any]] = {}
    human_jsonl = cohort_jsonl_paths.get("human_canonical")
    if human_jsonl is None or not human_jsonl.exists():
        logger.warning("human_canonical JSONL missing — ortholog ECD = no rows")
        return []
    # Also index by hgnc_id for the human-side metadata (uniprot_acc, ensembl_gene)
    human_topo_by_hgnc: dict[str, dict[str, Any]] = {}
    with human_jsonl.open() as f:
        for line in f:
            rec = json.loads(line)
            human_topo[rec["uniprot_accession"]] = rec
            if rec.get("hgnc_id"):
                human_topo_by_hgnc[rec["hgnc_id"]] = rec

    # candidate hgnc_id → ensembl_gene + uniprot_acc (for output denormalization)
    cand_by_hgnc: dict[str, Candidate] = {c.hgnc_id: c for c in candidates}

    out: list[dict[str, Any]] = []
    for ortholog_cohort, hgnc_map in ortholog_human_hgnc_maps.items():
        if not hgnc_map:
            continue
        species = SPECIES_BY_COHORT[ortholog_cohort]  # 'mouse' or 'cynomolgus'
        ortholog_jsonl = cohort_jsonl_paths.get(ortholog_cohort)
        if ortholog_jsonl is None or not ortholog_jsonl.exists():
            logger.warning("%s JSONL missing — skipping for ECD", ortholog_cohort)
            continue
        # Build ortholog topology index keyed by uniprot_acc.
        ortho_topo: dict[str, dict[str, Any]] = {}
        with ortholog_jsonl.open() as f:
            for line in f:
                rec = json.loads(line)
                ortho_topo[rec["uniprot_accession"]] = rec

        n_with_ecd = 0
        n_no_topology = 0
        for ortho_uniprot, human_hgnc in hgnc_map.items():
            ortho_rec = ortho_topo.get(ortho_uniprot)
            human_rec = human_topo_by_hgnc.get(human_hgnc)
            cand = cand_by_hgnc.get(human_hgnc)

            ecd_pct = None
            n_loops = 0
            if ortho_rec is not None and human_rec is not None:
                result = compute_ecd_identity(
                    human_topology=human_rec["per_residue_topology"],
                    human_sequence=human_rec["sequence"],
                    paralog_topology=ortho_rec["per_residue_topology"],
                    paralog_sequence=ortho_rec["sequence"],
                )
                ecd_pct = result.ecd_pct_identity
                n_loops = result.n_ecd_loops_compared
                if ecd_pct is not None:
                    n_with_ecd += 1
            else:
                n_no_topology += 1

            out.append({
                "ortholog_ecd_version": ortholog_ecd_version,
                "human_hgnc_id": human_hgnc,
                "human_uniprot_acc": (cand.uniprot_acc if cand else None),
                "human_ensembl_gene": (cand.ensembl_gene if cand else None),
                "human_gene_symbol": (cand.cohort_symbol if cand else None),
                "species": species,
                "ortholog_uniprot_acc": ortho_uniprot,
                "ortholog_ensembl_gene": (ortho_rec or {}).get("uniprot_entry_name"),
                "ortholog_gene_symbol": (ortho_rec or {}).get("uniprot_entry_name"),
                "biomart_percent_identity": None,  # joined from compara_ortholog at query time
                "ecd_pct_identity": ecd_pct,
                "n_ecd_loops_compared": n_loops,
                "compara_release": compara_release,
            })
        logger.info(
            "ortholog ECD %s: %d rows, %d with ECD, %d missing topology",
            ortholog_cohort, len(hgnc_map), n_with_ecd, n_no_topology,
        )
    return out


def _sha256_of_file(p: Path, chunk_size: int = 65536) -> str | None:
    """Return SHA256 hex digest of a file, or None if it doesn't exist."""
    import hashlib

    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _capture_git_provenance() -> dict[str, Any]:
    """Capture git SHA, branch, and dirty-tree state for the manifest."""
    import subprocess

    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=15
            ).stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return ""

    sha = _run(["git", "rev-parse", "HEAD"])
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = bool(_run(["git", "status", "--porcelain"]))
    upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    return {
        "sha": sha,
        "branch": branch,
        "upstream": upstream,
        "dirty": dirty,
        "remote_url": _run(["git", "config", "--get", "remote.origin.url"]),
    }


def _capture_library_versions() -> dict[str, str]:
    """Versions of key external libraries embedded in the pipeline."""
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for mod_name in ("Bio", "httpx", "biopython"):
        try:
            import importlib

            mod = importlib.import_module(mod_name)
            versions[mod_name] = getattr(mod, "__version__", "")
        except Exception:  # noqa: BLE001
            pass
    return versions


def _query_resolver_versions_in_cohort(candidates: list[Candidate]) -> dict[str, int]:
    """Aggregate resolver_version counts across the gene_identifier rows that
    backed this candidate set. Captures which resolver SHA(s) the pipeline
    consumed — if the cohort spans multiple resolver versions (e.g. after a
    partial backfill), this row count surfaces it.
    """
    import os
    import httpx
    from collections import Counter

    hgnc_ids = [c.hgnc_id for c in candidates if c.hgnc_id]
    if not hgnc_ids:
        return {}

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    if not (account and token and db):
        return {}
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{db}/query"
    counter: Counter[str] = Counter()
    chunk_size = 500
    with httpx.Client(timeout=120) as client:
        for start in range(0, len(hgnc_ids), chunk_size):
            chunk = hgnc_ids[start : start + chunk_size]
            quoted = ",".join(f"'{h}'" for h in chunk)
            sql = (
                "SELECT resolver_version, COUNT(*) AS n FROM gene_identifier "
                f"WHERE hgnc_id IN ({quoted}) GROUP BY resolver_version"
            )
            resp = client.post(
                url, json={"sql": sql}, headers={"Authorization": f"Bearer {token}"}
            )
            body = resp.json()
            if not body.get("success"):
                continue
            result = body.get("result") or []
            if isinstance(result, dict):
                result = [result]
            for r in result:
                for row in r.get("results") or []:
                    rv = (row.get("resolver_version") or "").strip()
                    counter[rv] += int(row.get("n") or 0)
    return dict(counter)


def build_run_manifest(
    *,
    args: argparse.Namespace,
    candidate_set_path: Path,
    candidates: list[Candidate],
    cohort_jsonl_paths: dict[str, Path],
    paralog_csv: Path | None,
    paralog_jsonl: Path | None,
    ortholog_ecd_jsonl: Path | None,
    ortholog_human_hgnc_maps: dict[str, dict[str, str]],
    run_dir: Path,
    started_at: datetime,
) -> dict[str, Any]:
    """Build the cross-cutting provenance manifest for this sweep run.

    Captures every piece of state a future reader needs to reproduce the
    sweep: git SHA the code ran from, gene_identifier resolver versions,
    Compara release, BioMart/UniProt source URLs, candidate set hash,
    per-cohort JSONL counts + hashes, library versions, taxon IDs,
    cleanup setting. Mirrored into ``topology_release.notes`` so the
    manifest is queryable from D1.
    """
    git = _capture_git_provenance()
    versions = _capture_library_versions()
    resolver_versions = _query_resolver_versions_in_cohort(candidates)

    by_reason: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    n_needs_review = 0
    for c in candidates:
        by_reason[c.selection_reason] = by_reason.get(c.selection_reason, 0) + 1
        key = c.triage_verdict or "_no_triage"
        by_verdict[key] = by_verdict.get(key, 0) + 1

    cohort_summary: dict[str, dict[str, Any]] = {}
    for cohort, jsonl_path in cohort_jsonl_paths.items():
        n = 0
        if jsonl_path.exists():
            with jsonl_path.open() as f:
                n = sum(1 for _ in f)
        cohort_summary[cohort] = {
            "jsonl_path": str(jsonl_path.relative_to(REPO_ROOT)),
            "jsonl_sha256": _sha256_of_file(jsonl_path),
            "n_rows": n,
        }

    paralog_summary: dict[str, Any] = {
        "biomart_csv": (
            str(paralog_csv.relative_to(REPO_ROOT)) if paralog_csv else None
        ),
        "biomart_csv_sha256": _sha256_of_file(paralog_csv) if paralog_csv else None,
        "ecd_jsonl": (
            str(paralog_jsonl.relative_to(REPO_ROOT)) if paralog_jsonl else None
        ),
        "ecd_jsonl_sha256": _sha256_of_file(paralog_jsonl) if paralog_jsonl else None,
        "top_n_per_gene_cap": 50,  # default in ensembl_compara_paralogs.DEFAULT_TOP_N_PER_GENE
    }
    if paralog_jsonl and paralog_jsonl.exists():
        import json as _json

        with paralog_jsonl.open() as f:
            rows = [_json.loads(line) for line in f if line.strip()]
            paralog_summary["n_pairs"] = len(rows)
            paralog_summary["n_with_ecd"] = sum(
                1 for r in rows if r.get("ecd_pct_identity") is not None
            )

    ortholog_summary: dict[str, Any] = {
        "ecd_jsonl": (
            str(ortholog_ecd_jsonl.relative_to(REPO_ROOT))
            if ortholog_ecd_jsonl
            else None
        ),
        "ecd_jsonl_sha256": (
            _sha256_of_file(ortholog_ecd_jsonl) if ortholog_ecd_jsonl else None
        ),
        "by_cohort": {},
    }
    for cohort, hgnc_map in ortholog_human_hgnc_maps.items():
        taxon = ORTHOLOG_SPECIES[cohort][1]
        ortholog_summary["by_cohort"][cohort] = {
            "n_resolved_orthologs": len(hgnc_map),
            "taxon_id": taxon,
        }

    return {
        "topology_version": args.topology_version,
        "paralog_version": args.paralog_version or f"paralog_{args.topology_version}",
        "ortholog_ecd_version": f"orthologecd_{args.topology_version}",
        "run_started_at": started_at.isoformat(),
        "run_ended_at": datetime.now(UTC).isoformat(),
        "wall_time_seconds": (datetime.now(UTC) - started_at).total_seconds(),
        "git": git,
        "library_versions": versions,
        "deeptmhmm": {
            "tool_version": DEEPTMHMM_TOOL_VERSION,
            "root": os.environ.get("DEEPTMHMM_ROOT", ""),
            "attribution": "DeepTMHMM 1.0.24 (DTU)",
            "license_url": "https://dtu.biolib.com/DeepTMHMM/",
            "max_sequence_length": DEEPTMHMM_MAX_SEQUENCE_LENGTH,
        },
        "compara": {
            "release": args.compara_version,
            "biomart_url": "https://www.ensembl.org/biomart/martservice",
        },
        "uniprot": {
            "rest_url": "https://rest.uniprot.org/uniprotkb/",
        },
        "candidate_set": {
            "tsv_path": str(candidate_set_path.relative_to(REPO_ROOT)),
            "tsv_sha256": _sha256_of_file(candidate_set_path),
            "n_candidates_before_paralog_expansion": "<see candidates_expanded_with_paralogs event>",
            "n_candidates_total": len(candidates),
            "by_selection_reason": by_reason,
            "by_triage_verdict": by_verdict,
            "n_needs_review": n_needs_review,
        },
        "resolver": {
            "gene_identifier_resolver_versions": resolver_versions,
            "note": (
                "Counts of distinct resolver_version values across the "
                "gene_identifier rows that backed this candidate set. "
                "Single value = uniform resolver; multiple = cohort spans "
                "a resolver upgrade and you may want to re-resolve."
            ),
        },
        "cohorts": cohort_summary,
        "paralog": paralog_summary,
        "orthologs": ortholog_summary,
        "run_dir": str(run_dir.relative_to(REPO_ROOT)),
        "events_log": str((run_dir.parent / f"topology_run_{args.topology_version}" / "events.jsonl").relative_to(REPO_ROOT)),
        "cleanup_after_upload": args.cleanup_after_upload,
    }


def write_ortholog_ecd_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def write_paralog_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topology-version", required=True)
    ap.add_argument(
        "--cohorts",
        default="human_canonical,human_isoforms,mouse_ortholog,cyno_ortholog",
        help="Comma-separated cohort list",
    )
    ap.add_argument(
        "--candidate-set",
        type=Path,
        default=None,
        help="Path to candidate_accessions.tsv. Defaults to "
             "data/processed/topology_run_<topology_version>/candidate_accessions.tsv",
    )
    ap.add_argument("--max-workers", type=int, default=None,
                    help="ProcessPool workers for DeepTMHMM (default: min(cpu, 8))")
    ap.add_argument("--fetch-workers", type=int, default=8,
                    help="Threads for UniProt FASTA fetch")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument(
        "--skip-paralogs",
        action="store_true",
        help="Skip paralog pull + ECD identity stage (faster dry runs)",
    )
    ap.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip D1 upload (just produce JSONL on disk)",
    )
    ap.add_argument(
        "--deeptmhmm-root",
        type=Path,
        default=None,
        help="Override the DeepTMHMM install root (parent of "
             "DeepTMHMM-Academic-License-v1.0/predict.py and the .venv-deeptmhmm "
             "venv). Falls back to DEEPTMHMM_ROOT env var, then to the default "
             "in src/accessible_surfaceome/sources/deeptmhmm.py.",
    )
    ap.add_argument(
        "--paralog-version",
        default=None,
        help="paralog_version stamp; defaults to paralog_<topology_version>",
    )
    ap.add_argument("--compara-version", default=DEFAULT_COMPARA_VERSION)
    ap.add_argument(
        "--cleanup-after-upload",
        action="store_true",
        help="After D1 upload completes, delete intermediate batch directories "
             "(embeddings, plot.png, TMRs.gff3, deeptmhmm_results.md, _inputs/) "
             "but keep predicted_topologies.3line as provenance. Keeps disk "
             "usage to ~100 MB instead of ~2 GB peak.",
    )
    args = ap.parse_args()

    cohorts = [c.strip() for c in args.cohorts.split(",") if c.strip()]
    bad = [c for c in cohorts if c not in VALID_COHORTS]
    if bad:
        raise SystemExit(f"unknown cohorts: {bad}; valid={sorted(VALID_COHORTS)}")

    if args.max_workers is None:
        args.max_workers = min(os.cpu_count() or 6, 8)

    # Promote --deeptmhmm-root to the env var so ProcessPool workers inherit it.
    if args.deeptmhmm_root is not None:
        os.environ["DEEPTMHMM_ROOT"] = str(args.deeptmhmm_root.expanduser().resolve())
        logger.info("DEEPTMHMM_ROOT set to %s", os.environ["DEEPTMHMM_ROOT"])

    # Resolve paths
    candidate_set_path = args.candidate_set or (
        REPO_ROOT / "data" / "processed" / f"topology_run_{args.topology_version}"
        / "candidate_accessions.tsv"
    )
    run_dir = (
        REPO_ROOT / "data" / "external" / f"deeptmhmm_topology_run_{args.topology_version}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl_root = (
        REPO_ROOT / "data" / "processed" / f"topology_run_{args.topology_version}"
    )
    jsonl_root.mkdir(parents=True, exist_ok=True)

    events_log = jsonl_root / "events.jsonl"
    def event(stage: str, **kv: Any) -> None:
        line = {"ts": datetime.now(UTC).isoformat(), "stage": stage, **kv}
        with events_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        logger.info("[%s] %s", stage, ", ".join(f"{k}={v}" for k, v in kv.items()))

    run_started_at = datetime.now(UTC)
    # Record git provenance at start so a Ctrl-C'd run still leaves an audit trail.
    _git_provenance = _capture_git_provenance()
    event("start", topology_version=args.topology_version, cohorts=cohorts,
          max_workers=args.max_workers, git_sha=_git_provenance.get("sha"),
          git_branch=_git_provenance.get("branch"),
          git_dirty=_git_provenance.get("dirty"))

    candidates = load_candidate_set(candidate_set_path)
    event("candidate_set_loaded", n=len(candidates),
          source=str(candidate_set_path.relative_to(REPO_ROOT)))

    # ----- Stage 1.5: paralog BioMart pull + candidate expansion (Option A) -----
    # Pull paralogs BEFORE the cohort run so the candidate list can be
    # augmented with paralog UniProts not already in the surface-DB / triage
    # union. Every distinct paralog then gets DeepTMHMM topology, which means
    # ECD identity is computable for every paralog pair downstream.
    paralog_csv: Path | None = None
    if not args.skip_paralogs:
        override_ensembl_ids = [c.ensembl_gene for c in candidates if c.ensembl_gene]
        logger.info(
            "paralog pull: %d candidates → %d Ensembl gene IDs going to BioMart",
            len(candidates), len(override_ensembl_ids),
        )
        paralog_csv = maybe_pull_paralogs(override_ensembl_ids=override_ensembl_ids)
        if paralog_csv is not None:
            n_before = len(candidates)
            candidates = _expand_candidates_with_paralogs(candidates, paralog_csv)
            event(
                "candidates_expanded_with_paralogs",
                n_before=n_before,
                n_after=len(candidates),
                n_paralog_added=len(candidates) - n_before,
            )

    candidate_by_acc = {c.uniprot_acc: c for c in candidates}

    # ----- Stage 2: Per-cohort accession lists -----
    # cohort_accessions[cohort] is the list of UniProt accessions to feed to
    # DeepTMHMM for that cohort. Built differently per cohort source:
    #   * human_canonical → candidate set's resolved uniprot_acc
    #   * human_isoforms → existing legacy .3line set (M1 cohort)
    #   * mouse/cyno_ortholog → compara_ortholog (D1) + UniProt-by-Ensembl resolution
    cohort_accessions: dict[str, list[str]] = {}
    # ortholog_human_hgnc_by_acc[cohort][ortholog_uniprot_acc] = human_hgnc_id.
    # Used by parse_cohort_to_jsonl to stamp the human HGNC ID onto each
    # ortholog topology row so consumers can join back to gene_identifier.
    ortholog_human_hgnc_maps: dict[str, dict[str, str]] = {}
    if "human_canonical" in cohorts:
        cohort_accessions["human_canonical"] = [c.uniprot_acc for c in candidates]
    if "human_isoforms" in cohorts:
        # For v1 we use the existing human_isoforms cohort FASTA inputs
        # already produced under data/external/deeptmhmm_surfaceome_predictions/
        # human_isoforms_from_afdb_non_hla/. Resolving fresh isoforms for
        # arbitrary candidates is out of scope for this orchestrator.
        cohort_accessions["human_isoforms"] = []

    for ortholog_cohort in ("mouse_ortholog", "cyno_ortholog"):
        if ortholog_cohort not in cohorts:
            continue
        targets = _resolve_ortholog_targets_from_d1(
            candidates, species_key=ortholog_cohort
        )
        if not targets:
            cohort_accessions[ortholog_cohort] = []
            ortholog_human_hgnc_maps[ortholog_cohort] = {}
            continue
        # Resolve mouse/cyno Ensembl IDs → UniProt accs (cached on disk so
        # subsequent runs don't re-hit UniProt). Cache is shared across
        # cohorts because keying is (ensembl_gene, taxon_id).
        cache_path = REPO_ROOT / "data" / "external" / "ortholog_uniprot_resolution.tsv"
        ensg_to_acc = _resolve_ortholog_uniprots(
            targets, cache_path=cache_path, max_workers=4
        )
        # Build ortholog_uniprot_acc → human_hgnc_id map (the stable
        # join key for downstream topology_public consumers).
        ortholog_human_hgnc: dict[str, str] = {}
        for t in targets:
            acc = ensg_to_acc.get(t.ortholog_ensembl_gene, "")
            if acc and acc not in ortholog_human_hgnc:
                # First-match wins on collisions (rare; usually a single
                # mouse UniProt acc maps back to one human HGNC ID).
                ortholog_human_hgnc[acc] = t.human_hgnc_id
        cohort_accessions[ortholog_cohort] = sorted(ortholog_human_hgnc)
        ortholog_human_hgnc_maps[ortholog_cohort] = ortholog_human_hgnc
        logger.info(
            "  %s: %d targets → %d resolved UniProt accs (cache hit + UniProt REST)",
            ortholog_cohort, len(targets), len(ortholog_human_hgnc),
        )

    # ----- Stage 3: Fetch FASTAs (human_canonical only for v1) -----
    # Ortholog and isoform FASTA-set construction reuses the existing
    # ensembl_compara + download_main scaffolding rather than reimplementing
    # the UniProt isoform lookup here. The orchestrator's primary job is to
    # extend human_canonical coverage to the full candidate universe.
    canonical_fasta_paths: dict[str, Path] = {}
    if "human_canonical" in cohorts:
        canonical_fasta_paths = fetch_sequences_for_accessions(
            cohort_accessions["human_canonical"],
            cache_dir=SEQUENCE_CACHE_DIR,
            max_workers=args.fetch_workers,
        )
        event("fetch_complete", cohort="human_canonical",
              n_fetched=len(canonical_fasta_paths))

    # Ortholog FASTAs: fetch up front so they're cached for DeepTMHMM. Each
    # call returns {uniprot_acc: cached_fasta_path}. Empty when the cohort
    # wasn't requested or compara_ortholog produced no targets.
    ortholog_fasta_paths_by_cohort: dict[str, dict[str, Path]] = {}
    for ortholog_cohort in ("mouse_ortholog", "cyno_ortholog"):
        if ortholog_cohort not in cohorts or not cohort_accessions.get(ortholog_cohort):
            continue
        paths = fetch_sequences_for_accessions(
            cohort_accessions[ortholog_cohort],
            cache_dir=SEQUENCE_CACHE_DIR,
            max_workers=args.fetch_workers,
        )
        ortholog_fasta_paths_by_cohort[ortholog_cohort] = paths
        event(
            "fetch_complete",
            cohort=ortholog_cohort,
            n_fetched=len(paths),
            n_requested=len(cohort_accessions[ortholog_cohort]),
        )

    # ----- Stage 4: DeepTMHMM run + parse, per cohort -----
    cohort_jsonl_paths: dict[str, Path] = {}
    cohort_map_legacy = {
        "human_canonical": "human_canonical_non_hla",
        "human_isoforms": "human_isoforms_from_afdb_non_hla",
        "mouse_ortholog": "mouse_ortholog_one2one_highconf_non_hla",
        "cyno_ortholog": "cyno_ortholog_one2one_highconf_non_hla",
    }
    for cohort in cohorts:
        cohort_dir = run_dir / cohort
        cohort_dir.mkdir(parents=True, exist_ok=True)
        legacy_3line = (
            REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
            / cohort_map_legacy[cohort] / "predicted_topologies.3line"
        )
        already_predicted: set[str] = set()
        if legacy_3line.exists():
            try:
                for rec in parse_3line(legacy_3line):
                    already_predicted.add(rec["uniprot_accession"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("could not pre-scan legacy .3line %s: %s", cohort, exc)

        if cohort == "human_canonical":
            target_fasta_paths = canonical_fasta_paths
        elif cohort in ortholog_fasta_paths_by_cohort:
            target_fasta_paths = ortholog_fasta_paths_by_cohort[cohort]
        else:
            # human_isoforms or an ortholog cohort with no resolved targets:
            # legacy-only path.
            target_fasta_paths = {}

        gap_fasta_paths = [
            p for acc, p in target_fasta_paths.items() if acc not in already_predicted
        ]
        logger.info(
            "  %s: %d FASTAs in scope, %d already in legacy .3line, "
            "%d going to DeepTMHMM",
            cohort, len(target_fasta_paths),
            len(target_fasta_paths) - len(gap_fasta_paths),
            len(gap_fasta_paths),
        )
        output_3line_paths: list[Path] = []
        if gap_fasta_paths:
            output_3line_paths, skipped = run_cohort_deeptmhmm(
                cohort=cohort,
                cohort_dir=cohort_dir,
                fasta_paths=gap_fasta_paths,
                max_workers=args.max_workers,
                batch_size=args.batch_size,
            )
            event(
                "deeptmhmm_done", cohort=cohort,
                n_batches=len(output_3line_paths),
                n_skipped_too_long=len(skipped),
                n_reused_from_legacy=len(target_fasta_paths) - len(gap_fasta_paths),
            )
        # Always include the legacy .3line so the JSONL ends with full coverage
        # of any prior predictions in addition to the fresh batches.
        if legacy_3line.exists():
            output_3line_paths.append(legacy_3line)
            if not gap_fasta_paths:
                event("legacy_reuse", cohort=cohort,
                      source=str(legacy_3line.relative_to(REPO_ROOT)))
        if not output_3line_paths:
            logger.warning("  %s: no .3line outputs (no fresh runs + no legacy) → 0 rows",
                           cohort)
            continue

        jsonl = parse_cohort_to_jsonl(
            cohort=cohort,
            output_3line_paths=output_3line_paths,
            cohort_dir=jsonl_root / cohort,
            topology_version=args.topology_version,
            candidate_by_acc=candidate_by_acc,
            ortholog_human_hgnc_by_acc=(
                ortholog_human_hgnc_maps.get(cohort)
                if cohort in ortholog_human_hgnc_maps
                else None
            ),
        )
        cohort_jsonl_paths[cohort] = jsonl
        event("cohort_parsed", cohort=cohort, jsonl=str(jsonl.relative_to(REPO_ROOT)))

    # ----- Stage 5: paralog ECD identity (paralog BioMart pull already
    # happened in Stage 1.5; here we just compute ECD against the now-complete
    # topology JSONL which includes both candidates AND paralog expansions). -----
    paralog_jsonl: Path | None = None
    if (
        not args.skip_paralogs
        and paralog_csv is not None
        and "human_canonical" in cohort_jsonl_paths
    ):
        paralog_version = args.paralog_version or f"paralog_{args.topology_version}"
        paralog_rows = compute_paralog_records(
            paralog_csv=paralog_csv,
            canonical_topology_jsonl=cohort_jsonl_paths["human_canonical"],
            paralog_version=paralog_version,
            compara_version=args.compara_version,
        )
        paralog_jsonl = jsonl_root / "paralog_records.jsonl"
        write_paralog_jsonl(paralog_jsonl, paralog_rows)
        n_with_ecd = sum(1 for r in paralog_rows if r.get("ecd_pct_identity") is not None)
        event(
            "paralog_records_written",
            jsonl=str(paralog_jsonl.relative_to(REPO_ROOT)),
            n=len(paralog_rows),
            n_with_ecd=n_with_ecd,
        )

    # ----- Stage 5b: ortholog ECD identity (parallel to paralog ECD, but
    # cross-species — each (human, mouse/cyno ortholog) pair gets per-loop
    # BLOSUM62 ECD identity from the topology rows already in the JSONLs). -----
    ortholog_ecd_jsonl: Path | None = None
    has_ortholog_cohort = any(
        c in cohort_jsonl_paths for c in ("mouse_ortholog", "cyno_ortholog")
    )
    if has_ortholog_cohort and "human_canonical" in cohort_jsonl_paths:
        ortholog_ecd_version = f"orthologecd_{args.topology_version}"
        ortholog_ecd_rows = compute_ortholog_ecd_records(
            candidates=candidates,
            cohort_jsonl_paths=cohort_jsonl_paths,
            ortholog_human_hgnc_maps=ortholog_human_hgnc_maps,
            ortholog_ecd_version=ortholog_ecd_version,
            compara_release=args.compara_version,
        )
        ortholog_ecd_jsonl = jsonl_root / "ortholog_ecd_records.jsonl"
        write_ortholog_ecd_jsonl(ortholog_ecd_jsonl, ortholog_ecd_rows)
        n_with_ecd = sum(1 for r in ortholog_ecd_rows if r.get("ecd_pct_identity") is not None)
        event(
            "ortholog_ecd_records_written",
            jsonl=str(ortholog_ecd_jsonl.relative_to(REPO_ROOT)),
            n=len(ortholog_ecd_rows),
            n_with_ecd=n_with_ecd,
        )

    # ----- Stage 6: D1 upload -----
    if not args.skip_upload:
        import subprocess

        # Build a compact provenance JSON to stamp into each release row's
        # ``notes`` column. Lets D1 queriers see git SHA + manifest path
        # without having to read the run dir off disk.
        notes_payload = {
            "manifest_path": str(
                (jsonl_root / "run_manifest.json").relative_to(REPO_ROOT)
            ),
            "git_sha": _git_provenance.get("sha", ""),
            "git_branch": _git_provenance.get("branch", ""),
            "git_dirty": _git_provenance.get("dirty", False),
            "deeptmhmm_version": DEEPTMHMM_TOOL_VERSION,
            "compara_release": args.compara_version,
            "topology_version": args.topology_version,
            "run_started_at": run_started_at.isoformat(),
        }
        notes_json = json.dumps(notes_payload, sort_keys=True)

        jsonl_args: list[str] = []
        for j in cohort_jsonl_paths.values():
            jsonl_args.extend(["--jsonl", str(j)])
        cmd = [
            "uv", "run", "python", "scripts/upload_topology_to_d1.py",
            "--topology-version", args.topology_version,
            "--cohorts-present", ",".join(cohort_jsonl_paths.keys()),
            "--source-run-dir", str(run_dir.relative_to(REPO_ROOT)),
            "--notes", notes_json,
            *jsonl_args,
        ]
        logger.info("uploading topology")
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
        event("topology_uploaded", n_jsonl=len(cohort_jsonl_paths))

        if paralog_jsonl is not None:
            paralog_version = args.paralog_version or f"paralog_{args.topology_version}"
            cmd = [
                "uv", "run", "python", "scripts/upload_paralogs_to_d1.py",
                "--paralog-version", paralog_version,
                "--compara-release", args.compara_version,
                "--jsonl", str(paralog_jsonl),
                "--notes", notes_json,
            ]
            logger.info("uploading paralogs")
            subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            event("paralogs_uploaded", paralog_version=paralog_version)

        if ortholog_ecd_jsonl is not None:
            ortholog_ecd_version = f"orthologecd_{args.topology_version}"
            cmd = [
                "uv", "run", "python", "scripts/upload_ortholog_ecd_to_d1.py",
                "--ortholog-ecd-version", ortholog_ecd_version,
                "--compara-release", args.compara_version,
                "--jsonl", str(ortholog_ecd_jsonl),
                "--notes", notes_json,
            ]
            logger.info("uploading ortholog ECD")
            subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            event("ortholog_ecd_uploaded", ortholog_ecd_version=ortholog_ecd_version)

    # ----- Stage 7: write the run manifest BEFORE optional cleanup so the
    # manifest is the canonical provenance source even if the batch dirs
    # get wiped. The manifest captures git SHA, resolver versions, library
    # versions, Compara release, BioMart URLs, source hashes, per-cohort
    # counts — everything a future reader needs to reproduce this sweep.
    # ---------------------------------------------------------------------
    manifest = build_run_manifest(
        args=args,
        candidate_set_path=candidate_set_path,
        candidates=candidates,
        cohort_jsonl_paths=cohort_jsonl_paths,
        paralog_csv=paralog_csv,
        paralog_jsonl=paralog_jsonl,
        ortholog_ecd_jsonl=ortholog_ecd_jsonl,
        ortholog_human_hgnc_maps=ortholog_human_hgnc_maps,
        run_dir=run_dir,
        started_at=run_started_at,
    )
    manifest_path = jsonl_root / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    event("run_manifest_written", path=str(manifest_path.relative_to(REPO_ROOT)),
          sha256=_sha256_of_file(manifest_path))
    logger.info("run manifest written to %s", manifest_path.relative_to(REPO_ROOT))

    # ----- Stage 8 (optional): clean up large local intermediates after upload -----
    # PRESERVED for provenance:
    #   predicted_topologies.3line   — the raw DeepTMHMM output strings
    #   TMRs.gff3                    — per-protein TM-region coordinates (small)
    #   deeptmhmm_results.md         — DeepTMHMM's per-batch summary report
    # REMOVED (rebuildable from DeepTMHMM + sequences):
    #   embeddings/                  — per-residue ESM embeddings (~50 KB/protein, big)
    #   plot.png                     — per-batch plot (visual, redundant with .3line)
    #   _inputs/                     — batch FASTA inputs (rebuildable from sequence cache)
    if args.cleanup_after_upload and not args.skip_upload:
        import shutil

        keep_files = {"predicted_topologies.3line", "TMRs.gff3", "deeptmhmm_results.md"}
        bytes_removed = 0
        for cohort_dir in run_dir.iterdir():
            if not cohort_dir.is_dir():
                continue
            for batch_dir in cohort_dir.iterdir():
                if not batch_dir.is_dir():
                    continue
                if batch_dir.name == "_inputs":
                    try:
                        size = sum(f.stat().st_size for f in batch_dir.rglob("*") if f.is_file())
                    except OSError:
                        size = 0
                    shutil.rmtree(batch_dir)
                    bytes_removed += size
                    continue
                three_line = batch_dir / "predicted_topologies.3line"
                if three_line.exists():
                    for child in batch_dir.iterdir():
                        if child.name in keep_files:
                            continue
                        try:
                            size = (
                                sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                                if child.is_dir()
                                else child.stat().st_size
                            )
                        except OSError:
                            size = 0
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                        bytes_removed += size
                else:
                    try:
                        size = sum(f.stat().st_size for f in batch_dir.rglob("*") if f.is_file())
                    except OSError:
                        size = 0
                    shutil.rmtree(batch_dir)
                    bytes_removed += size
        event("cleanup_after_upload", run_dir=str(run_dir.relative_to(REPO_ROOT)),
              bytes_removed=bytes_removed,
              kept=sorted(keep_files))
        logger.info(
            "cleanup: kept .3line + TMRs.gff3 + deeptmhmm_results.md per batch; "
            "removed embeddings + plot + _inputs (%.1f MB freed)",
            bytes_removed / 1024 / 1024,
        )

    event("end", topology_version=args.topology_version,
          run_manifest=str(manifest_path.relative_to(REPO_ROOT)))
    logger.info("done — events log at %s", events_log.relative_to(REPO_ROOT))
    logger.info("run manifest at %s", manifest_path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
