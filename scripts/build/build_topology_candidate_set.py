"""Build the topology-sweep candidate set keyed on HGNC ID.

Driven from PR #30's ``gene_identifier`` D1 table — the canonical
HGNC-ID-keyed source of truth for every protein-coding gene (19,464 rows
at HEAD, 100% coverage of the M1 cohort). We iterate **HGNC IDs**, not
symbols. Symbol-keyed legacy data sources are translated to HGNC IDs
through ``gene_identifier.cohort_symbol`` — the resolver's snapshot of
what symbol the cohort had at build time, which is the only legitimate
join with ``triage_run.gene_symbol`` and ``candidate_universe.tsv``.

The candidate set is the union of:

  (a) ``candidate_universe.tsv`` with ``in_db_union = 1`` — i.e. any of
      the 5 gating surface databases voted "yes" under that source's
      optimized cutoff (see ``merge/__init__.py:GATING_FLAG_COLUMNS``;
      cutoffs are baked into each per-source loader).
  (b) ``triage_run.predicted_verdict IN ('yes', 'contextual')`` for the
      latest genome-wide Sonnet run.

Output: ``data/processed/topology_run_<version>/candidate_accessions.tsv``,
keyed on ``hgnc_id``, carrying every stable identifier ``gene_identifier``
exposes plus the (in_db_union, triage_verdict, selection_reason) audit
columns.

Usage::

    uv run python scripts/build_topology_candidate_set.py \\
        --topology-version topo_2026_05_16

Verification override — by HGNC ID, not symbol::

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
class GeneIdentifier:
    """One row from D1's ``gene_identifier`` — the HGNC-keyed canonical record."""

    hgnc_id: str
    hgnc_symbol: str
    cohort_symbol: str | None
    uniprot_acc: str | None
    ncbi_gene_id: int | None
    ensembl_gene: str | None
    ensembl_canonical_protein: str | None
    resolver_version: str
    needs_review: int


@dataclass(frozen=True)
class CandidateRow:
    """One row of the candidate accessions TSV — HGNC-keyed."""

    hgnc_id: str
    hgnc_symbol: str
    cohort_symbol: str
    uniprot_acc: str            # required — DeepTMHMM input
    ensembl_gene: str | None
    ncbi_gene_id: int | None
    ensembl_canonical_protein: str | None
    in_db_union: int
    triage_verdict: str | None  # 'yes' | 'contextual' | None
    selection_reason: str       # db_only | triage_only | both | override
    needs_review: int           # mirrored from gene_identifier
    resolver_version: str


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
        timeout=120,
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


def _load_gene_identifier_cohort(*, client: httpx.Client) -> dict[str, GeneIdentifier]:
    """Load ``gene_identifier`` keyed by HGNC ID — the cohort universe.

    This is the **primary key** of the pipeline. Every candidate row, every
    upload row, every join in topology_public / compara_paralog is anchored
    on the HGNC IDs in this dict. The 19,464-row cohort here corresponds
    1:1 with ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv``.
    """
    account, db, token = _from_env_agents()
    rows = _d1_query(
        account,
        db,
        token,
        "SELECT hgnc_id, hgnc_symbol, cohort_symbol, uniprot_acc, "
        "ncbi_gene_id, ensembl_gene, ensembl_canonical_protein, "
        "resolver_version, needs_review "
        "FROM gene_identifier",
        client=client,
    )
    out: dict[str, GeneIdentifier] = {}
    for r in rows:
        hid = (r.get("hgnc_id") or "").strip()
        if not hid:
            continue
        out[hid] = GeneIdentifier(
            hgnc_id=hid,
            hgnc_symbol=(r.get("hgnc_symbol") or "").strip(),
            cohort_symbol=(r.get("cohort_symbol") or None) or None,
            uniprot_acc=(r.get("uniprot_acc") or None) or None,
            ncbi_gene_id=(int(r["ncbi_gene_id"]) if r.get("ncbi_gene_id") else None),
            ensembl_gene=(r.get("ensembl_gene") or None) or None,
            ensembl_canonical_protein=(r.get("ensembl_canonical_protein") or None) or None,
            resolver_version=(r.get("resolver_version") or "").strip(),
            needs_review=int(r.get("needs_review") or 0),
        )
    return out


def _build_symbol_to_hgnc_index(
    cohort: dict[str, GeneIdentifier],
) -> dict[str, str]:
    """Build symbol → hgnc_id lookup for translating legacy symbol-keyed sources.

    Both ``cohort_symbol`` and ``hgnc_symbol`` map to the same HGNC ID
    (one HGNC ID per gene). When a free-text symbol matches via either
    path it resolves to that HGNC ID. Symbol-collision (two HGNC IDs
    sharing a primary symbol — rare, the resolver bug class PR #30 fixed)
    is broken by keeping the first match and warning; the pipeline never
    silently picks the wrong gene.
    """
    sym_to_hgnc: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for hid, gi in cohort.items():
        for sym_raw in (gi.hgnc_symbol, gi.cohort_symbol):
            if not sym_raw:
                continue
            sym = sym_raw.strip().upper()
            if not sym:
                continue
            if sym in sym_to_hgnc and sym_to_hgnc[sym] != hid:
                collisions.setdefault(sym, [sym_to_hgnc[sym]]).append(hid)
                continue
            sym_to_hgnc[sym] = hid
    if collisions:
        logger.warning(
            "symbol collisions in gene_identifier (kept first match): %d affected",
            len(collisions),
        )
        # Log first few so they're auditable but don't flood.
        for sym, hids in list(collisions.items())[:5]:
            logger.warning("  %s → %s (extra: %s)", sym, hids[0], hids[1:])
    return sym_to_hgnc


def _load_db_yes_hgnc_ids(
    tsv: Path, *, sym_to_hgnc: dict[str, str]
) -> set[str]:
    """Translate ``candidate_universe.tsv`` in_db_union=1 rows → set of HGNC IDs.

    Each row in candidate_universe.tsv carries a gene_symbol_resolved (M1
    merge's resolver output at build time). We map that symbol back to
    its hgnc_id via the gene_identifier cohort. Rows whose symbol doesn't
    resolve are logged and dropped — they're the resolver-drift cases
    PR #30's fix-run already addressed.
    """
    if not tsv.exists():
        raise SystemExit(f"candidate_universe.tsv not found at {tsv}")
    db_yes: set[str] = set()
    n_seen = 0
    n_unresolved = 0
    unresolved_examples: list[str] = []
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            in_db_union = (r.get("in_db_union") or "").strip()
            if in_db_union not in {"1", "1.0", "true", "True"}:
                continue
            n_seen += 1
            sym = (
                r.get("gene_symbol_resolved") or r.get("gene_symbol") or ""
            ).strip().upper()
            if not sym:
                continue
            hid = sym_to_hgnc.get(sym)
            if hid is None:
                n_unresolved += 1
                if len(unresolved_examples) < 10:
                    unresolved_examples.append(sym)
                continue
            db_yes.add(hid)
    logger.info(
        "candidate_universe in_db_union=1: %d rows, %d resolved to HGNC, "
        "%d unresolved (examples: %s)",
        n_seen, len(db_yes), n_unresolved, unresolved_examples,
    )
    return db_yes


def _load_triage_yes_hgnc_ids(
    *,
    client: httpx.Client,
    run_id: str,
    sym_to_hgnc: dict[str, str],
) -> dict[str, str]:
    """Translate triage 'yes'/'contextual' rows → ``{hgnc_id: verdict}``.

    COALESCE-merges with the ``<run_id>__resolver_v3_fix`` rerun (per
    CLAUDE.md's "Working with the D1 databases" → run_id conventions
    section). For genes that the resolver v3 audit re-ran with the
    corrected gene assignment, the FIX verdict wins. Otherwise we use
    the original. This drops the ~3 fix-run verdict changes from the
    candidate set:

      * GPHRB:  yes        → no          (drops from set)
      * SOFU1:  no         → contextual  (adds to set)
      * WAS:    contextual → no          (drops from set)

    Join with gene_identifier is on ``cohort_symbol = triage_run.gene_symbol`` —
    the resolver's snapshot of the input symbol at cohort build time.
    """
    account, db, token = _from_env_agents()
    rows = _d1_query(
        account,
        db,
        token,
        # COALESCE with __resolver_v3_fix run; filter to yes/contextual.
        # The fix run only has rows for genes that needed re-resolution
        # (45 genes), so most rows fall through to the original verdict.
        f"SELECT t.gene_symbol AS gene_symbol, "
        f"       COALESCE(f.predicted_verdict, t.predicted_verdict) AS predicted_verdict "
        f"FROM triage_run t "
        f"LEFT JOIN triage_run f "
        f"  ON f.gene_symbol = t.gene_symbol "
        f"  AND f.run_id = '{run_id}__resolver_v3_fix' "
        f"WHERE t.run_id = '{run_id}' "
        f"  AND COALESCE(f.predicted_verdict, t.predicted_verdict) IN ('yes', 'contextual') "
        f"  AND t.gene_symbol IS NOT NULL AND t.gene_symbol != ''",
        client=client,
    )
    out: dict[str, str] = {}
    n_unresolved = 0
    unresolved_examples: list[str] = []
    for r in rows:
        sym = (r.get("gene_symbol") or "").strip().upper()
        verdict = (r.get("predicted_verdict") or "").strip()
        if not sym or verdict not in TRIAGE_YES_VERDICTS:
            continue
        hid = sym_to_hgnc.get(sym)
        if hid is None:
            n_unresolved += 1
            if len(unresolved_examples) < 10:
                unresolved_examples.append(sym)
            continue
        existing = out.get(hid)
        # 'yes' wins over 'contextual' if a gene has both verdicts (shouldn't,
        # but be defensive).
        if existing is None or (existing == "contextual" and verdict == "yes"):
            out[hid] = verdict
    logger.info(
        "triage yes+contextual: %d rows from D1, %d resolved to HGNC, "
        "%d unresolved (examples: %s)",
        len(rows), len(out), n_unresolved, unresolved_examples,
    )
    return out


def _build_from_override_hgnc_ids(
    hgnc_ids: list[str],
    *,
    cohort: dict[str, GeneIdentifier],
) -> list[CandidateRow]:
    """Build rows from explicit HGNC IDs (dry-run / verification path)."""
    rows: list[CandidateRow] = []
    for hid in hgnc_ids:
        gi = cohort.get(hid)
        if gi is None:
            logger.warning("override HGNC ID %s not in gene_identifier — skipping", hid)
            continue
        if not gi.uniprot_acc:
            logger.warning("override HGNC ID %s has no uniprot_acc — skipping", hid)
            continue
        rows.append(
            CandidateRow(
                hgnc_id=gi.hgnc_id,
                hgnc_symbol=gi.hgnc_symbol,
                cohort_symbol=(gi.cohort_symbol or gi.hgnc_symbol),
                uniprot_acc=gi.uniprot_acc,
                ensembl_gene=gi.ensembl_gene,
                ncbi_gene_id=gi.ncbi_gene_id,
                ensembl_canonical_protein=gi.ensembl_canonical_protein,
                in_db_union=0,
                triage_verdict=None,
                selection_reason="override",
                needs_review=gi.needs_review,
                resolver_version=gi.resolver_version,
            )
        )
    return rows


def build_candidate_rows(
    *,
    candidate_universe_tsv: Path,
    triage_run_id: str,
    override_hgnc_ids: list[str] | None,
    skip_d1_triage: bool,
) -> list[CandidateRow]:
    """Drive from HGNC IDs in gene_identifier, then union DB-yes + triage-yes/contextual."""
    with httpx.Client(timeout=120) as client:
        cohort = _load_gene_identifier_cohort(client=client)
        logger.info("gene_identifier cohort loaded: %d HGNC IDs", len(cohort))

        if override_hgnc_ids:
            return _build_from_override_hgnc_ids(override_hgnc_ids, cohort=cohort)

        sym_to_hgnc = _build_symbol_to_hgnc_index(cohort)
        logger.info(
            "symbol → HGNC index: %d entries (covers both hgnc_symbol and cohort_symbol)",
            len(sym_to_hgnc),
        )

        db_yes_hgnc = _load_db_yes_hgnc_ids(
            candidate_universe_tsv, sym_to_hgnc=sym_to_hgnc
        )

        triage_yc: dict[str, str] = {}
        if not skip_d1_triage:
            try:
                triage_yc = _load_triage_yes_hgnc_ids(
                    client=client, run_id=triage_run_id, sym_to_hgnc=sym_to_hgnc
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("triage query failed (DB-only set): %s", exc)

    # The candidate set is the union, iterated over HGNC IDs.
    all_hids = sorted(db_yes_hgnc | set(triage_yc))
    rows: list[CandidateRow] = []
    n_dropped_no_uniprot = 0
    n_not_in_cohort = 0

    for hid in all_hids:
        gi = cohort.get(hid)
        if gi is None:
            # Impossible — by construction every hid here came from gene_identifier.
            n_not_in_cohort += 1
            continue
        if not gi.uniprot_acc:
            # Resolver couldn't pick a UniProt accession (e.g. HGNC gene with
            # no Swiss-Prot xref). DeepTMHMM has nothing to predict on.
            n_dropped_no_uniprot += 1
            continue

        in_db = hid in db_yes_hgnc
        triage_verdict = triage_yc.get(hid)
        if in_db and triage_verdict is not None:
            reason = "both"
        elif in_db:
            reason = "db_only"
        else:
            reason = "triage_only"

        rows.append(
            CandidateRow(
                hgnc_id=hid,
                hgnc_symbol=gi.hgnc_symbol,
                cohort_symbol=(gi.cohort_symbol or gi.hgnc_symbol),
                uniprot_acc=gi.uniprot_acc,
                ensembl_gene=gi.ensembl_gene,
                ncbi_gene_id=gi.ncbi_gene_id,
                ensembl_canonical_protein=gi.ensembl_canonical_protein,
                in_db_union=int(in_db),
                triage_verdict=triage_verdict,
                selection_reason=reason,
                needs_review=gi.needs_review,
                resolver_version=gi.resolver_version,
            )
        )

    logger.info(
        "candidate set: %d rows (dropped: %d HGNC IDs missing from cohort, "
        "%d with no resolved uniprot_acc)",
        len(rows), n_not_in_cohort, n_dropped_no_uniprot,
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
        "needs_review",
        "resolver_version",
    ]
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write(
                "\t".join(
                    [
                        r.hgnc_id,
                        r.hgnc_symbol,
                        r.cohort_symbol,
                        r.uniprot_acc,
                        r.ensembl_gene or "",
                        str(r.ncbi_gene_id) if r.ncbi_gene_id is not None else "",
                        r.ensembl_canonical_protein or "",
                        str(r.in_db_union),
                        r.triage_verdict or "",
                        r.selection_reason,
                        str(r.needs_review),
                        r.resolver_version,
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
        "--skip-d1-triage",
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
        skip_d1_triage=args.skip_d1_triage,
    )

    out_dir = Path("data/processed") / f"topology_run_{args.topology_version}"
    out_path = out_dir / "candidate_accessions.tsv"
    write_candidate_tsv(out_path, rows)

    by_reason: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    n_needs_review = 0
    for r in rows:
        by_reason[r.selection_reason] = by_reason.get(r.selection_reason, 0) + 1
        key = r.triage_verdict or "_no_triage"
        by_verdict[key] = by_verdict.get(key, 0) + 1
        if r.needs_review:
            n_needs_review += 1
    logger.info("wrote %d rows to %s", len(rows), out_path)
    logger.info("by selection_reason: %s", by_reason)
    logger.info("by triage_verdict:   %s", by_verdict)
    logger.info("needs_review flagged: %d", n_needs_review)
    return 0


if __name__ == "__main__":
    sys.exit(main())
