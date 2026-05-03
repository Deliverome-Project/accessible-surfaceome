"""Reconcile per-source UniProt accessions against the current history.

Each source's accessions are rewritten with the current UniProt
accession-history reference (``sec_ac.txt`` + ``delac_sp.txt``) before
the merge keys on ``uniprot_accession``. ``_normalize_accessions`` is
the single point where deleted, secondary, and split-mapping accessions
are resolved; the per-row provenance carried out (``split_mapping_ambiguous``)
lets the merge orchestrator quarantine ambiguous remaps without losing
the underlying evidence.
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd


class NormalizeStats(TypedDict):
    source: str
    input_rows: int
    deleted_rows_dropped: int
    secondary_rows_rewritten: int
    split_duplications: int
    output_rows: int


def normalize_accessions(
    df: pd.DataFrame,
    *,
    sec_ac: dict[str, list[str]],
    delac_sp: set[str],
    source_name: str,
    agg_override: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, NormalizeStats]:
    """Rewrite secondary UniProt accessions to their current primaries.

    - Deleted Swiss-Prot accessions are dropped.
    - Secondary accessions are replaced by the current primary. If UniProt
      has split an old entry into multiple primaries, the row is duplicated
      once per primary and each derived row carries
      ``split_mapping_ambiguous = 1`` so downstream can distinguish
      "confident remap" from "one-of-N possible descendants" (the old
      annotation applies to at most one of the derived entries, not all).
    - Rows that collapse onto the same primary are aggregated. Default
      reducers are ``max`` for numeric columns and ``first`` for strings;
      pass ``agg_override`` to replace the reducer for specific columns
      (used for CSPA to preserve categorical semantics).
    - ``split_mapping_ambiguous`` uses ``min`` so a primary gains the
      ambiguous flag only if *every* pre-collapse row reaching it came
      from a split remap (any confident pre-collapse row clears the
      flag).

    Returns the normalized DataFrame plus a stats dict for traceability.
    """
    key = "uniprot_accession"
    df = df.copy()
    df[key] = df[key].astype(str).str.strip()

    n_in = len(df)
    n_deleted = int(df[key].isin(delac_sp).sum())
    df = df[~df[key].isin(delac_sp)].copy()

    is_secondary = df[key].isin(sec_ac)
    n_secondary_rows = int(is_secondary.sum())

    df["_primaries"] = df[key].map(lambda a: sec_ac.get(a, [a]))
    df["_primary_count"] = df["_primaries"].map(len)
    n_split_rewrites = int(
        df.loc[is_secondary, "_primaries"].map(len).sum() - n_secondary_rows
    )
    # Mark every explosion of a split accession (one secondary → 2+ primaries)
    # as ambiguous BEFORE the explode + groupby collapse.
    df["split_mapping_ambiguous"] = (df["_primary_count"] >= 2).astype(int)
    df = df.explode("_primaries").reset_index(drop=True)
    df[key] = df["_primaries"].astype(str)
    df = df.drop(columns=["_primaries", "_primary_count"])

    agg: dict[str, object] = {}
    for col in df.columns:
        if col == key:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            agg[col] = "max"
        else:
            agg[col] = "first"
    # ``min`` so only primaries whose every contributing row was itself
    # ambiguous keep the flag; a confident (non-split) remap clears it.
    agg["split_mapping_ambiguous"] = "min"
    if agg_override:
        agg.update(agg_override)
    collapsed = df.groupby(key, as_index=False).agg(agg)

    stats: NormalizeStats = {
        "source": source_name,
        "input_rows": int(n_in),
        "deleted_rows_dropped": int(n_deleted),
        "secondary_rows_rewritten": int(n_secondary_rows),
        "split_duplications": int(n_split_rewrites),
        "output_rows": int(len(collapsed)),
    }
    return collapsed, stats
