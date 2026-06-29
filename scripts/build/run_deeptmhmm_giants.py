"""Run DeepTMHMM on length-skipped giants one at a time, bypassing the filter.

The main sweep (`scripts/build/run_topology_sweep.py`) skips proteins over
``DEEPTMHMM_MAX_SEQUENCE_LENGTH`` (8,000 aa) because DeepTMHMM 1.0.24's
ESM-2 inference OOMs on 16 GB machines when several giants run in
parallel. Run them serially here so each gets the full memory budget.

Workflow per acc:
  1. Read the cached FASTA (must already be in data/external/sequences/).
  2. Write a single-protein batch FASTA under ``run_dir/_inputs/<acc>.fasta``.
  3. Run DeepTMHMM ``predict.py`` into ``run_dir/<acc>/`` with no length
     filter applied.
  4. Parse the resulting ``predicted_topologies.3line`` and stamp on the
     topology_version + cohort + hgnc_id + gene_symbol fields the upload
     script expects.
  5. Append to a giants JSONL the caller can hand to
     ``scripts/upload/upload_topology_to_d1.py``.

Memory + time estimates (Apple M2, 16 GB):
  Q7Z5P9 MUC19 (8,384 aa)  → ~5 min,   peak RSS ~10 GB
  Q8NF91 SYNE1 (8,797 aa)  → ~6 min,   peak RSS ~11 GB
  Q9H195 MUC3B (13,477 aa) → ~15 min,  peak RSS ~20+ GB (likely OOMs)

Run::

    DEEPTMHMM_ROOT=/path/to/deeptmhmm DEEPTMHMM_THREADS=2 \
        uv run python scripts/build/run_deeptmhmm_giants.py \
        --accessions Q7Z5P9,Q8NF91,Q9H195 \
        --topology-version topo_2026_05_16

Then upload (idempotent INSERT OR IGNORE so safe to re-run)::

    uv run python scripts/upload/upload_topology_to_d1.py \
        --jsonl data/processed/topology_run_topo_2026_05_16/giants_topology_records.jsonl \
        --cohorts-present human_canonical
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.sources.deeptmhmm import (
    parse_3line,
    resolve_deeptmhmm_paths,
    run_deeptmhmm_batch,
)

logger = logging.getLogger(__name__)

DEFAULT_GIANTS = ["Q7Z5P9", "Q8NF91", "Q9H195"]


def _lookup_gene_metadata(uniprot_acc: str) -> tuple[str | None, str | None, str | None]:
    """Pull (hgnc_id, hgnc_symbol, ensembl_canonical_protein) from public D1."""
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    db = os.environ["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/d1/database/{db}/query"
    r = httpx.post(
        url,
        json={
            "sql": "SELECT hgnc_id, hgnc_symbol, ensembl_canonical_protein "
                   "FROM gene_identifier_public WHERE uniprot_acc = ? LIMIT 1",
            "params": [uniprot_acc],
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    data = r.json()
    if not data.get("success"):
        return (None, None, None)
    rows = data["result"][0]["results"]
    if not rows:
        return (None, None, None)
    row = rows[0]
    return (
        row.get("hgnc_id"),
        row.get("hgnc_symbol"),
        row.get("ensembl_canonical_protein"),
    )


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--accessions",
        default=",".join(DEFAULT_GIANTS),
        help=f"comma-separated UniProt accessions (default: {','.join(DEFAULT_GIANTS)})",
    )
    ap.add_argument("--topology-version", default="topo_2026_05_16")
    ap.add_argument("--cohort", default="human_canonical")
    ap.add_argument(
        "--out-jsonl",
        default=str(REPO_ROOT / "data" / "processed" / "topology_run_topo_2026_05_16" / "giants_topology_records.jsonl"),
    )
    ap.add_argument(
        "--run-dir",
        default=str(REPO_ROOT / "data" / "external" / "deeptmhmm_topology_run_topo_2026_05_16" / "_giants"),
        help="parent dir for per-acc DeepTMHMM batch outputs",
    )
    ap.add_argument(
        "--sequences-dir",
        default=str(REPO_ROOT / "data" / "external" / "sequences"),
        help="UniProt FASTA cache dir",
    )
    ap.add_argument(
        "--timeout-s", type=float, default=3600.0,
        help="per-protein DeepTMHMM subprocess timeout (default 1 hour)",
    )
    args = ap.parse_args()

    accs = [a.strip() for a in args.accessions.split(",") if a.strip()]
    if not accs:
        logger.error("no accessions provided")
        return 1

    package_dir, venv_dir = resolve_deeptmhmm_paths()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = run_dir / "_inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    sequences_dir = Path(args.sequences_dir)
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    out_records: list[dict] = []
    errors: list[tuple[str, str]] = []
    for acc in accs:
        fasta_src = sequences_dir / f"{acc}.fasta"
        if not fasta_src.exists():
            logger.error("  %s: no FASTA at %s", acc, fasta_src)
            errors.append((acc, "no_fasta"))
            continue
        text = fasta_src.read_text(encoding="utf-8")
        # Bypass `assemble_batch_fasta`'s length filter — write the FASTA
        # verbatim into the batch input dir.
        batch_fasta = inputs_dir / f"{acc}.fasta"
        batch_fasta.write_text(text, encoding="utf-8")
        seq_len = sum(len(ln) for ln in text.splitlines()[1:] if not ln.startswith(">"))
        logger.info("  %s: running DeepTMHMM (seq_len=%d, timeout=%.0fs)",
                    acc, seq_len, args.timeout_s)
        out_dir = run_dir / acc
        try:
            three_line = run_deeptmhmm_batch(
                batch_fasta,
                output_dir=out_dir,
                package_dir=package_dir,
                venv_dir=venv_dir,
                timeout_s=args.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("  %s: DeepTMHMM failed: %s", acc, exc)
            errors.append((acc, str(exc)[:160]))
            continue
        # Parse + enrich with the schema the uploader expects.
        try:
            records = parse_3line(three_line)
        except Exception as exc:  # noqa: BLE001
            logger.error("  %s: parse_3line failed: %s", acc, exc)
            errors.append((acc, f"parse: {exc}"[:160]))
            continue
        hgnc_id, hgnc_symbol, _ensembl = _lookup_gene_metadata(acc)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for rec in records:
            rec["topology_version"] = args.topology_version
            rec["cohort"] = args.cohort
            rec["species"] = "human"
            rec["is_canonical"] = 1
            rec["hgnc_id"] = hgnc_id
            rec["gene_symbol"] = hgnc_symbol or ""
            rec["isoform_id"] = rec.get("uniprot_accession_full") or f"{acc}-1"
            rec["tool_version"] = "deeptmhmm-1.0.24"
            rec["retrieved_at"] = now
            out_records.append(rec)
            logger.info(
                "  %s done: label=%s tm=%d ecd=%d signal=%d",
                acc, rec.get("deeptmhmm_label"),
                rec.get("tm_helix_count", 0),
                rec.get("ecd_length_residues", 0),
                rec.get("signal_peptide_length", 0),
            )

    if out_records:
        with out_path.open("w", encoding="utf-8") as fh:
            for rec in out_records:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
        logger.info("wrote %d records to %s", len(out_records), out_path.relative_to(REPO_ROOT))
    else:
        logger.warning("no records produced; not writing JSONL")
    if errors:
        logger.warning("errors on %d accs:", len(errors))
        for acc, reason in errors:
            logger.warning("  %s: %s", acc, reason)
        return 2 if not out_records else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
