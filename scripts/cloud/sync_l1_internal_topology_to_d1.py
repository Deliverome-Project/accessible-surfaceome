"""Sync missing L1 internal-member DeepTMHMM v1 topologies into D1 ``topology_public``.

``scripts/enrich_tag_site_lit.py`` resolves every L1 internal member against
``topology_public`` by exact ``sequence_sha256`` so tag-site coordinates are
always numbered in the member's true protein frame. When new MANE-switched
designed ORFs or GENCODE/Ensembl-named human isoforms are added to L1
(e.g. the Nov 2026 L1 v1 review export), their DeepTMHMM v1 ``.3line`` outputs
exist in ``deliverome-surfaceome-library-v1/library/l1/`` before being synced
back to D1 ``topology_public``.

This script finds every row of ``data/tag_sites/l1_internal_members.tsv`` whose
exact ``sequence_sha256`` is not yet in ``topology_public``, locates the
exact-sha256 ``.3line`` prediction under ``--library-l1-dir``, joins canonical
``hgnc_id`` / ``uniprot_acc`` from ``gene_identifier_public``, and inserts the
missing rows idempotently (``INSERT OR IGNORE``) into both ``surfaceome_agents``
(private) and ``surfaceome_public`` (public).

Usage::

    uv run python scripts/cloud/sync_l1_internal_topology_to_d1.py --dry-run
    uv run python scripts/cloud/sync_l1_internal_topology_to_d1.py
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.agents.tag_site.member_frames import (
    Member,
    load_members,
    resolve_member_frame,
)
from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.sources.deeptmhmm import (
    SURFACE_MEMBRANE_LABELS,
    _count_runs,
    _terminal_state,
    _translate_orientation,
)

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
BATCH_SIZE = 4  # 24 cols * 4 rows = 96 <= D1's 100-parameter cap
TOPOLOGY_VERSION = "topo_2026_11_27_l1_v1_internal"
TOOL_VERSION = "deeptmhmm-1.0.24"
DEFAULT_MEMBERS_TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
DEFAULT_LIBRARY_L1_DIR = (
    REPO_ROOT.parent / "deliverome-surfaceome-library-v1" / "library" / "l1"
)

COLS: tuple[str, ...] = (
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
)


@dataclass(frozen=True)
class ThreeLineEntry:
    """One parsed 3-line DeepTMHMM prediction indexed by exact sequence sha256."""

    header: str
    deeptmhmm_label: str
    sequence: str
    topology: str
    source_path: str

    @property
    def sequence_sha256(self) -> str:
        return hashlib.sha256(self.sequence.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class D1Target:
    name: str
    account_id: str
    database_id: str
    api_token: str

    @property
    def url(self) -> str:
        return f"{API_ROOT}/accounts/{self.account_id}/d1/database/{self.database_id}/query"


def parse_generic_3line(path: Path, *, rel_root: Path | None = None) -> list[ThreeLineEntry]:
    """Parse any DeepTMHMM ``.3line`` file without restricting FASTA header syntax."""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    entries: list[ThreeLineEntry] = []
    rel = str(path.relative_to(rel_root)) if rel_root else str(path)
    for i in range(0, len(lines) - 2, 3):
        hdr, seq, topo = lines[i], lines[i + 1], lines[i + 2]
        if not hdr.startswith(">") or len(seq) != len(topo):
            continue
        label = hdr.rsplit("|", 1)[-1].strip() if "|" in hdr else "TM"
        entries.append(
            ThreeLineEntry(
                header=hdr[1:].strip(),
                deeptmhmm_label=label,
                sequence=seq,
                topology=topo,
                source_path=rel,
            )
        )
    return entries


def index_3line_dir(library_l1_dir: Path) -> dict[str, ThreeLineEntry]:
    """Scan all ``*.3line`` files under ``library_l1_dir`` keyed by sequence sha256."""
    by_sha: dict[str, ThreeLineEntry] = {}
    for p in sorted(library_l1_dir.rglob("*.3line")):
        for entry in parse_generic_3line(p, rel_root=library_l1_dir):
            by_sha.setdefault(entry.sequence_sha256, entry)
    return by_sha


def build_topology_row(
    member: Member,
    entry: ThreeLineEntry,
    *,
    hgnc_id: str | None,
    canonical_uniprot: str | None,
    topology_version: str = TOPOLOGY_VERSION,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Build a ``topology_public`` row dict matching ``upload_topology_to_d1.COLS``."""
    if entry.sequence_sha256 != member.sequence_sha256:
        raise ValueError(
            f"sha256 mismatch for {member.candidate_id}: "
            f"expected {member.sequence_sha256}, got {entry.sequence_sha256}"
        )
    topo = entry.topology
    n_side = _terminal_state(topo, from_n_term=True)
    c_side = _terminal_state(topo, from_n_term=False)
    label = entry.deeptmhmm_label
    uniprot_acc = (
        "l1"
        if member.topology_cohort == "library_designed_orf"
        else (canonical_uniprot or member.topology_acc.split("-", 1)[0])
    )
    return {
        "topology_version": topology_version,
        "cohort": member.topology_cohort,
        "hgnc_id": hgnc_id,
        "uniprot_acc": uniprot_acc,
        "uniprot_acc_full": member.topology_acc,
        "isoform_id": member.topology_acc,
        "gene_symbol": member.gene_symbol,
        "species": member.species,
        "is_canonical": 0,
        "sequence": entry.sequence,
        "protein_length": len(entry.sequence),
        "deeptmhmm_label": label,
        "tm_helix_count": _count_runs(topo, "M"),
        "beta_strand_count": _count_runs(topo, "B"),
        "n_terminal_orientation": _translate_orientation(n_side),
        "c_terminal_orientation": _translate_orientation(c_side),
        "signal_peptide_length": topo.count("S"),
        "ecd_length_residues": topo.count("O"),
        "icd_length_residues": topo.count("I"),
        "per_residue_topology": topo,
        "predicted_surface_membrane": int(label in SURFACE_MEMBRANE_LABELS),
        "predicted_secreted": int(label == "SP"),
        "tool_version": TOOL_VERSION,
        "retrieved_at": retrieved_at or datetime.now(UTC).isoformat(),
    }


def _resolve_targets(*, public_only: bool, private_only: bool) -> list[D1Target]:
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
        raise SystemExit("No D1 targets configured")
    return targets


def _find_missing_members(members: list[Member], *, pub: D1Client) -> list[Member]:
    accs = sorted({m.topology_acc for m in members})
    by_acc: dict[str, list[tuple[str, str, str]]] = {}
    for i in range(0, len(accs), 40):
        chunk = accs[i : i + 40]
        marks = ", ".join(["?"] * len(chunk))
        rows = pub.query(
            f"SELECT uniprot_acc, uniprot_acc_full, sequence, per_residue_topology "
            f"FROM topology_public "
            f"WHERE uniprot_acc IN ({marks}) OR uniprot_acc_full IN ({marks});",
            chunk + chunk,
        )
        for r in rows:
            tup = (r["uniprot_acc_full"], r["sequence"], r["per_residue_topology"])
            for k in {r["uniprot_acc"], r["uniprot_acc_full"]}:
                by_acc.setdefault(k, []).append(tup)
    return [
        m for m in members if resolve_member_frame(m, candidates=by_acc.get(m.topology_acc, [])) is None
    ]


def _gene_ident_map(genes: list[str], *, pub: D1Client) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for i in range(0, len(genes), 50):
        chunk = genes[i : i + 50]
        marks = ", ".join(["?"] * len(chunk))
        rows = pub.query(
            f"SELECT hgnc_symbol, hgnc_id, uniprot_acc FROM gene_identifier_public "
            f"WHERE hgnc_symbol IN ({marks});",
            chunk,
        )
        for r in rows:
            sym = (r.get("hgnc_symbol") or "").strip()
            if sym and sym not in out:
                out[sym] = {
                    "hgnc_id": (r.get("hgnc_id") or "").strip() or None,
                    "uniprot_acc": (r.get("uniprot_acc") or "").strip() or None,
                }
    return out


def _upload_rows(target: D1Target, rows: list[dict[str, Any]], *, client: httpx.Client) -> None:
    cols_sql = ", ".join(COLS)
    one = "(" + ", ".join(["?"] * len(COLS)) + ")"
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i : i + BATCH_SIZE]
        sql = f"INSERT OR IGNORE INTO topology_public ({cols_sql}) VALUES " + ", ".join(
            [one] * len(chunk)
        )
        params: list[Any] = []
        for row in chunk:
            params.extend(row[c] for c in COLS)
        resp = client.post(
            target.url,
            json={"sql": sql, "params": params},
            headers={"Authorization": f"Bearer {target.api_token}"},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"D1 insert failed ({target.name}): {data}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--members-tsv", type=Path, default=DEFAULT_MEMBERS_TSV)
    ap.add_argument("--library-l1-dir", type=Path, default=DEFAULT_LIBRARY_L1_DIR)
    ap.add_argument("--topology-version", default=TOPOLOGY_VERSION)
    ap.add_argument("--public-only", action="store_true")
    ap.add_argument("--private-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    load_env()
    members = load_members(args.members_tsv)
    with D1Client.public() as pub:
        missing = _find_missing_members(members, pub=pub)
        if not missing:
            logger.info("All %d/%d L1 internal members already resolve in topology_public.", len(members), len(members))
            return 0
        id_map = _gene_ident_map(sorted({m.gene_symbol for m in missing}), pub=pub)

    by_sha = index_3line_dir(args.library_l1_dir)
    rows: list[dict[str, Any]] = []
    still_missing: list[Member] = []
    now = datetime.now(UTC).isoformat()
    for m in missing:
        entry = by_sha.get(m.sequence_sha256)
        if entry is None:
            still_missing.append(m)
            continue
        meta = id_map.get(m.gene_symbol, {})
        row = build_topology_row(
            m,
            entry,
            hgnc_id=meta.get("hgnc_id"),
            canonical_uniprot=meta.get("uniprot_acc"),
            topology_version=args.topology_version,
            retrieved_at=now,
        )
        rows.append(row)
        logger.info(
            "  + %s %-8s cohort=%-20s acc_full=%-45s len=%d tm=%d src=%s",
            m.candidate_id,
            m.gene_symbol,
            row["cohort"],
            row["uniprot_acc_full"],
            row["protein_length"],
            row["tm_helix_count"],
            entry.source_path,
        )

    if still_missing:
        logger.error(
            "%d member(s) not found in %s: %s",
            len(still_missing),
            args.library_l1_dir,
            [m.candidate_id for m in still_missing],
        )
        return 1

    targets = _resolve_targets(public_only=args.public_only, private_only=args.private_only)
    logger.info(
        "Prepared %d topology_public row(s) for target(s): %s",
        len(rows),
        [t.name for t in targets],
    )
    if args.dry_run:
        logger.info("DRY RUN — nothing written.")
        return 0

    with httpx.Client() as client:
        for target in targets:
            _upload_rows(target, rows, client=client)
            logger.info("  wrote %d row(s) to %s.topology_public", len(rows), target.name)

    with D1Client.public() as pub:
        remaining = _find_missing_members(members, pub=pub)
    logger.info(
        "Post-sync verification: %d/%d L1 internal members resolve in topology_public (missing=%d).",
        len(members) - len(remaining),
        len(members),
        len(remaining),
    )
    return 0 if not remaining else 1


if __name__ == "__main__":
    sys.exit(main())
