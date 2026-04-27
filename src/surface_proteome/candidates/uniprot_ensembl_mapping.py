"""Shared helper for ENSG / ENSP → UniProt primary accession mapping.

Loads the two long tables emitted by
``src/surface_proteome/candidates/download_uniprot_ensembl_xrefs.py`` (one row per
Ensembl-ID / UniProt-primary pair across the full reviewed human proteome)
and returns plain ``dict[str, list[str]]`` lookup tables. Lists (rather
than scalars) handle the rare one-to-many case where a single Ensembl ID
legitimately maps to multiple UniProt primaries.

Used by:

- ``src/surface_proteome/candidates/build_hpa.py`` (ENSG → UP)
- ``src/surface_proteome/candidates/build_jensenlab_compartments.py`` (ENSP → UP)
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd


def _load_pair_tsv(path: Path, id_col: str) -> dict[str, list[str]]:
    """Read a two-column mapping TSV into ``{ensembl_id: [uniprot_primary, ...]}``."""
    mapping: dict[str, list[str]] = defaultdict(list)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Ensembl xref mapping at {path}. Run "
            "`uv run python -m surface_proteome.candidates.download_uniprot_ensembl_xrefs` first."
        )
    df = pd.read_csv(path, sep="\t", dtype=str, usecols=[id_col, "uniprot_accession"])
    for eid, acc in zip(df[id_col].fillna(""), df["uniprot_accession"].fillna("")):
        if not eid or not acc:
            continue
        lst = mapping[eid]
        if acc not in lst:
            lst.append(acc)
    return dict(mapping)


def load_ensembl_mapping(
    xref_dir: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load both mappings from ``xref_dir`` and return ``(ensg, ensp)``.

    Raises ``FileNotFoundError`` if either file is missing.
    """
    ensg_path = xref_dir / "ensg_to_uniprot.tsv"
    ensp_path = xref_dir / "ensp_to_uniprot.tsv"
    ensg_map = _load_pair_tsv(ensg_path, "ensembl_gene_id")
    ensp_map = _load_pair_tsv(ensp_path, "ensembl_protein_id")
    return ensg_map, ensp_map


def map_to_uniprot(
    ensembl_ids: pd.Series,
    mapping: dict[str, list[str]],
) -> tuple[pd.Series, pd.Series]:
    """Attach a list-of-primaries column to each Ensembl ID.

    Returns ``(primaries_list, n_primaries)`` — the first a Series of lists
    (empty when the ID is unmapped), the second a Series of ints for quick
    filtering on mapped/ambiguous rows. Caller is responsible for
    exploding and flagging ``split_mapping_ambiguous`` rows.
    """
    primaries = ensembl_ids.map(lambda e: list(mapping.get(str(e).strip(), [])))
    n_primaries = primaries.map(len)
    return primaries, n_primaries
