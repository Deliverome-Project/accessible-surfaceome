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
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def _resolve_ortholog_accessions(
    candidates: list[Candidate], *, species_key: str
) -> list[tuple[str, str]]:
    """Return (acc_full, gene_symbol) pairs for mouse or cyno orthologs.

    Reads the BioMart ortholog CSV produced by sources/ensembl_compara.py.
    Filters to one2one + high-confidence rows for the species. The Compara
    CSV is symbol-keyed (the M1 merge predates PR #30); we join on
    ``cohort_symbol`` — the resolver's snapshot of the cohort symbol at
    build time. This is the legitimate symbol join: cohort_symbol IS the
    symbol the merge wrote into ``input_gene_symbol``, so they're the
    same string by construction. A follow-up refactor will rebuild the
    Compara orthologs CSV keyed on Ensembl gene IDs to eliminate this
    entirely.
    """
    if not COMPARA_ORTHOLOG_CSV.exists():
        logger.warning(
            "Compara ortholog CSV not found at %s; %s cohort will be empty. "
            "Run: uv run python -m accessible_surfaceome.sources.ensembl_compara download",
            COMPARA_ORTHOLOG_CSV.relative_to(REPO_ROOT), species_key,
        )
        return []
    human_symbols = {c.cohort_symbol.upper() for c in candidates if c.cohort_symbol}
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    # The Compara CSV columns include: input_gene_symbol, resolved_gene_symbol,
    # plus species-specific *_homolog_associated_gene_name, *_orthology_type,
    # *_orthology_confidence. We look up by gene_symbol_resolved and pull the
    # UniProt accession via a separate UniProt query — but for the v1 sweep
    # we only have ensembl IDs from the CSV. We resolve UniProt at fetch time.
    pass_filter = (
        "mmusculus" if species_key == "mouse_ortholog" else "mfascicularis"
    )
    with COMPARA_ORTHOLOG_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym_resolved = (row.get("resolved_gene_symbol") or "").strip().upper()
            sym_input = (row.get("input_gene_symbol") or "").strip().upper()
            if sym_resolved not in human_symbols and sym_input not in human_symbols:
                continue
            otype = (row.get(f"{pass_filter}_homolog_orthology_type") or "").strip()
            conf = (row.get(f"{pass_filter}_homolog_orthology_confidence") or "").strip()
            if otype != "ortholog_one2one" or conf not in {"1", "1.0"}:
                continue
            ortho_ensg = (row.get(f"{pass_filter}_homolog_ensembl_gene") or "").strip()
            ortho_sym = (row.get(f"{pass_filter}_homolog_associated_gene_name") or "").strip()
            if ortho_ensg and ortho_ensg not in seen:
                seen.add(ortho_ensg)
                # acc_full will be resolved at FASTA-fetch time from UniProt
                # mapping; stash the Ensembl ID here so the caller can do the
                # UniProt lookup later. For v1 we punt and skip — the existing
                # ortholog FASTA pull in deeptmhmm.py:download_main already
                # does this lookup; we mirror that on demand.
                out.append((ortho_ensg, ortho_sym))
    return out


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

    # Build batch FASTAs (deterministic chunking by sorted path).
    fasta_paths_sorted = sorted(fasta_paths)
    batches: list[tuple[Path, Path]] = []
    for batch_idx in range(0, len(fasta_paths_sorted), batch_size):
        batch_files = fasta_paths_sorted[batch_idx : batch_idx + batch_size]
        batch_n = batch_idx // batch_size
        batch_root = cohort_dir / f"batch_{batch_n:04d}"
        batch_root.mkdir(parents=True, exist_ok=True)
        batch_fasta = batch_root / "input.fasta"
        n_written, batch_skips = assemble_batch_fasta(
            batch_files, batch_path=batch_fasta, max_seq_length=DEEPTMHMM_MAX_SEQUENCE_LENGTH,
        )
        skipped_too_long.extend(batch_skips)
        if n_written == 0:
            continue
        batches.append((batch_fasta, batch_root))

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
) -> Path:
    """Parse all .3line outputs into one topology_records.jsonl for the cohort.

    For human cohorts, filter records to just those whose base UniProt
    accession is in the candidate set — keeps the JSONL row count aligned
    with what the candidate set asked for, and makes 3-protein dry runs
    actually output 3 rows instead of all 2,359 in the legacy .3line.
    For ortholog cohorts (mouse/cyno), no candidate-accession filter is
    applied — orthologs use different accessions and need a Compara-CSV
    join to map back to the human candidate; that join lives elsewhere.
    """
    species = SPECIES_BY_COHORT[cohort]
    is_human_cohort = cohort in {"human_canonical", "human_isoforms"}
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
                if is_human_cohort and candidate_by_acc and base not in candidate_by_acc:
                    n_filtered_out += 1
                    continue
                # Dedupe across multiple legacy + fresh .3line files.
                full = rec["uniprot_accession_full"]
                if full in seen_full_accs:
                    continue
                seen_full_accs.add(full)
                cand = candidate_by_acc.get(base)
                rec["topology_version"] = topology_version
                rec["cohort"] = cohort
                rec["species"] = species
                rec["isoform_id"] = rec["uniprot_accession_full"]
                rec["is_canonical"] = int(cohort == "human_canonical"
                                          or rec["uniprot_accession_full"].endswith("-1")
                                          or "-" not in rec["uniprot_accession_full"])
                # Stable IDs from gene_identifier (via the candidate set).
                # hgnc_id is the canonical key; gene_symbol is denormalized
                # for offline reads only. Ortholog cohorts have no human
                # HGNC ID per row — leave hgnc_id NULL there.
                rec["hgnc_id"] = (
                    cand.hgnc_id if (cand and cohort in {"human_canonical", "human_isoforms"})
                    else None
                )
                rec["gene_symbol"] = cand.cohort_symbol if cand else ""
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


def maybe_pull_paralogs(*, override_ensembl_ids: list[str]) -> Path | None:
    """If the paralog CSV is missing, kick off a fresh BioMart pull.

    Takes Ensembl gene IDs (resolved from ``gene_identifier`` by the
    caller) instead of symbols. The downstream
    ``ensembl_compara_paralogs.download_main`` understands the
    ``--override-ensembl-ids`` flag and bypasses HGNC TSV loading entirely
    when given a non-empty list, so the symbol-keyed fallback path is
    never exercised.
    """
    if COMPARA_PARALOG_BY_GENE_CSV.exists():
        return COMPARA_PARALOG_BY_GENE_CSV
    logger.info("paralog CSV missing; running ensembl_compara_paralogs download...")
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

    event("start", topology_version=args.topology_version, cohorts=cohorts,
          max_workers=args.max_workers)

    candidates = load_candidate_set(candidate_set_path)
    event("candidate_set_loaded", n=len(candidates),
          source=str(candidate_set_path.relative_to(REPO_ROOT)))
    candidate_by_acc = {c.uniprot_acc: c for c in candidates}

    # ----- Stage 2: Per-cohort accession lists -----
    cohort_accessions: dict[str, list[str]] = {}
    if "human_canonical" in cohorts:
        cohort_accessions["human_canonical"] = [c.uniprot_acc for c in candidates]
    if "human_isoforms" in cohorts:
        # For v1 we use the existing human_isoforms cohort FASTA inputs
        # already produced under data/external/deeptmhmm_surfaceome_predictions/
        # human_isoforms_from_afdb_non_hla/ — that set is curated by
        # ensembl_compara/deeptmhmm.download_main. Resolving fresh isoforms
        # for arbitrary candidates is out of scope for this orchestrator;
        # the existing predictions land in D1 via reparse below. New
        # candidates that need fresh isoform DeepTMHMM should re-run the
        # download_main pipeline beforehand.
        cohort_accessions["human_isoforms"] = []
    if "mouse_ortholog" in cohorts:
        ortho_pairs = _resolve_ortholog_accessions(candidates, species_key="mouse_ortholog")
        cohort_accessions["mouse_ortholog"] = []
        logger.info("  mouse_ortholog: %d Ensembl IDs (UniProt resolution at fetch time TBD)",
                    len(ortho_pairs))
    if "cyno_ortholog" in cohorts:
        ortho_pairs = _resolve_ortholog_accessions(candidates, species_key="cyno_ortholog")
        cohort_accessions["cyno_ortholog"] = []
        logger.info("  cyno_ortholog: %d Ensembl IDs (UniProt resolution at fetch time TBD)",
                    len(ortho_pairs))

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

    # ----- Stage 4: DeepTMHMM run + parse, per cohort -----
    cohort_jsonl_paths: dict[str, Path] = {}
    for cohort in cohorts:
        cohort_dir = run_dir / cohort
        cohort_dir.mkdir(parents=True, exist_ok=True)

        if cohort == "human_canonical":
            # Skip DeepTMHMM for FASTAs whose base accession is already in the
            # legacy .3line — that's the 2,359-protein backlog we don't need
            # to re-predict. Only the gap (~3,321) goes through DeepTMHMM.
            legacy_3line = (
                REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
                / "human_canonical_non_hla" / "predicted_topologies.3line"
            )
            already_predicted: set[str] = set()
            if legacy_3line.exists():
                try:
                    for rec in parse_3line(legacy_3line):
                        already_predicted.add(rec["uniprot_accession"])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("could not pre-scan legacy .3line: %s", exc)
            gap_fasta_paths = [
                p for acc, p in canonical_fasta_paths.items()
                if acc not in already_predicted
            ]
            logger.info(
                "  %s: %d FASTAs total, %d already covered by legacy .3line, "
                "%d going to DeepTMHMM", cohort, len(canonical_fasta_paths),
                len(canonical_fasta_paths) - len(gap_fasta_paths),
                len(gap_fasta_paths),
            )
            output_3line_paths, skipped = run_cohort_deeptmhmm(
                cohort=cohort,
                cohort_dir=cohort_dir,
                fasta_paths=gap_fasta_paths,
                max_workers=args.max_workers,
                batch_size=args.batch_size,
            )
            event("deeptmhmm_done", cohort=cohort,
                  n_batches=len(output_3line_paths), n_skipped_too_long=len(skipped),
                  n_reused_from_legacy=len(canonical_fasta_paths) - len(gap_fasta_paths))
            # Append the legacy .3line so the JSONL ends with full coverage
            # of any prior predictions in addition to the fresh batches.
            if legacy_3line.exists():
                output_3line_paths.append(legacy_3line)
        else:
            # Reuse pre-existing predictions for isoforms / orthologs in v1.
            cohort_map = {
                "human_isoforms": "human_isoforms_from_afdb_non_hla",
                "mouse_ortholog": "mouse_ortholog_one2one_highconf_non_hla",
                "cyno_ortholog": "cyno_ortholog_one2one_highconf_non_hla",
            }
            legacy = (
                REPO_ROOT / "data" / "external" / "deeptmhmm_surfaceome_predictions"
                / cohort_map[cohort] / "predicted_topologies.3line"
            )
            if not legacy.exists():
                logger.warning("  %s: legacy .3line not found at %s; cohort produces 0 rows",
                               cohort, legacy.relative_to(REPO_ROOT))
                continue
            output_3line_paths = [legacy]
            event("legacy_reuse", cohort=cohort,
                  source=str(legacy.relative_to(REPO_ROOT)))

        jsonl = parse_cohort_to_jsonl(
            cohort=cohort,
            output_3line_paths=output_3line_paths,
            cohort_dir=jsonl_root / cohort,
            topology_version=args.topology_version,
            candidate_by_acc=candidate_by_acc,
        )
        cohort_jsonl_paths[cohort] = jsonl
        event("cohort_parsed", cohort=cohort, jsonl=str(jsonl.relative_to(REPO_ROOT)))

    # ----- Stage 5: paralogs + ECD identity -----
    paralog_jsonl: Path | None = None
    if not args.skip_paralogs and "human_canonical" in cohort_jsonl_paths:
        # ALWAYS pass the candidate set's Ensembl gene IDs (resolved via
        # gene_identifier) to the BioMart pull — no fallback to the legacy
        # candidate_universe-TSV + HGNC-TSV path. The HGNC TSV isn't
        # hydrated in this worktree and the legacy path's symbol-based
        # resolution is exactly the bug class PR #30 fixes.
        override_ensembl_ids = [
            c.ensembl_gene for c in candidates if c.ensembl_gene
        ]
        logger.info(
            "paralog pull: %d candidates → %d Ensembl gene IDs going to BioMart",
            len(candidates), len(override_ensembl_ids),
        )
        paralog_csv = maybe_pull_paralogs(override_ensembl_ids=override_ensembl_ids)
        if paralog_csv is not None:
            paralog_version = args.paralog_version or f"paralog_{args.topology_version}"
            paralog_rows = compute_paralog_records(
                paralog_csv=paralog_csv,
                canonical_topology_jsonl=cohort_jsonl_paths["human_canonical"],
                paralog_version=paralog_version,
                compara_version=args.compara_version,
            )
            paralog_jsonl = jsonl_root / "paralog_records.jsonl"
            write_paralog_jsonl(paralog_jsonl, paralog_rows)
            event("paralog_records_written",
                  jsonl=str(paralog_jsonl.relative_to(REPO_ROOT)),
                  n=len(paralog_rows))

    # ----- Stage 6: D1 upload -----
    if not args.skip_upload:
        import subprocess
        jsonl_args: list[str] = []
        for j in cohort_jsonl_paths.values():
            jsonl_args.extend(["--jsonl", str(j)])
        cmd = [
            "uv", "run", "python", "scripts/upload_topology_to_d1.py",
            "--topology-version", args.topology_version,
            "--cohorts-present", ",".join(cohort_jsonl_paths.keys()),
            "--source-run-dir", str(run_dir.relative_to(REPO_ROOT)),
            *jsonl_args,
        ]
        logger.info("uploading topology: %s", " ".join(cmd))
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
        event("topology_uploaded", n_jsonl=len(cohort_jsonl_paths))

        if paralog_jsonl is not None:
            paralog_version = args.paralog_version or f"paralog_{args.topology_version}"
            cmd = [
                "uv", "run", "python", "scripts/upload_paralogs_to_d1.py",
                "--paralog-version", paralog_version,
                "--compara-release", args.compara_version,
                "--jsonl", str(paralog_jsonl),
            ]
            logger.info("uploading paralogs: %s", " ".join(cmd))
            subprocess.run(cmd, cwd=REPO_ROOT, check=True)
            event("paralogs_uploaded", paralog_version=paralog_version)

    event("end", topology_version=args.topology_version)
    logger.info("done — events log at %s", events_log.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
