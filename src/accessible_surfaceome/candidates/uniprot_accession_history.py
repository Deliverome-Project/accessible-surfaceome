"""Shared helpers for applying UniProt accession-history reconciliation.

Parses the canonical reference files fetched by
``src/accessible_surfaceome/candidates/download_uniprot_accession_history.py``:

- ``sec_ac.txt``    — secondary → primary accession map
- ``delac_sp.txt``  — deleted Swiss-Prot accessions

Used by:

- ``accessible_surfaceome.reports.audit`` (audit)
- ``src/accessible_surfaceome/candidates/merge.py`` (merge normalization)
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

# UniProt accession regex (Swiss-Prot + TrEMBL long-form).
# https://www.uniprot.org/help/accession_numbers
UNIPROT_ACCESSION_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)


def parse_sec_ac(path: Path) -> dict[str, list[str]]:
    """Parse ``sec_ac.txt`` into ``{secondary_accession: [primary, ...]}``.

    sec_ac.txt structure: header block, then a table under column headers
    ``Secondary AC / Primary AC`` separated from data by a line of
    underscores. Each data line has one secondary and one primary
    accession; the same secondary can appear on multiple lines if the
    original entry was later split into several current primaries.
    """
    mapping: dict[str, list[str]] = defaultdict(list)
    in_data = False
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not in_data:
                if line.startswith("_" * 4):
                    in_data = True
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            sec, prim = parts
            if not (
                UNIPROT_ACCESSION_RE.match(sec)
                and UNIPROT_ACCESSION_RE.match(prim)
            ):
                continue
            mapping[sec].append(prim)
    return dict(mapping)


def parse_delac_sp(path: Path) -> set[str]:
    """Parse ``delac_sp.txt`` into a set of deleted Swiss-Prot accessions."""
    deleted: set[str] = set()
    in_data = False
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not in_data:
                if line.startswith("_" * 4):
                    in_data = True
                continue
            if line.startswith("-" * 4):
                # Trailing license / footer block starts with dashes.
                break
            if not line:
                continue
            if UNIPROT_ACCESSION_RE.match(line):
                deleted.add(line)
    return deleted


def load_accession_history(history_dir: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Load sec_ac + delac_sp from ``history_dir`` and return (sec_ac, delac_sp).

    Raises ``FileNotFoundError`` if either file is missing.
    """
    sec_ac_path = history_dir / "sec_ac.txt"
    delac_sp_path = history_dir / "delac_sp.txt"
    if not sec_ac_path.exists() or not delac_sp_path.exists():
        raise FileNotFoundError(
            f"Missing accession-history files under {history_dir}. Run "
            "`uv run python -m accessible_surfaceome.candidates.download_uniprot_accession_history` first."
        )
    return parse_sec_ac(sec_ac_path), parse_delac_sp(delac_sp_path)
