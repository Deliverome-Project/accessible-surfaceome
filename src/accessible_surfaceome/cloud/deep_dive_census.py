"""Read-only post-run census across the deep-dive's persistence surfaces.

A multi-day Modal sweep writes each gene to up to four places, and they can
drift independently (see ``scripts/deep_dive_sweep.annotate_one``):

1. **Volume JSON** — ``<annotations_dir>/<run_id>/<symbol>.json``, the canonical
   artifact (pulled back with ``modal volume get``).
2. **Private D1** ``deep_dive_run`` parent + ``deep_dive_evidence`` /
   ``deep_dive_search_log`` children.
3. **Public D1** ``surface_annotation`` — what the Worker serves to the viewer.

(The committed ``viewer/public/data`` snapshot is **deliberately out of scope**:
public D1 is the live serving source; snapshots are regenerated from Volume JSON
only at release checkpoints, not per-run.)

The existing point tools each reconcile *one* pair —
``deep_dive_audit.find_orphans`` (private parent ↔ children),
``deep_dive_json_backfill`` (Volume JSON → private parent),
``upload_viewer_snapshots_to_d1`` (JSON → public D1). This module is the
**single read-only reconciler** that joins all of them against the intended
cohort and classifies every gene, so one command answers "is this run
trustworthy, and what's the worst problem per gene?". It does **not** repair —
the operator runs the matching point tool for each drift class
(``status`` names the class).

The reconciliation core (:func:`build_census`) is a pure function over plain
dicts so it is unit-testable without D1; the thin D1/​disk readers live below it
and in ``scripts/deep_dive_census.py``.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_audit import find_orphans

# Status classes, worst-first. Each non-ok class names the point tool the
# operator runs to repair it (see ``REPAIR_HINT``). ``status`` reports the
# single highest-priority problem so the matrix stays one-line-per-gene.
STATUS_OK = "ok"
STATUS_MISSING = "missing"  # never completed anywhere — resume, not drift
STATUS_QUARANTINED = "quarantined"  # over-cap abort — manual review, no auto-resume
STATUS_ORPHAN_CHILDREN = "orphan_children"
STATUS_PRIVATE_MISSING = "private_missing"
STATUS_PUBLIC_MISSING = "public_missing"
STATUS_PUBLIC_STALE = "public_stale"
STATUS_JSON_MISSING = "json_missing"
STATUS_UNEXPECTED = "unexpected"  # on a surface but not in the cohort gene-list

# Drift = landed unevenly / inconsistently across surfaces. These fail the gate
# and each has a repair path. ``missing`` is coverage (safe resume), not drift.
DRIFT_STATUSES = frozenset(
    {
        STATUS_ORPHAN_CHILDREN,
        STATUS_PRIVATE_MISSING,
        STATUS_PUBLIC_MISSING,
        STATUS_PUBLIC_STALE,
        STATUS_JSON_MISSING,
    }
)

REPAIR_HINT: dict[str, str] = {
    STATUS_ORPHAN_CHILDREN: "scripts/audit_deep_dive_orphans.py --execute",
    STATUS_PRIVATE_MISSING: "scripts/backfill_deep_dive_from_json.py --execute",
    STATUS_PUBLIC_MISSING: "scripts/upload_viewer_snapshots_to_d1.py --execute",
    STATUS_PUBLIC_STALE: "scripts/upload_viewer_snapshots_to_d1.py --execute",
    STATUS_JSON_MISSING: "re-pull the Volume (modal volume get) — canonical JSON absent",
    STATUS_MISSING: "resume the sweep (full_sweep) — gene never completed",
    STATUS_QUARANTINED: (
        "MANUAL REVIEW — over per-gene cost cap; re-run deliberately with "
        "--include-quarantined (e.g. raised ceiling), never auto-resumed"
    ),
    STATUS_UNEXPECTED: "gene on a surface but not in --gene-list; check the cohort file",
}


@dataclass(frozen=True)
class GeneCensus:
    """One gene's presence across the three gate surfaces.

    ``children_complete`` / ``public_schema_current`` are tri-state: ``None``
    means "not applicable / not determinable" (e.g. no private parent to count
    children for; public not checked because creds were absent).
    """

    gene_symbol: str
    in_cohort: bool
    in_volume_json: bool
    in_private: bool
    in_public: bool
    children_complete: bool | None
    public_schema_current: bool | None
    json_schema_version: str | None = None
    private_schema_version: str | None = None
    public_schema_version: str | None = None
    public_checked: bool = True
    quarantined: bool = False

    @property
    def status(self) -> str:
        if not self.in_cohort:
            return STATUS_UNEXPECTED
        # Quarantine wins over "missing": an over-cap gene has no record (so it
        # would otherwise read as never-ran), but it is deliberately parked for
        # manual review, not a coverage gap to auto-resume.
        if self.quarantined and not self.in_private:
            return STATUS_QUARANTINED
        if not (self.in_volume_json or self.in_private or self.in_public):
            return STATUS_MISSING
        # Present somewhere — walk the worst-first ladder. The first match is
        # the actionable root cause; repairing it is the operator's next step.
        if self.in_private and self.children_complete is False:
            return STATUS_ORPHAN_CHILDREN
        if self.in_volume_json and not self.in_private:
            return STATUS_PRIVATE_MISSING
        if not self.in_volume_json and (self.in_private or self.in_public):
            # The canonical artifact is gone but derived rows exist — can't
            # repair the others from JSON, so flag it before public checks.
            return STATUS_JSON_MISSING
        if self.public_checked and self.in_private and not self.in_public:
            return STATUS_PUBLIC_MISSING
        if self.public_checked and self.in_public and self.public_schema_current is False:
            return STATUS_PUBLIC_STALE
        return STATUS_OK

    @property
    def is_ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def is_drift(self) -> bool:
        return self.status in DRIFT_STATUSES


def build_census(
    *,
    cohort_symbols: list[str],
    volume: dict[str, str | None],
    private: dict[str, str],
    orphan_symbols: set[str],
    public: dict[str, str] | None,
    quarantined: set[str] | None = None,
) -> list[GeneCensus]:
    """Classify every gene across the cohort and the three surfaces.

    Arguments are plain data so this is pure / unit-testable:

    * ``cohort_symbols`` — the intended gene-list (defines coverage).
    * ``volume`` — ``{symbol: json_schema_version}`` for records on disk
      (value may be ``None`` if the JSON was unreadable but present).
    * ``private`` — ``{symbol: schema_version}`` from ``deep_dive_run``.
    * ``orphan_symbols`` — symbols whose private children are incomplete
      (from :func:`find_orphans`).
    * ``public`` — ``{symbol: schema_version}`` from ``surface_annotation``,
      or ``None`` when public D1 was not checked (creds absent). ``None``
      suppresses the public drift classes rather than falsely flagging every
      gene as ``public_missing``.

    The "expected" schema for the public-currency check is the canonical Volume
    JSON's schema, falling back to the private parent's — i.e. "is the Worker
    serving the same schema the record was written at?".
    """
    public_checked = public is not None
    pub = public or {}
    quarantined = quarantined or set()
    cohort = set(cohort_symbols)
    all_symbols = cohort | set(volume) | set(private) | set(pub)

    out: list[GeneCensus] = []
    for symbol in sorted(all_symbols):
        in_private = symbol in private
        in_public = symbol in pub
        in_volume = symbol in volume
        expected_schema = volume.get(symbol) or private.get(symbol)
        public_schema = pub.get(symbol)
        if not (public_checked and in_public):
            public_current: bool | None = None
        elif expected_schema is None or public_schema is None:
            public_current = None
        else:
            public_current = public_schema == expected_schema
        out.append(
            GeneCensus(
                gene_symbol=symbol,
                in_cohort=symbol in cohort,
                in_volume_json=in_volume,
                in_private=in_private,
                in_public=in_public,
                children_complete=(symbol not in orphan_symbols) if in_private else None,
                public_schema_current=public_current,
                json_schema_version=volume.get(symbol),
                private_schema_version=private.get(symbol),
                public_schema_version=public_schema,
                public_checked=public_checked,
                quarantined=symbol in quarantined,
            )
        )
    return out


def summarize(rows: list[GeneCensus]) -> Counter[str]:
    """Count genes by status class."""
    return Counter(r.status for r in rows)


def exit_code(rows: list[GeneCensus]) -> int:
    """Gate exit code: 0 = all ok, 1 = any drift (must repair), 2 = needs
    attention but no drift (missing → resume, quarantined → manual review,
    or unexpected)."""
    if any(r.is_drift for r in rows):
        return 1
    if any(
        r.status in (STATUS_MISSING, STATUS_QUARANTINED, STATUS_UNEXPECTED)
        for r in rows
    ):
        return 2
    return 0


# --------------------------------------------------------------------------
# Disk + D1 readers (thin; the pure classifier above does the real work)
# --------------------------------------------------------------------------


def load_cohort_symbols(tsv: Path) -> list[str]:
    """Read the intended-cohort gene symbols from a TSV.

    Accepts the same shape as ``deep_dive_sweep.load_gene_list`` (``hgnc_symbol``
    or ``gene_symbol`` column) but lives here, in the installed package, so the
    CLI never has to import the non-package ``scripts/`` directory (that import
    only resolves under Modal's container path, not ``python scripts/...``).
    """
    out: list[str] = []
    with tsv.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            symbol = (row.get("hgnc_symbol") or row.get("gene_symbol") or "").strip()
            if symbol:
                out.append(symbol)
    return out


def scan_volume_json(run_dir: Path) -> dict[str, str | None]:
    """Map ``{symbol: schema_version}`` for every record JSON in a run dir.

    Keyed on the record's ``gene.hgnc_symbol`` (authoritative — matches the D1
    key), falling back to the filename stem. Reads the ``schema_version`` field
    directly without full Pydantic validation — fast over thousands of files;
    an unreadable/invalid file maps to ``None`` (still counts as present).
    """
    out: dict[str, str | None] = {}
    if not run_dir.exists():
        return out
    for path in sorted(run_dir.glob("*.json")):
        try:
            blob = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            out[path.stem] = None
            continue
        gene = blob.get("gene") if isinstance(blob, dict) else None
        symbol = (gene or {}).get("hgnc_symbol") if isinstance(gene, dict) else None
        out[symbol or path.stem] = (
            blob.get("schema_version") if isinstance(blob, dict) else None
        )
    return out


def private_parents(d1: D1Client, run_id: str) -> dict[str, str]:
    """Map ``{symbol: schema_version}`` for ``deep_dive_run`` parents."""
    rows = d1.query(
        "SELECT gene_symbol, schema_version FROM deep_dive_run WHERE run_id = ?;",
        [run_id],
    )
    return {str(r["gene_symbol"]): str(r["schema_version"]) for r in rows}


def orphan_symbols(d1: D1Client, run_id: str) -> set[str]:
    """Symbols whose private children are incomplete (reuses the orphan audit)."""
    return {o.gene_symbol for o in find_orphans(d1, run_id)}


def public_schema_versions(d1_public: D1Client, symbols: list[str]) -> dict[str, str]:
    """Map ``{symbol: latest schema_version}`` from public ``surface_annotation``.

    Chunked ``IN`` lists keep each statement well under D1's bind-variable
    limit. When a gene has rows at multiple ``schema_version`` values (a
    republish at a new schema left the old row), the lexicographically greatest
    is taken as current — matching the Worker's ``ORDER BY schema_version DESC``.
    """
    out: dict[str, str] = {}
    chunk = 100
    for start in range(0, len(symbols), chunk):
        batch = symbols[start : start + chunk]
        placeholders = ",".join("?" for _ in batch)
        rows = d1_public.query(
            f"SELECT gene_symbol, schema_version FROM surface_annotation "
            f"WHERE gene_symbol IN ({placeholders});",
            list(batch),
        )
        for r in rows:
            sym = str(r["gene_symbol"])
            ver = str(r["schema_version"])
            if sym not in out or ver > out[sym]:
                out[sym] = ver
    return out


__all__ = [
    "DRIFT_STATUSES",
    "REPAIR_HINT",
    "GeneCensus",
    "build_census",
    "exit_code",
    "load_cohort_symbols",
    "orphan_symbols",
    "private_parents",
    "public_schema_versions",
    "scan_volume_json",
    "summarize",
]
