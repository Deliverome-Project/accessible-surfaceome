"""Build the candidate set for the topology sweep.

The "yes" set is the union of:
  (a) every UniProt accession in ``candidate_universe.tsv`` with
      ``in_db_union == 1`` (any of the 7 surface databases said yes), AND
  (b) every UniProt accession with ``triage_run_public.predicted_verdict
      = 'yes'`` for the latest ``bench_version`` (the Sonnet surface_triage
      agent said yes).

Output: ``data/processed/topology_run_<version>/candidate_accessions.tsv``
with one row per base UniProt accession, plus a ``selection_reason`` column
in {db_only, triage_only, both} for downstream auditing.

Usage::

    uv run python scripts/build_topology_candidate_set.py \\
        --topology-version topo_2026_05_16

To override the candidate set (e.g. for a 3-protein dry run) pass
``--override-accessions O95800,O00206,P00533`` — the candidate_universe
and triage queries are skipped and the override list is written verbatim.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"

DEFAULT_CANDIDATE_UNIVERSE_TSV = Path(
    "data/processed/candidate_universe/candidate_universe.tsv"
)


@dataclass(frozen=True)
class CandidateRow:
    uniprot_acc: str
    gene_symbol: str
    selection_reason: str  # db_only | triage_only | both


def _from_env_public() -> tuple[str, str, str]:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    missing = [k for k, v in [
        ("CLOUDFLARE_ACCOUNT_ID", account),
        ("CLOUDFLARE_API_TOKEN", token),
        ("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", db),
    ] if not v]
    if missing:
        raise SystemExit("Missing env vars: " + ", ".join(missing))
    return account, db, token


def _d1_query(account: str, db: str, token: str, sql: str, *, client: httpx.Client) -> Any:
    url = f"{API_ROOT}/accounts/{account}/d1/database/{db}/query"
    resp = client.post(
        url,
        json={"sql": sql},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"D1 error: {body}")
    result = body.get("result") or []
    if isinstance(result, dict):
        result = [result]
    rows: list[dict[str, Any]] = []
    for r in result:
        rows.extend(r.get("results") or [])
    return rows


def _load_candidate_universe(tsv: Path) -> dict[str, str]:
    """Return uniprot_acc -> gene_symbol_resolved for every in_db_union==1 row."""
    out: dict[str, str] = {}
    if not tsv.exists():
        raise SystemExit(f"candidate_universe.tsv not found at {tsv}")
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            in_db_union = (r.get("in_db_union") or "").strip()
            if in_db_union not in {"1", "1.0", "true", "True"}:
                continue
            acc = (r.get("uniprot_accession") or "").strip().upper()
            if not acc:
                continue
            sym = (r.get("gene_symbol_resolved") or r.get("gene_symbol") or "").strip()
            out[acc] = sym
    return out


def _load_triage_yes(*, client: httpx.Client) -> dict[str, str]:
    """Return uniprot_acc -> gene_symbol for every triage 'yes' verdict.

    Queries the latest bench_version present in triage_run_public; if no
    rows exist (fresh DB or table missing), returns an empty dict and logs.
    """
    account, db, token = _from_env_public()
    # Latest bench_version (lexicographic; bench versions are date-stamped).
    rows = _d1_query(
        account, db, token,
        "SELECT bench_version, COUNT(*) AS n FROM triage_run_public "
        "GROUP BY bench_version ORDER BY bench_version DESC LIMIT 1",
        client=client,
    )
    if not rows:
        logger.info("triage_run_public has no rows; triage selection contributes 0")
        return {}
    bench = rows[0]["bench_version"]
    logger.info("latest triage bench_version: %s", bench)

    rows = _d1_query(
        account, db, token,
        f"SELECT DISTINCT uniprot_acc, gene_symbol FROM triage_run_public "
        f"WHERE bench_version = '{bench}' AND predicted_verdict = 'yes' "
        f"AND uniprot_acc IS NOT NULL AND uniprot_acc != ''",
        client=client,
    )
    out: dict[str, str] = {}
    for r in rows:
        acc = (r.get("uniprot_acc") or "").strip().upper()
        if acc:
            out[acc] = (r.get("gene_symbol") or "").strip()
    return out


def build_candidate_rows(
    *,
    candidate_universe_tsv: Path,
    override: list[str] | None,
    skip_d1: bool,
) -> list[CandidateRow]:
    """Union the two sets and tag each row with its selection_reason."""
    if override:
        return [
            CandidateRow(uniprot_acc=acc.upper(), gene_symbol="", selection_reason="override")
            for acc in override
            if acc
        ]

    db_set = _load_candidate_universe(candidate_universe_tsv)
    logger.info("candidate_universe (in_db_union=1): %d accessions", len(db_set))

    triage_set: dict[str, str] = {}
    if not skip_d1:
        try:
            with httpx.Client(timeout=60) as client:
                triage_set = _load_triage_yes(client=client)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to query triage_run_public (continuing without triage): %s", exc
            )
    logger.info("triage_run_public predicted_verdict='yes': %d accessions", len(triage_set))

    all_keys = sorted(set(db_set) | set(triage_set))
    rows: list[CandidateRow] = []
    for acc in all_keys:
        in_db = acc in db_set
        in_triage = acc in triage_set
        if in_db and in_triage:
            reason = "both"
        elif in_db:
            reason = "db_only"
        else:
            reason = "triage_only"
        sym = db_set.get(acc) or triage_set.get(acc) or ""
        rows.append(CandidateRow(uniprot_acc=acc, gene_symbol=sym, selection_reason=reason))
    return rows


def write_candidate_tsv(path: Path, rows: list[CandidateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("uniprot_acc\tgene_symbol\tselection_reason\n")
        for r in rows:
            f.write(f"{r.uniprot_acc}\t{r.gene_symbol}\t{r.selection_reason}\n")


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topology-version", required=True, help="e.g. topo_2026_05_16")
    ap.add_argument(
        "--candidate-universe-tsv",
        type=Path,
        default=DEFAULT_CANDIDATE_UNIVERSE_TSV,
    )
    ap.add_argument(
        "--override-accessions",
        type=str,
        default="",
        help="Comma-separated UniProt accessions to use INSTEAD of the union. "
             "Skips the candidate_universe + triage queries entirely.",
    )
    ap.add_argument(
        "--skip-d1",
        action="store_true",
        help="Skip the triage_run_public query (offline dry runs).",
    )
    args = ap.parse_args()

    override = [s.strip() for s in args.override_accessions.split(",") if s.strip()]
    rows = build_candidate_rows(
        candidate_universe_tsv=args.candidate_universe_tsv,
        override=override or None,
        skip_d1=args.skip_d1,
    )

    out_dir = Path("data/processed") / f"topology_run_{args.topology_version}"
    out_path = out_dir / "candidate_accessions.tsv"
    write_candidate_tsv(out_path, rows)

    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r.selection_reason] = by_reason.get(r.selection_reason, 0) + 1
    logger.info("wrote %d rows to %s", len(rows), out_path)
    logger.info("by selection_reason: %s", by_reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
