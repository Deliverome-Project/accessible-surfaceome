"""Resolve a gene symbol (or passthrough HGNC id) to a stable HGNC id via the
cohort TSV, honoring the CLAUDE.md stable-identifier rule."""

from __future__ import annotations

import csv
import functools
import re
from pathlib import Path

from accessible_surfaceome.env import REPO_ROOT

_HGNC_RE = re.compile(r"^HGNC:\d+$")
_DEFAULT_COHORT = (
    REPO_ROOT
    / "data"
    / "external"
    / "ncbi_gene_info"
    / "Homo_sapiens.protein_coding.with_hgnc.tsv"
)


@functools.lru_cache(maxsize=8)
def _load_hgnc_map(path_str: str) -> dict[str, str]:
    path = Path(path_str)
    if not path.exists():
        raise LookupError(
            f"cohort TSV not found at {path}; run scripts/bootstrap-worktree.sh candidate"
        )
    mapping: dict[str, str] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            # Real cohort TSV keys the symbol as `gene_symbol`; `symbol` is a
            # fallback for lighter-weight fixtures.
            symbol = (row.get("gene_symbol") or row.get("symbol") or "").strip().upper()
            hid = (row.get("hgnc_id") or "").strip()
            if symbol and hid and symbol not in mapping:
                mapping[symbol] = hid
    return mapping


def resolve_hgnc_id(symbol_or_hgnc: str, *, cohort_tsv: Path | None = None) -> str:
    token = symbol_or_hgnc.strip()
    if _HGNC_RE.match(token):
        return token

    path = cohort_tsv or _DEFAULT_COHORT
    mapping = _load_hgnc_map(str(path.resolve()))
    hid = mapping.get(token.upper())
    if hid:
        return hid
    raise LookupError(f"no hgnc_id for symbol {symbol_or_hgnc!r} in {path}")
