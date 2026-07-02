"""Export deep-dive record facets from public D1 ``surface_annotation`` to a
committed figure-source TSV.

One row per published gene carrying the ``filters`` facets + a few top-level
fields the deep-dive figures derive from (final-categories buckets, record
richness, triage-vs-deep-dive, the S13 deterministic-features tiers). The
deep-dive figure builders in ``build_figure_tsvs.py`` read THIS TSV, so they
stay offline-reproducible (per tests/test_figure_tsv_reproducible_from_builder).

Re-run after each sweep batch — the figures re-render off the fresh export.
Uses ``json_extract`` in SQL so each row ships ~a few hundred bytes, NOT the
~120 KB annotation_json (pulling the full blob for the whole cohort is the
~145 MB that crashed the D1 isolate memory cap — see PR #104).

Run:
    uv run python scripts/export_deep_dive_figure_source.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/deep_dive/deep_dive_records.tsv"

# (output column, JSON path in annotation_json). Kept small + explicit so the
# query ships only what the figures need.
_FIELDS: list[tuple[str, str]] = [
    ("surface_accessibility", "$.filters.surface_accessibility"),
    ("confidence", "$.filters.confidence"),
    ("subcategory", "$.filters.subcategory"),
    ("state_dependence", "$.filters.state_dependence"),
    ("surface_call_reason", "$.filters.surface_call_reason"),
    ("surface_specificity", "$.filters.surface_specificity"),
    ("induction_trigger", "$.filters.induction_trigger"),
    ("tumor_associated", "$.filters.tumor_associated"),
    ("llm_family", "$.filters.llm_family"),
    ("evidence_grade", "$.filters.evidence_grade"),
    ("evidence_density", "$.filters.evidence_density"),
    ("n_papers_selected", "$.filters.n_papers_selected"),
    ("n_papers_found", "$.filters.n_papers_found"),
    ("expression_breadth", "$.filters.expression_breadth"),
    ("has_shed_form", "$.filters.has_shed_form"),
    ("has_secreted_form", "$.filters.has_secreted_form"),
    ("has_live_cell_surface_evidence", "$.filters.has_live_cell_surface_evidence"),
    ("triage_signal", "$.triage_signal"),
    ("record_confidence", "$.confidence"),
    ("evidence_count", "$.evidence_count"),
    ("primary_evidence_count", "$.primary_evidence_count"),
    ("model_path", "$.model_path"),
]


def _select_sql() -> str:
    cols = ",\n  ".join(
        f"json_extract(annotation_json, '{path}') AS {name}"
        for name, path in _FIELDS
    )
    return (
        "SELECT gene_symbol, uniprot_acc, schema_version,\n  "
        + cols
        + "\nFROM surface_annotation ORDER BY gene_symbol;"
    )


def main() -> int:
    load_env()
    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(_select_sql(), [])
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, sep="\t", index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df)} deep-dive records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
