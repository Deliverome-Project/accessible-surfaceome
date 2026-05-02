"""Audit value conflicts in _normalize_accessions collapse groups.

Replays the explode step in ``_normalize_accessions`` without the final
``groupby().agg()`` so we can inspect, per source, every primary
accession that ends up with 2+ pre-collapse rows. For each such group we
flag every column whose values differ across rows — these are the cases
where the generic ``max`` / ``first`` reducer silently resolves
conflicting evidence.

Output: ``data/analysis/cross_source_uniprot_audit/collapse_conflicts.tsv``

Rationale for keeping the current reducers (documented here so future
reviewers can challenge):
- Numeric columns that collapse are ``surfy_ml_score`` and
  ``cspa_is_high_confidence``. ``max`` on ``surfy_ml_score`` yields the
  best allele-level ML score (plan open-question #1). ``max`` on a 0/1
  integer is boolean OR — correct for "any allele is high-confidence".
- String columns that collapse (``cspa_category``, ``cspa_gene_symbol``)
  only do so for HLA entries where the boolean flag is the load-bearing
  column downstream; the string ``first`` pick is cosmetic.

Rerun after any change to loader filters or the collapse reducer.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from surface_proteome.candidates.merge import (
    _best_cspa_category,
    _first_nonempty_symbol,
    _load_compartments,
    _load_cspa,
    _load_deeptmhmm,
    _load_go,
    _load_hpa,
    _load_surfy,
    _load_uniprot,
)
from surface_proteome.candidates.uniprot_accession_history import (
    load_accession_history,
)

ROOT = Path(__file__).resolve().parents[3]

SOURCES = {
    "uniprot": _load_uniprot,
    "go": _load_go,
    "surfy": _load_surfy,
    "cspa": _load_cspa,
    "deeptmhmm": _load_deeptmhmm,
    "hpa": _load_hpa,
    "compartments": _load_compartments,
}

# Mirror of the per-source overrides in build_candidate_universe.main().
# Kept in sync manually; the audit labels the actual reducer used so the
# collapse_conflicts.tsv correctly reflects how a conflict was resolved.
SOURCE_AGG_OVERRIDES: dict[str, dict[str, object]] = {
    "cspa": {
        "cspa_category": _best_cspa_category,
        "cspa_gene_symbol": _first_nonempty_symbol,
    },
    "surfy": {
        "surfy_gene_symbol": _first_nonempty_symbol,
    },
}
OUTPUT_DIR = ROOT / "data" / "analysis" / "cross_source_uniprot_audit"
OUTPUT_TSV = OUTPUT_DIR / "collapse_conflicts.tsv"
HISTORY_DIR = ROOT / "data" / "external" / "uniprot_accession_history"


def _explode(df: pd.DataFrame, sec_ac, delac_sp) -> pd.DataFrame:
    key = "uniprot_accession"
    df = df.copy()
    df[key] = df[key].astype(str).str.strip()
    df = df[~df[key].isin(delac_sp)].copy()
    df["_primaries"] = df[key].map(lambda a: sec_ac.get(a, [a]))
    df = df.explode("_primaries").reset_index(drop=True)
    df[key] = df["_primaries"].astype(str)
    return df.drop(columns=["_primaries"])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sec_ac, delac_sp = load_accession_history(HISTORY_DIR)

    rows: list[dict[str, object]] = []
    for name, loader in SOURCES.items():
        raw = loader()
        exploded = _explode(raw, sec_ac, delac_sp)
        overrides = SOURCE_AGG_OVERRIDES.get(name, {})
        groups = exploded.groupby("uniprot_accession")
        multi = groups.size()
        multi = multi[multi >= 2]
        for acc, n in multi.items():
            g = groups.get_group(acc)
            for col in g.columns:
                if col == "uniprot_accession":
                    continue
                vals = g[col].dropna().unique().tolist()
                if len(vals) <= 1:
                    continue
                is_numeric = bool(pd.api.types.is_numeric_dtype(g[col]))
                if col in overrides:
                    reducer_val = overrides[col]
                    reducer = getattr(reducer_val, "__name__", str(reducer_val))
                else:
                    reducer = "max" if is_numeric else "first"
                rows.append(
                    {
                        "source": name,
                        "primary_accession": acc,
                        "n_pre_collapse_rows": int(n),
                        "column": col,
                        "is_numeric": is_numeric,
                        "reducer": reducer,
                        "n_distinct_values": len(vals),
                        "distinct_values": "|".join(str(v) for v in vals),
                    }
                )

    out = pd.DataFrame(rows, columns=[
        "source", "primary_accession", "n_pre_collapse_rows",
        "column", "is_numeric", "reducer",
        "n_distinct_values", "distinct_values",
    ])
    out.to_csv(OUTPUT_TSV, sep="\t", index=False)
    print(f"wrote {OUTPUT_TSV.relative_to(ROOT)} ({len(out):,} conflict rows)")
    if len(out):
        print(out.groupby(["source", "column", "reducer"]).size().to_string())


if __name__ == "__main__":
    main()
