"""Build the Supp Fig 15 deep-dive concordance TSV from the frozen record bundle.

The bundle (``data/processed/deep_dive_concordance_v1/``) freezes three record
sets for the same 50 randomly sampled deep-dive genes (two disjoint batches of
25, seeds 20260927 and 20260928):

* ``published.jsonl.gz`` — the public records as served on 2026-09-27
  (``/v1/genes/{sym}`` + ``/evidence``), i.e. run ``cu_v3_sonnet_2026_06``;
* ``full_rerun.jsonl.gz`` — a from-scratch re-annotation with identical prompts
  (run ``deep_dive_concordance_v1``, private D1 only — never published);
* ``fixed_evidence_replay.jsonl.gz`` — builders + synthesizer re-run on each
  published run's own evidence ledger (retrieval and selection held fixed).

Freezing them makes the figure reproducible even after the live records are
republished. This script writes ``data/processed/figures/deep_dive_replicate_kappa.tsv``
— one row per gene per comparison (``comparison`` = ``full_rerun`` or
``fixed_evidence_replay``, so 100 rows), carrying stable identifiers plus, for
each field, the published value, the re-analysed value (``*_reanalysis``) and
hard / soft match flags. One TSV, because each figure gist bundles exactly one.

Run::

    uv run python scripts/build/build_deep_dive_concordance_tsvs.py
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

from accessible_surfaceome.release.catalog_presets import deep_dive_tier

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data/processed/deep_dive_concordance_v1"
OUT_DIR = ROOT / "data/processed/figures"
PUBLISHED_RUN = "cu_v3_sonnet_2026_06"
RERUN_RUN = "deep_dive_concordance_v1"

ORDINAL: dict[str, list[str]] = {
    "surface_accessibility": ["no", "low", "moderate", "high"],
    "confidence": ["low", "moderate", "high"],
    "state_dependence": ["low", "moderate", "high"],
    "evidence_grade": ["weak", "supportive_but_indirect", "direct_single_method",
                       "direct_multi_method"],
    "surface_specificity": ["mostly_intracellular", "mixed", "surface_dominant"],
    "expression_breadth": ["rare", "restricted", "broad", "pan_tissue"],
    "expression_level": ["absent", "low", "moderate", "high"],
}
SURFACE_REASONS = {
    "classical_surface_receptor", "multipass_with_exposed_loops", "gpi_anchored",
    "stable_complex_partner", "extracellular_face_protein", "tissue_restricted_surface",
    "cell_state_induced", "dual_localization", "stable_surface_attachment",
    "lysosomal_exocytosis",
}
NONSURFACE_REASONS = {
    "secreted_only", "endomembrane_resident", "cytoplasmic", "inner_leaflet_anchored",
    "nuclear", "mitochondrial_internal", "nuclear_envelope", "pmhc_only_intracellular",
}
SUBCAT_GROUP = {"single_pass_T1": "single_pass", "single_pass_T2": "single_pass",
                "multi_pass": "multipass", "GPCR": "multipass", "tetraspanin": "multipass"}
BOOLEANS = [
    "has_live_cell_surface_evidence", "tumor_associated", "has_shed_form",
    "has_secreted_form", "has_epitope_masking", "has_known_ligand",
    "has_restricted_subdomain", "overexpression_surface_localization_observed",
    "low_endogenous_expression",
]
# The three of the viewer's 24 LLM facets that live outside ``filters``.
NESTED: dict[str, tuple[str, ...]] = {
    "primary_compartment": ("biological_context", "subcellular_localization",
                            "primary_compartment"),
    "restricted_subdomain_kind": ("accessibility_risks", "restricted_subdomain", "domain"),
    "secreted_form_source": ("accessibility_risks", "secreted_form", "source"),
}
FIELDS = [*ORDINAL, "surface_call_reason", "induction_trigger", "subcategory",
          "llm_family", "co_receptor_dependency", *BOOLEANS, *NESTED]
POSITIVE = {"canonical", "likely"}


def value(rec: dict[str, Any], field: str) -> Any:
    if field in NESTED:
        node: Any = rec
        for key in NESTED[field]:
            node = node.get(key) if isinstance(node, dict) else None
        return node
    return rec["filters"].get(field)


def soft_match(field: str, a: Any, b: Any) -> bool:
    """Lenient agreement: adjacent ordinal level, same surface side, etc."""
    if a == b:
        return True
    if field in ORDINAL:
        scale = ORDINAL[field]
        return a in scale and b in scale and abs(scale.index(a) - scale.index(b)) <= 1
    if field == "surface_call_reason":
        return (a in SURFACE_REASONS and b in SURFACE_REASONS) or (
            a in NONSURFACE_REASONS and b in NONSURFACE_REASONS)
    if field == "induction_trigger":
        return (a == "none") == (b == "none")
    if field == "subcategory":
        return SUBCAT_GROUP.get(a, a) == SUBCAT_GROUP.get(b, b)
    return False


def cited(rec: dict[str, Any]) -> set[str]:
    return {
        (span.get("source") or {}).get("source_id")
        for ev in rec.get("evidence") or []
        for span in ev.get("spans", [])
        if (span.get("source") or {}).get("source_id")
    }


def load(name: str) -> dict[str, tuple[int, dict[str, Any]]]:
    with gzip.open(BUNDLE / f"{name}.jsonl.gz", "rt") as fh:
        rows = [json.loads(line) for line in fh]
    return {r["hgnc_symbol"]: (r["sample_batch"], r["record"]) for r in rows}


def compare(published: dict, other: dict, *, comparison: str, run_id: str) -> list[dict[str, Any]]:
    label = "reanalysis"
    out = []
    for sym, (batch, pub) in published.items():
        rec = other[sym][1]
        tp, to = deep_dive_tier(pub["filters"])[0], deep_dive_tier(rec["filters"])[0]
        gene = pub["gene"]
        row: dict[str, Any] = {
            "hgnc_id": gene.get("hgnc_id"), "hgnc_symbol": sym,
            "uniprot_acc": gene.get("uniprot_acc"), "ensembl_gene": gene.get("ensembl_gene"),
            "ncbi_gene_id": gene.get("ncbi_gene_id"), "sample_batch": batch,
            "comparison": comparison,
            "published_run_id": PUBLISHED_RUN, f"{label}_run_id": run_id,
            "tier_published": tp, f"tier_{label}": to,
            "tier_match": tp == to,
            "tier_soft_match": (tp in POSITIVE) == (to in POSITIVE),
        }
        for f in FIELDS:
            a, b = value(pub, f), value(rec, f)
            row[f"{f}_published"], row[f"{f}_{label}"] = a, b
            row[f"{f}_match"] = a == b
            row[f"{f}_soft_match"] = soft_match(f, a, b)
        cp, co = cited(pub), cited(rec)
        row["n_cited_published"], row[f"n_cited_{label}"] = len(cp), len(co)
        row["cited_jaccard"] = round(len(cp & co) / len(cp | co), 3) if (cp | co) else ""
        out.append(row)
    return out


def write(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {path.relative_to(ROOT)}")


def main() -> None:
    published = load("published")
    rows = compare(published, load("full_rerun"), comparison="full_rerun", run_id=RERUN_RUN)
    rows += compare(published, load("fixed_evidence_replay"),
                    comparison="fixed_evidence_replay", run_id=f"{PUBLISHED_RUN}+replay")
    write(rows, OUT_DIR / "deep_dive_replicate_kappa.tsv")


if __name__ == "__main__":
    main()
