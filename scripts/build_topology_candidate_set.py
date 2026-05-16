"""Build the candidate set for the topology sweep — HGNC-ID-keyed.

The "yes" set is the union of:
  (a) every gene in ``candidate_universe.tsv`` with ``in_db_union == 1`` —
      i.e. any of the 5 gating surface databases voted "yes" under that
      source's optimized cutoff (see merge/__init__.py:GATING_FLAG_COLUMNS),
  (b) every gene with ``triage_run.predicted_verdict IN ('yes', 'contextual')``
      for the latest genome-wide Sonnet run.

Stable IDs from PR #30's ``gene_identifier`` table are joined onto every row
so the orchestrator and uploaders never re-resolve from symbol. Output is
keyed on HGNC ID and carries (hgnc_id, hgnc_symbol, uniprot_acc, ensembl_gene,
ncbi_gene_id, ensembl_canonical_protein) — exactly the stable identifier set
``gene_identifier`` exposes.

When a candidate gene doesn't have a ``gene_identifier`` row yet (PR #30's
build script is run separately and may not yet cover the full union), we
fall back to the symbol → uniprot/ensembl mapping from
``candidate_universe.tsv`` and emit a warning row with ``stable_id_source =
'fallback'``. The orchestrator skips fallback rows by default to avoid
silent resolver drift.

Output: ``data/processed/topology_run_<version>/candidate_accessions.tsv``.

Usage::

    uv run python scripts/build_topology_candidate_set.py \\
        --topology-version topo_2026_05_16

Override with explicit HGNC IDs (3-protein dry run)::

    uv run python scripts/build_topology_candidate_set.py \\
        --topology-version topo_test \\
        --override-hgnc-ids HGNC:4526,HGNC:11850,HGNC:3236  # GPR75, TLR4, EGFR
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

# The Sonnet triage run we treat as the "current" verdict source. Latest
# whole-genome triage with the canonical NCBI-resolver variant.
DEFAULT_TRIAGE_RUN_ID = "genome_full_sonnet_ncbi_v1"
TRIAGE_YES_VERDICTS = frozenset({"yes", "contextual"})


@dataclass(frozen=True)
class CandidateRow:
    """One row of the candidate accessions TSV — stable-ID-keyed."""

    hgnc_id: str | None
    hgnc_symbol: str
    uniprot_acc: str
    ensembl_gene: str | None
    ncbi_gene_id: int | None
    ensembl_canonical_protein: str | None
    cohort_symbol: str           # symbol the M1 cohort used (for join-back to TSV)
    in_db_union: int             # 1 iff in candidate_universe.tsv with in_db_union=1
    triage_verdict: str | None   # 'yes' | 'contextual' | None (only yes+contextual carry through)
    selection_reason: str        # db_only | triage_only | both
    stable_id_source: str        # 'gene_identifier' | 'fallback' | 'override'
    needs_review: int            # mirrored from gene_identifier when applicable


def _from_env_agents() -> tuple[str, str, str]:
    """Resolve the agents-DB (private) D1 config from env."""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    missing = [
        k
        for k, v in [
            ("CLOUDFLARE_ACCOUNT_ID", account),
            ("CLOUDFLARE_API_TOKEN", token),
            ("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", db),
        ]
        if not v
    ]
    if missing:
        raise SystemExit("Missing env vars: " + ", ".join(missing))
    return account, db, token


def _d1_query(
    account: str, db: str, token: str, sql: str, *, client: httpx.Client
) -> list[dict[str, Any]]:
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


def _load_candidate_universe(tsv: Path) -> dict[str, dict[str, Any]]:
    """Return ``{symbol_upper: row}`` for every in_db_union=1 row, with the
    best (highest n_sources_surface) UniProt per symbol kept on collision.
    """
    if not tsv.exists():
        raise SystemExit(f"candidate_universe.tsv not found at {tsv}")
    by_sym: dict[str, dict[str, Any]] = {}
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            in_db_union = (r.get("in_db_union") or "").strip()
            if in_db_union not in {"1", "1.0", "true", "True"}:
                continue
            sym = (
                r.get("gene_symbol_resolved") or r.get("gene_symbol") or ""
            ).strip().upper()
            if not sym:
                continue
            try:
                n = int(float((r.get("n_sources_surface") or "0").strip() or "0"))
            except ValueError:
                n = 0
            existing = by_sym.get(sym)
            if existing is None or n > int(float(existing.get("_n", 0))):
                r["_n"] = n
                by_sym[sym] = r
    return by_sym


def _load_gene_identifier_index(
    *, client: httpx.Client
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return two indexes of ``gene_identifier``: by HGNC symbol, by cohort symbol.

    The two often agree but diverge for the ~30 rename-drift cases where HGNC
    has applied a primary-symbol change UniProt / NCBI hasn't synced. Lookups
    fall back from cohort_symbol → hgnc_symbol so either spelling resolves.
    """
    account, db, token = _from_env_agents()
    rows = _d1_query(
        account,
        db,
        token,
        "SELECT hgnc_id, hgnc_symbol, cohort_symbol, uniprot_acc, "
        "ncbi_gene_id, ensembl_gene, ensembl_canonical_protein, "
        "resolver_path, resolver_version, needs_review "
        "FROM gene_identifier",
        client=client,
    )
    by_hgnc_sym: dict[str, dict[str, Any]] = {}
    by_cohort_sym: dict[str, dict[str, Any]] = {}
    for r in rows:
        if (sym := (r.get("hgnc_symbol") or "").strip().upper()):
            by_hgnc_sym[sym] = r
        if (csym := (r.get("cohort_symbol") or "").strip().upper()):
            by_cohort_sym[csym] = r
    return by_hgnc_sym, by_cohort_sym


def _load_triage_yes_contextual(
    *, client: httpx.Client, run_id: str
) -> dict[str, str]:
    """Return ``{cohort_symbol_upper: verdict}`` for triage 'yes' + 'contextual'."""
    account, db, token = _from_env_agents()
    rows = _d1_query(
        account,
        db,
        token,
        f"SELECT DISTINCT gene_symbol, predicted_verdict FROM triage_run "
        f"WHERE run_id = '{run_id}' "
        f"AND predicted_verdict IN ('yes', 'contextual') "
        f"AND gene_symbol IS NOT NULL AND gene_symbol != ''",
        client=client,
    )
    out: dict[str, str] = {}
    for r in rows:
        sym = (r.get("gene_symbol") or "").strip().upper()
        verdict = (r.get("predicted_verdict") or "").strip()
        if sym and verdict in TRIAGE_YES_VERDICTS:
            # contextual loses to yes if a gene somehow has both (it shouldn't,
            # but defensive — sort puts 'yes' first lexicographically).
            existing = out.get(sym)
            if existing is None or (existing == "contextual" and verdict == "yes"):
                out[sym] = verdict
    return out


def _resolve_gene_identifier(
    symbol_upper: str,
    *,
    by_hgnc_sym: dict[str, dict[str, Any]],
    by_cohort_sym: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Try gene_identifier lookup by HGNC primary symbol first, then cohort symbol."""
    if (row := by_hgnc_sym.get(symbol_upper)) is not None:
        return row
    if (row := by_cohort_sym.get(symbol_upper)) is not None:
        return row
    return None


def _build_from_override_hgnc_ids(
    hgnc_ids: list[str],
    *,
    by_hgnc_sym: dict[str, dict[str, Any]],
    by_cohort_sym: dict[str, dict[str, Any]],
) -> list[CandidateRow]:
    """Build rows from explicit HGNC IDs (dry-run / verification path)."""
    by_hgnc_id: dict[str, dict[str, Any]] = {
        r["hgnc_id"]: r for r in by_hgnc_sym.values() if r.get("hgnc_id")
    }
    rows: list[CandidateRow] = []
    for hid in hgnc_ids:
        gi = by_hgnc_id.get(hid)
        if gi is None:
            logger.warning("override HGNC ID %s not in gene_identifier — skipping", hid)
            continue
        if not gi.get("uniprot_acc"):
            logger.warning("override HGNC ID %s has no uniprot_acc — skipping", hid)
            continue
        rows.append(
            CandidateRow(
                hgnc_id=hid,
                hgnc_symbol=(gi.get("hgnc_symbol") or "").strip(),
                uniprot_acc=(gi.get("uniprot_acc") or "").strip(),
                ensembl_gene=(gi.get("ensembl_gene") or None),
                ncbi_gene_id=(
                    int(gi["ncbi_gene_id"]) if gi.get("ncbi_gene_id") else None
                ),
                ensembl_canonical_protein=(gi.get("ensembl_canonical_protein") or None),
                cohort_symbol=(gi.get("cohort_symbol") or gi.get("hgnc_symbol") or "").strip(),
                in_db_union=0,
                triage_verdict=None,
                selection_reason="override",
                stable_id_source="override",
                needs_review=int(gi.get("needs_review") or 0),
            )
        )
    return rows


def build_candidate_rows(
    *,
    candidate_universe_tsv: Path,
    triage_run_id: str,
    override_hgnc_ids: list[str] | None,
    skip_d1: bool,
) -> list[CandidateRow]:
    """Union DB-yes + triage-yes/contextual, attach stable IDs from gene_identifier."""
    with httpx.Client(timeout=60) as client:
        by_hgnc_sym, by_cohort_sym = _load_gene_identifier_index(client=client)
        logger.info(
            "gene_identifier rows loaded: %d (by HGNC symbol), %d (by cohort symbol)",
            len(by_hgnc_sym), len(by_cohort_sym),
        )

        if override_hgnc_ids:
            return _build_from_override_hgnc_ids(
                override_hgnc_ids,
                by_hgnc_sym=by_hgnc_sym,
                by_cohort_sym=by_cohort_sym,
            )

        db_yes_by_sym = _load_candidate_universe(candidate_universe_tsv)
        logger.info("candidate_universe in_db_union=1: %d symbols", len(db_yes_by_sym))

        triage_yc: dict[str, str] = {}
        if not skip_d1:
            try:
                triage_yc = _load_triage_yes_contextual(client=client, run_id=triage_run_id)
                logger.info(
                    "triage yes+contextual (run_id=%s): %d symbols",
                    triage_run_id, len(triage_yc),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("triage query failed (continuing DB-only): %s", exc)

    all_symbols = set(db_yes_by_sym) | set(triage_yc)
    rows: list[CandidateRow] = []
    n_gi_hit = 0
    n_fallback = 0
    n_dropped_no_uniprot = 0

    for sym in sorted(all_symbols):
        in_db = sym in db_yes_by_sym
        triage_verdict = triage_yc.get(sym)

        if in_db and triage_verdict is not None:
            reason = "both"
        elif in_db:
            reason = "db_only"
        else:
            reason = "triage_only"

        gi = _resolve_gene_identifier(
            sym, by_hgnc_sym=by_hgnc_sym, by_cohort_sym=by_cohort_sym
        )

        if gi is not None and gi.get("uniprot_acc"):
            n_gi_hit += 1
            rows.append(
                CandidateRow(
                    hgnc_id=gi.get("hgnc_id"),
                    hgnc_symbol=(gi.get("hgnc_symbol") or sym),
                    uniprot_acc=(gi.get("uniprot_acc") or "").strip(),
                    ensembl_gene=(gi.get("ensembl_gene") or None),
                    ncbi_gene_id=(
                        int(gi["ncbi_gene_id"]) if gi.get("ncbi_gene_id") else None
                    ),
                    ensembl_canonical_protein=(gi.get("ensembl_canonical_protein") or None),
                    cohort_symbol=(gi.get("cohort_symbol") or sym),
                    in_db_union=int(in_db),
                    triage_verdict=triage_verdict,
                    selection_reason=reason,
                    stable_id_source="gene_identifier",
                    needs_review=int(gi.get("needs_review") or 0),
                )
            )
            continue

        # Fallback: gene_identifier missing this gene (PR #30 builder not yet
        # populated for it). Use candidate_universe.tsv's UniProt accession
        # if we have one. The orchestrator can choose to skip fallback rows
        # so the sweep never silently runs against the un-resolved gene.
        fb = db_yes_by_sym.get(sym)
        fb_uniprot = (fb.get("uniprot_accession") if fb else "") or ""
        fb_uniprot = fb_uniprot.strip().upper()
        if not fb_uniprot:
            n_dropped_no_uniprot += 1
            continue
        n_fallback += 1
        rows.append(
            CandidateRow(
                hgnc_id=None,
                hgnc_symbol=sym,
                uniprot_acc=fb_uniprot,
                ensembl_gene=None,
                ncbi_gene_id=None,
                ensembl_canonical_protein=None,
                cohort_symbol=sym,
                in_db_union=int(in_db),
                triage_verdict=triage_verdict,
                selection_reason=reason,
                stable_id_source="fallback",
                needs_review=0,
            )
        )

    logger.info(
        "candidate set: %d rows total (gene_identifier=%d, fallback=%d, "
        "dropped-no-uniprot=%d)",
        len(rows), n_gi_hit, n_fallback, n_dropped_no_uniprot,
    )
    return rows


def write_candidate_tsv(path: Path, rows: list[CandidateRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "hgnc_id",
        "hgnc_symbol",
        "cohort_symbol",
        "uniprot_acc",
        "ensembl_gene",
        "ncbi_gene_id",
        "ensembl_canonical_protein",
        "in_db_union",
        "triage_verdict",
        "selection_reason",
        "stable_id_source",
        "needs_review",
    ]
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write(
                "\t".join(
                    [
                        r.hgnc_id or "",
                        r.hgnc_symbol or "",
                        r.cohort_symbol or "",
                        r.uniprot_acc or "",
                        r.ensembl_gene or "",
                        str(r.ncbi_gene_id) if r.ncbi_gene_id is not None else "",
                        r.ensembl_canonical_protein or "",
                        str(r.in_db_union),
                        r.triage_verdict or "",
                        r.selection_reason,
                        r.stable_id_source,
                        str(r.needs_review),
                    ]
                )
                + "\n"
            )


def main() -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--topology-version", required=True, help="e.g. topo_2026_05_16"
    )
    ap.add_argument(
        "--candidate-universe-tsv",
        type=Path,
        default=DEFAULT_CANDIDATE_UNIVERSE_TSV,
    )
    ap.add_argument(
        "--triage-run-id",
        default=DEFAULT_TRIAGE_RUN_ID,
        help=f"triage_run.run_id to read verdicts from (default: {DEFAULT_TRIAGE_RUN_ID})",
    )
    ap.add_argument(
        "--override-hgnc-ids",
        type=str,
        default="",
        help="Comma-separated HGNC IDs to use INSTEAD of the union, for "
             "verification runs. Each ID is looked up in gene_identifier.",
    )
    ap.add_argument(
        "--skip-d1",
        action="store_true",
        help="Skip the triage_run query (offline dry runs). gene_identifier "
             "is still required from D1.",
    )
    args = ap.parse_args()

    override = [s.strip() for s in args.override_hgnc_ids.split(",") if s.strip()]
    rows = build_candidate_rows(
        candidate_universe_tsv=args.candidate_universe_tsv,
        triage_run_id=args.triage_run_id,
        override_hgnc_ids=override or None,
        skip_d1=args.skip_d1,
    )

    out_dir = Path("data/processed") / f"topology_run_{args.topology_version}"
    out_path = out_dir / "candidate_accessions.tsv"
    write_candidate_tsv(out_path, rows)

    by_reason: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    for r in rows:
        by_reason[r.selection_reason] = by_reason.get(r.selection_reason, 0) + 1
        by_source[r.stable_id_source] = by_source.get(r.stable_id_source, 0) + 1
        key = r.triage_verdict or "_no_triage"
        by_verdict[key] = by_verdict.get(key, 0) + 1
    logger.info("wrote %d rows to %s", len(rows), out_path)
    logger.info("by selection_reason: %s", by_reason)
    logger.info("by stable_id_source: %s", by_source)
    logger.info("by triage_verdict:   %s", by_verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
