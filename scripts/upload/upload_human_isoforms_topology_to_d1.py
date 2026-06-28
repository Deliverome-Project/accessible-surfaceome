"""Sync the human-isoforms DeepTMHMM cohort into ``topology_public`` D1.

The orchestrator's ``_fetch_isoform_topologies`` queries
``WHERE cohort = 'human_isoforms'`` on the ``topology_public`` D1
mirror, but that cohort had never been uploaded — only
``human_canonical`` / ``mouse_ortholog`` / ``cyno_ortholog`` were
synced. As a result every deep-dive record carried
``deterministic_features.isoform_topologies = []``.

This script reads the local DeepTMHMM .3line file for human
isoforms, joins each row against ``gene_identifier_public`` to
recover ``hgnc_id`` + canonical ``gene_symbol``, and bulk-inserts
into both private + public D1 with ``cohort='human_isoforms'``.

Run::

    uv run python scripts/upload_human_isoforms_topology_to_d1.py
    uv run python scripts/upload_human_isoforms_topology_to_d1.py --dry-run
    uv run python scripts/upload_human_isoforms_topology_to_d1.py --public-only

Idempotent on (topology_version, cohort, uniprot_acc_full) via
INSERT OR IGNORE. Safe to re-run after a partial failure.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources.deeptmhmm import parse_3line

logger = logging.getLogger(__name__)

# D1 caps placeholders at ~100 per statement. 24 columns × 4 rows = 96 → batch 4.
BATCH_SIZE = 4
API_ROOT = "https://api.cloudflare.com/client/v4"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
THREE_LINE_PATH = (
    REPO_ROOT
    / "data"
    / "external"
    / "deeptmhmm_surfaceome_predictions"
    / "human_isoforms_from_afdb_non_hla"
    / "predicted_topologies.3line"
)

COHORT = "human_isoforms"
TOPOLOGY_VERSION = "topo_2026_05_16"  # matches the canonical / mouse / cyno cohorts
TOOL_VERSION = "deeptmhmm-1.0.24"
SPECIES = "human"

# Column order matches `scripts/upload_topology_to_d1.py` so the SQL
# statement template is identical between the two sync scripts.
COLS = [
    "topology_version",
    "cohort",
    "hgnc_id",
    "uniprot_acc",
    "uniprot_acc_full",
    "isoform_id",
    "gene_symbol",
    "species",
    "is_canonical",
    "sequence",
    "protein_length",
    "deeptmhmm_label",
    "tm_helix_count",
    "beta_strand_count",
    "n_terminal_orientation",
    "c_terminal_orientation",
    "signal_peptide_length",
    "ecd_length_residues",
    "icd_length_residues",
    "per_residue_topology",
    "predicted_surface_membrane",
    "predicted_secreted",
    "tool_version",
    "retrieved_at",
]


@dataclass(frozen=True)
class D1Target:
    name: str
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def _resolve_targets(*, public_only: bool, private_only: bool) -> list[D1Target]:
    """Return the list of D1 databases to write to.

    Matches the canonical-cohort uploader: by default writes to both
    private (``surfaceome_agents``) and public (``surfaceome_public``)
    so the two stay in sync. ``--public-only`` is the useful path
    for a quick public-mirror fix when the private DB is already up
    to date.
    """
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    agents = os.environ.get("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID", "").strip()
    public = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not account or not token:
        raise SystemExit("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN")
    targets: list[D1Target] = []
    if not public_only and agents:
        targets.append(D1Target("surfaceome_agents", account, agents, token))
    if not private_only and public:
        targets.append(D1Target("surfaceome_public", account, public, token))
    if not targets:
        raise SystemExit(
            "No D1 targets configured. Set "
            "CLOUDFLARE_D1_SURFACEOME_AGENTS_ID and/or "
            "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID."
        )
    return targets


def _fetch_gene_identifier_map() -> dict[str, dict[str, str]]:
    """Build ``uniprot_acc → {hgnc_id, hgnc_symbol}`` from public D1.

    The orchestrator's ``_fetch_isoform_topologies`` filters by
    ``uniprot_acc`` (the BASE accession, not the dashed-isoform), so
    the row needs the canonical ``hgnc_id`` even though it's an
    isoform. We bulk-fetch the whole table (~20k rows, ~2 MB) once
    rather than per-isoform.
    """
    load_env()
    cfg = D1Config(
        account_id=os.environ["CLOUDFLARE_ACCOUNT_ID"],
        database_id=os.environ["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"],
        api_token=os.environ["CLOUDFLARE_API_TOKEN"],
    )
    out: dict[str, dict[str, str]] = {}
    with D1Client(cfg) as d1:
        rows = d1.query(
            "SELECT uniprot_acc, hgnc_id, hgnc_symbol "
            "FROM gene_identifier_public WHERE uniprot_acc IS NOT NULL AND uniprot_acc != '';",
            [],
        )
    for r in rows:
        acc = (r.get("uniprot_acc") or "").strip()
        if not acc:
            continue
        out[acc] = {
            "hgnc_id": (r.get("hgnc_id") or "").strip(),
            "hgnc_symbol": (r.get("hgnc_symbol") or "").strip(),
        }
    return out


def _records_from_3line(
    path: Path,
    *,
    gene_id_map: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Read the .3line file + assemble per-row dicts ready for INSERT.

    The .3line's accession field carries the isoform suffix (e.g.
    ``A0AV02-2``); ``uniprot_acc`` is the bare canonical (``A0AV02``,
    via ``parse_3line``'s ``_split_base_accession``); ``isoform_id``
    is the full dashed form. ``hgnc_id`` and ``gene_symbol`` come
    from the gene-identifier map joined on the bare canonical acc;
    isoforms whose canonical isn't in the map fall back to deriving
    the symbol from the DeepTMHMM entry-name (``S12A8_HUMAN`` →
    ``S12A8``) and ``hgnc_id`` is left empty.
    """
    parsed = parse_3line(path)
    now = datetime.now(UTC).isoformat()
    out: list[dict[str, Any]] = []
    n_missing_hgnc = 0
    for p in parsed:
        acc_full = p["uniprot_accession_full"]
        acc = p["uniprot_accession"]
        entry_name = p["uniprot_entry_name"]
        ident = gene_id_map.get(acc)
        if ident is None:
            n_missing_hgnc += 1
            # Fall back to deriving gene_symbol from the DeepTMHMM
            # entry name suffix (e.g. ``S12A8_HUMAN`` → ``S12A8``).
            # Leave hgnc_id empty; the orchestrator's join is on
            # uniprot_acc, not hgnc_id, so the row remains useful.
            gene_symbol = entry_name.replace("_HUMAN", "")
            hgnc_id = ""
        else:
            gene_symbol = ident["hgnc_symbol"] or entry_name.replace("_HUMAN", "")
            hgnc_id = ident["hgnc_id"]
        out.append({
            "topology_version": TOPOLOGY_VERSION,
            "cohort": COHORT,
            "hgnc_id": hgnc_id,
            "uniprot_acc": acc,
            "uniprot_acc_full": acc_full,
            # ``isoform_id`` is the readable form — keep the dashed
            # full acc so the viewer renders ``A0AV02-2`` (not just
            # ``A0AV02`` which is the canonical alone).
            "isoform_id": acc_full,
            "gene_symbol": gene_symbol,
            "species": SPECIES,
            # All entries in this cohort are alternative isoforms by
            # definition (canonical lives in the human_canonical
            # cohort).
            "is_canonical": 0,
            "sequence": p["sequence"] if "sequence" in p else "",
            "protein_length": int(p["protein_length"]),
            "deeptmhmm_label": p["deeptmhmm_label"],
            "tm_helix_count": int(p["tm_helix_count"]),
            "beta_strand_count": int(p["beta_strand_count"]),
            "n_terminal_orientation": p["n_terminal_orientation"],
            "c_terminal_orientation": p["c_terminal_orientation"],
            "signal_peptide_length": int(p["signal_peptide_length"]),
            "ecd_length_residues": int(p["ecd_length_residues"]),
            "icd_length_residues": int(p["icd_length_residues"]),
            "per_residue_topology": p["per_residue_topology"],
            "predicted_surface_membrane": int(p["predicted_surface_membrane"]),
            "predicted_secreted": int(p["predicted_secreted"]),
            "tool_version": TOOL_VERSION,
            "retrieved_at": now,
        })
    if n_missing_hgnc:
        logger.warning(
            "%d / %d isoform rows have no matching canonical in "
            "gene_identifier_public; hgnc_id will be empty for those "
            "rows (orchestrator join is on uniprot_acc, not hgnc_id, "
            "so this doesn't break the lookup)",
            n_missing_hgnc, len(parsed),
        )
    return out


def _post_batch(
    target: D1Target,
    sql: str,
    params: list[Any],
    *,
    client: httpx.Client,
) -> None:
    """POST one INSERT statement to a D1 target. Raises on error."""
    resp = client.post(
        target.url,
        headers={
            "Authorization": f"Bearer {target.api_token}",
            "Content-Type": "application/json",
        },
        json={"sql": sql, "params": params},
        timeout=60.0,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success", False):
        errors = body.get("errors", [])
        raise RuntimeError(f"D1 INSERT failed on {target.name}: {errors}")


def _parse_3line_record_with_sequence(path: Path) -> list[dict[str, Any]]:
    """Light wrapper that also captures the raw sequence string.

    ``parse_3line`` doesn't return the sequence by default; the column
    is needed for the D1 row. Re-parse the file here keeping the
    sequence so we don't have to modify the shared helper.
    """
    lines = [
        ln.rstrip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    if len(lines) % 3 != 0:
        raise ValueError(f"3line file malformed (not 3-line groups): {path}")
    parsed = parse_3line(path)
    if len(parsed) * 3 != len(lines):
        raise ValueError(
            f"parse_3line row count {len(parsed)} doesn't match "
            f"file row count {len(lines) // 3}"
        )
    for i, p in enumerate(parsed):
        p["sequence"] = lines[i * 3 + 1]
    return parsed


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)-5s %(message)s"
    )
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse + print summary, don't write to D1.")
    ap.add_argument("--public-only", action="store_true",
                    help="Skip the private D1 (write public mirror only).")
    ap.add_argument("--private-only", action="store_true",
                    help="Skip the public D1 (write private only).")
    args = ap.parse_args()

    if not THREE_LINE_PATH.exists():
        raise SystemExit(f"Input .3line missing: {THREE_LINE_PATH}")
    logger.info("reading %s", THREE_LINE_PATH)

    # Patch parse_3line to also capture the sequence — the upstream
    # helper drops the raw sequence string after derivation, but we
    # need it for the D1 column.
    import accessible_surfaceome.sources.deeptmhmm as deeptmhmm_mod
    original_parse = deeptmhmm_mod.parse_3line
    deeptmhmm_mod.parse_3line = _parse_3line_record_with_sequence  # type: ignore[assignment]
    try:
        logger.info("loading gene_identifier_public map…")
        gene_map = _fetch_gene_identifier_map()
        logger.info("  %d canonical → hgnc_id rows", len(gene_map))
        rows = _records_from_3line(THREE_LINE_PATH, gene_id_map=gene_map)
    finally:
        deeptmhmm_mod.parse_3line = original_parse

    logger.info("parsed %d isoform records", len(rows))

    by_label: dict[str, int] = {}
    for r in rows:
        by_label[r["deeptmhmm_label"]] = by_label.get(r["deeptmhmm_label"], 0) + 1
    logger.info("  by deeptmhmm_label: %s", dict(sorted(by_label.items())))

    if args.dry_run:
        logger.info("dry-run — not writing")
        # Spot-check 3 rows
        for r in rows[:3]:
            logger.info(
                "  sample: %s (%s) %s tm=%d ecd_len=%d hgnc=%s",
                r["isoform_id"], r["gene_symbol"], r["deeptmhmm_label"],
                r["tm_helix_count"], r["ecd_length_residues"], r["hgnc_id"] or "—",
            )
        return 0

    targets = _resolve_targets(
        public_only=args.public_only,
        private_only=args.private_only,
    )
    logger.info("writing to: %s", ", ".join(t.name for t in targets))

    cols_csv = ", ".join(COLS)
    placeholders_per_row = "(" + ", ".join(["?"] * len(COLS)) + ")"

    with httpx.Client() as client:
        for target in targets:
            n_written = 0
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                vals_clause = ", ".join([placeholders_per_row] * len(batch))
                sql = (
                    f"INSERT OR IGNORE INTO topology_public ({cols_csv}) "
                    f"VALUES {vals_clause};"
                )
                params: list[Any] = []
                for r in batch:
                    for c in COLS:
                        params.append(r[c])
                _post_batch(target, sql, params, client=client)
                n_written += len(batch)
                if n_written % 200 == 0:
                    logger.info("  %s: %d / %d", target.name, n_written, len(rows))
            logger.info("  %s: %d / %d ✓", target.name, n_written, len(rows))

    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
