"""Gene-symbol consolidation + MyGene resolution for the merged universe.

The seven sources each carry their own gene-symbol field
(``surfy_gene_symbol``, ``cspa_gene_symbol``, ...). After the outer
merge each row may have several of these populated; ``consolidate_gene_symbol``
picks the first non-empty in a fixed priority order, and
``resolve_gene_symbols_with_mygene`` then sends the union of those symbols
to MyGene for canonicalization (alias / previous-symbol normalization,
ambiguity flagging).
"""

from __future__ import annotations

import mygene
import pandas as pd


def consolidate_gene_symbol(row: pd.Series) -> str:
    for col in (
        "gene_primary",
        "surfy_gene_symbol",
        "cspa_gene_symbol",
        "go_gene_symbol",
        "hpa_gene_symbol",
        "compartments_gene_symbol",
    ):
        val = row.get(col)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _as_upper_list(value: object) -> list[str]:
    """Normalize a scalar/list value into uppercase string tokens."""
    if value is None:
        return []
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]
    return [
        str(item).strip().upper()
        for item in raw_values
        if str(item).strip()
    ]


def resolve_gene_symbols_with_mygene(
    symbols: list[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Resolve gene symbols with a single MyGene batch query (no fallback).

    Resolver statuses intentionally mirror the nomenclature statuses used in
    the tess/coral resolver stack:
    - ``exact``
    - ``normalized_alias``
    - ``normalized_previous``
    - ``ambiguous``
    - ``not_found``
    """
    if not symbols:
        empty = pd.DataFrame(
            columns=[
                "gene_symbol_query",
                "gene_symbol_resolved",
                "gene_symbol_mapping_status",
                "gene_symbol_mygene_score",
            ]
        )
        return empty, {
            "n_query_symbols": 0,
            "n_exact": 0,
            "n_normalized_alias": 0,
            "n_normalized_previous": 0,
            "n_ambiguous": 0,
            "n_not_found": 0,
        }

    mg = mygene.MyGeneInfo()
    try:
        raw_hits = mg.querymany(
            symbols,
            scopes="symbol,alias,prev_symbol",
            fields="symbol,alias,prev_symbol",
            species="human",
            as_dataframe=False,
            returnall=False,
            verbose=False,
        )
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        raise RuntimeError(
            "MyGene symbol resolution failed for candidate-universe merge "
            "(no fallback configured)."
        ) from exc

    hits_by_query: dict[str, list[dict[str, object]]] = {}
    for raw in raw_hits:
        if not isinstance(raw, dict):
            continue
        query = str(raw.get("query", "")).strip().upper()
        if not query:
            continue
        hits_by_query.setdefault(query, []).append(raw)

    def _candidate(hit: dict[str, object], query: str) -> tuple[int, float, str, str] | None:
        symbol = str(hit.get("symbol", "")).strip().upper()
        if not symbol:
            return None
        score_value = hit.get("_score", 0.0)
        score = float(score_value) if isinstance(score_value, str | int | float) else 0.0
        aliases = set(_as_upper_list(hit.get("alias")))
        prev_symbols = set(_as_upper_list(hit.get("prev_symbol")))
        if symbol == query:
            return (0, score, symbol, "exact")
        if query in prev_symbols:
            return (1, score, symbol, "normalized_previous")
        if query in aliases:
            return (2, score, symbol, "normalized_alias")
        return None

    records: list[dict[str, object]] = []
    for query in symbols:
        candidates: list[tuple[int, float, str, str]] = []
        for hit in hits_by_query.get(query, []):
            if hit.get("notfound"):
                continue
            parsed = _candidate(hit, query)
            if parsed is not None:
                candidates.append(parsed)

        if not candidates:
            records.append(
                {
                    "gene_symbol_query": query,
                    "gene_symbol_resolved": "",
                    "gene_symbol_mapping_status": "not_found",
                    "gene_symbol_mygene_score": 0.0,
                }
            )
            continue

        best_rank = min(rank for rank, _score, _symbol, _status in candidates)
        best_rank_rows = [row for row in candidates if row[0] == best_rank]
        best_score = max(score for _rank, score, _symbol, _status in best_rank_rows)
        best_rows = [
            row for row in best_rank_rows if abs(row[1] - best_score) < 1e-12
        ]
        best_symbols = sorted({symbol for _rank, _score, symbol, _status in best_rows})

        if len(best_symbols) > 1:
            records.append(
                {
                    "gene_symbol_query": query,
                    "gene_symbol_resolved": "",
                    "gene_symbol_mapping_status": "ambiguous",
                    "gene_symbol_mygene_score": float(best_score),
                }
            )
            continue

        chosen = sorted(
            best_rows,
            key=lambda row: (row[0], -row[1], row[2]),
        )[0]
        _rank, score, symbol, status = chosen
        records.append(
            {
                "gene_symbol_query": query,
                "gene_symbol_resolved": symbol,
                "gene_symbol_mapping_status": status,
                "gene_symbol_mygene_score": float(score),
            }
        )

    result = pd.DataFrame.from_records(records).sort_values("gene_symbol_query")
    mapping_counts = (
        result["gene_symbol_mapping_status"].value_counts(dropna=False).to_dict()
    )
    stats = {
        "n_query_symbols": len(symbols),
        "n_exact": int(mapping_counts.get("exact", 0)),
        "n_normalized_alias": int(mapping_counts.get("normalized_alias", 0)),
        "n_normalized_previous": int(mapping_counts.get("normalized_previous", 0)),
        "n_ambiguous": int(mapping_counts.get("ambiguous", 0)),
        "n_not_found": int(mapping_counts.get("not_found", 0)),
    }
    return result, stats
