"""Normalize the HPA subcellular_location.tsv snapshot for the M1 merge.

Scoped to **therapeutic-delivery-relevant surface annotations** (ADC /
CAR-T / mRNA-LNP targeting). See the companion report
``docs/reports/2026-04-17-hpa-therapeutic-delivery-refinement.md`` for
the design rationale and the Codex-review findings that motivated it.

Input:
- ``data/external/hpa_subcellular_location/subcellular_location.tsv``
  (fetched by ``download_hpa_subcellular_location.py``; v25.0, 13,603 rows)
- ``data/external/uniprot_ensembl_xrefs/ensg_to_uniprot.tsv``
  (fetched by ``download_uniprot_ensembl_xrefs.py``)

Output: ``data/processed/hpa/hpa_human_snapshot.tsv`` — one row per
(UniProt primary accession, ENSG) pair, restricted to the
**surface-candidate pool**.

Pool admission (row is kept in the snapshot) — mirrors how ``_load_surfy``
drops non-surface rows before the merge:

- "Plasma membrane" in ``Main location`` / ``Additional location``, OR
- "Cell Junctions" in ``Main location`` / ``Additional location`` — ADC-
  accessible epithelial junction proteins (cadherins, claudins, JAM,
  occludin, desmosomal cadherins) have legitimate extracellular domains
  and would otherwise be under-represented at M1, OR
- Non-empty ``Extracellular location`` — retained for provenance only
  (secreted predictions; flag=0 unless corroborated by PM/junction).

Focal adhesion, Vesicles, Endosomes, Lysosomes **alone** do NOT admit a
row to the pool — those are the ABCB9-class false positives the project
was built to avoid. When they co-occur with PM or junction evidence they
are surfaced via ``hpa_trafficking_associated = 1`` for downstream LLM
adjudication.

Flag rule (``hpa_surface_flag = 1``) — uses per-tier PM/junction
reliability, NOT the gene-wide ``Reliability`` column (which can report
e.g. "Supported" for a gene whose strong localization is nuclear while
the PM call lands only in ``Uncertain``):

    hpa_surface_flag = (hpa_pm_accessible == 1 OR hpa_junctional == 1)

with

    hpa_pm_accessible  = PM appears in Enhanced / Supported / Approved tier
    hpa_junctional     = Cell Junctions appears in Enhanced / Supported / Approved tier

Secreted-only rows (non-empty ``Extracellular location`` with no PM and
no junction evidence) are explicitly **not flagged** — HPA's
"Extracellular location" column is populated entirely by
"Predicted to be secreted" (sequence-based, not IF evidence), so every
row there is a signal-peptide prediction recapitulated, not an
experimental surface call. Secreted-only rows stay in the pool with
``hpa_secreted_only = 1`` for provenance.

Per-row derived columns (emitted verbatim as provenance):

- **Per-tier PM booleans**: ``hpa_pm_in_{enhanced,supported,approved,uncertain}``
- **Per-tier junction booleans**: ``hpa_cj_in_{enhanced,supported,approved,uncertain}``
- **Summaries**: ``hpa_pm_reliability``, ``hpa_junction_reliability``
  — enum {"enhanced","supported","approved","uncertain",""} picked from
  the highest tier where the respective location appears
- **States for downstream LLM pipeline**: ``hpa_pm_accessible``,
  ``hpa_junctional``, ``hpa_secreted_only``,
  ``hpa_trafficking_associated``
- **Gene-wide**: ``hpa_reliability``, ``hpa_low_confidence_only``
  (1 iff in pool but ``hpa_surface_flag = 0``), ``hpa_locations``,
  ``hpa_go_ids``
- **Split-mapping ambiguity**: ``hpa_split_mapping_ambiguous``
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from accessible_surfaceome.candidates.traceability import (
    sha256_file,
    utc_now_iso,
)
from accessible_surfaceome.candidates.uniprot_ensembl_mapping import (
    load_ensembl_mapping,
)

from accessible_surfaceome.paths import REPO_ROOT as ROOT

DATASET = "hpa"
HPA_INPUT_TSV = (
    ROOT / "data" / "external" / "hpa_subcellular_location"
    / "subcellular_location.tsv"
)
ENSEMBL_XREF_DIR = ROOT / "data" / "external" / "uniprot_ensembl_xrefs"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "hpa"
OUTPUT_TSV = "hpa_human_snapshot.tsv"
SUMMARY_JSON = "hpa_build_summary.json"
MANIFEST_JSON = "hpa_build_traceability.json"

GO_ID_RE = re.compile(r"GO:\d{7}")

TIER_COLS = ("Enhanced", "Supported", "Approved", "Uncertain")
TIER_KEYS = ("enhanced", "supported", "approved", "uncertain")
FLAG_ELIGIBLE_TIER_KEYS = ("enhanced", "supported", "approved")

TRAFFICKING_LOCATIONS = {"Vesicles", "Endosomes", "Lysosomes"}


def _has_location(value: str, target: str) -> bool:
    """Return True iff any semicolon-separated token in ``value`` equals ``target``."""
    if not isinstance(value, str) or not value:
        return False
    return any(p.strip() == target for p in value.split(";"))


def _has_any_location(value: str, targets: set[str]) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return any(p.strip() in targets for p in value.split(";"))


def _combine_locations(row: pd.Series) -> str:
    """Semicolon-joined union of Main + Additional + Extracellular (deduped)."""
    out: list[str] = []
    seen: set[str] = set()
    for col in ("Main location", "Additional location", "Extracellular location"):
        value = row.get(col, "")
        if not isinstance(value, str):
            continue
        for part in value.split(";"):
            p = part.strip()
            if not p or p in seen:
                continue
            seen.add(p)
            out.append(p)
    return ";".join(out)


def _extract_go_ids(value: str) -> str:
    if not isinstance(value, str) or not value:
        return ""
    ids = sorted(set(GO_ID_RE.findall(value)))
    return "|".join(ids)


def _derive_per_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Derive per-tier PM + Cell Junctions booleans from HPA tier columns."""
    for tier_col, tier_key in zip(TIER_COLS, TIER_KEYS, strict=True):
        df[f"hpa_pm_in_{tier_key}"] = df[tier_col].map(
            lambda v, _l="Plasma membrane": _has_location(v, _l)
        ).astype(int)
        df[f"hpa_cj_in_{tier_key}"] = df[tier_col].map(
            lambda v, _l="Cell Junctions": _has_location(v, _l)
        ).astype(int)
    return df


def _best_tier(row: pd.Series, prefix: str) -> str:
    for tier_key in TIER_KEYS:
        if row.get(f"{prefix}_in_{tier_key}", 0) == 1:
            return tier_key
    return ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-tsv", type=Path, default=HPA_INPUT_TSV)
    p.add_argument("--xref-dir", type=Path, default=ENSEMBL_XREF_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    input_path: Path = args.input_tsv
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(
            f"HPA input missing: {input_path}. Run "
            "`uv run python -m accessible_surfaceome.candidates.download_hpa_subcellular_location` first."
        )

    print(f"reading {input_path.relative_to(ROOT)} ...")
    df = pd.read_csv(input_path, sep="\t", dtype=str).fillna("")
    print(f"  {len(df):,} input rows")

    required = {"Gene", "Gene name", "Reliability",
                "Main location", "Additional location", "Extracellular location",
                "Enhanced", "Supported", "Approved", "Uncertain",
                "GO id"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"HPA column drift; missing: {sorted(missing)}")

    ensg_map, _ensp_map = load_ensembl_mapping(args.xref_dir)
    print(f"  loaded ENSG mapping ({len(ensg_map):,} ENSGs → UniProt)")

    df["hpa_reliability"] = df["Reliability"].str.strip()

    # Per-tier PM and Cell Junctions evidence.
    df = _derive_per_tier(df)

    # Raw per-row provenance flags.
    df["hpa_has_extracellular"] = (df["Extracellular location"].str.strip() != "").astype(int)
    df["hpa_trafficking_associated"] = (
        df["Main location"].map(
            lambda v, _t=TRAFFICKING_LOCATIONS: _has_any_location(v, _t)
        )
        | df["Additional location"].map(
            lambda v, _t=TRAFFICKING_LOCATIONS: _has_any_location(v, _t)
        )
    ).astype(int)

    # Per-tier-summary reliabilities.
    df["hpa_pm_reliability"] = df.apply(lambda r: _best_tier(r, "hpa_pm"), axis=1)
    df["hpa_junction_reliability"] = df.apply(
        lambda r: _best_tier(r, "hpa_cj"), axis=1
    )

    # State columns.
    df["hpa_pm_accessible"] = (
        (df["hpa_pm_in_enhanced"] == 1)
        | (df["hpa_pm_in_supported"] == 1)
        | (df["hpa_pm_in_approved"] == 1)
    ).astype(int)
    df["hpa_junctional"] = (
        (df["hpa_cj_in_enhanced"] == 1)
        | (df["hpa_cj_in_supported"] == 1)
        | (df["hpa_cj_in_approved"] == 1)
    ).astype(int)
    df["hpa_has_pm_any_tier"] = (
        df["hpa_pm_accessible"] | (df["hpa_pm_in_uncertain"] == 1)
    ).astype(int)
    df["hpa_has_cj_any_tier"] = (
        df["hpa_junctional"] | (df["hpa_cj_in_uncertain"] == 1)
    ).astype(int)
    df["hpa_secreted_only"] = (
        (df["hpa_has_extracellular"] == 1)
        & (df["hpa_has_pm_any_tier"] == 0)
        & (df["hpa_has_cj_any_tier"] == 0)
    ).astype(int)

    df["hpa_locations"] = df.apply(_combine_locations, axis=1)
    df["hpa_go_ids"] = df["GO id"].map(_extract_go_ids)

    # Flag rule: PM-accessible OR junctional at Enhanced/Supported/Approved
    # tier. Secreted-only rows stay in the pool but do NOT set the flag
    # (HPA "Extracellular location" = "Predicted to be secreted" =
    # sequence-based prediction, not IF evidence). Trafficking-associated
    # rows ride alongside PM/junction evidence and contribute only when
    # PM or CJ also passes.
    df["hpa_surface_flag"] = (
        (df["hpa_pm_accessible"] == 1) | (df["hpa_junctional"] == 1)
    ).astype(int)

    # Pool filter: PM or CJ evidence at any tier, or secreted (provenance).
    # Trafficking-associated ALONE does not admit — that's the ABCB9
    # false-positive class the project is explicitly avoiding.
    n_pre_pool_filter = len(df)
    pool_mask = (
        (df["hpa_has_pm_any_tier"] == 1)
        | (df["hpa_has_cj_any_tier"] == 1)
        | (df["hpa_has_extracellular"] == 1)
    )
    df = df[pool_mask].copy()
    n_dropped_non_surface = int(n_pre_pool_filter - len(df))

    # Low-confidence-only: in pool but not flagged. Includes:
    # - Secreted-only rows (predicted-secretion provenance, no intact-cell signal)
    # - PM/CJ rows that appear only in the Uncertain tier
    df["hpa_low_confidence_only"] = (df["hpa_surface_flag"] == 0).astype(int)

    df = df.rename(columns={"Gene": "ensembl_gene_id", "Gene name": "hpa_gene_symbol"})

    # Map ENSG → UniProt primary.
    df["_primaries"] = df["ensembl_gene_id"].map(
        lambda e: list(ensg_map.get(str(e).strip(), []))
    )
    n_total_input = len(df)
    df["_n_primaries"] = df["_primaries"].map(len)
    n_unmapped = int((df["_n_primaries"] == 0).sum())
    n_split = int((df["_n_primaries"] >= 2).sum())
    df["hpa_split_mapping_ambiguous"] = (df["_n_primaries"] >= 2).astype(int)

    df_mapped = df[df["_n_primaries"] >= 1].copy()
    df_mapped = df_mapped.explode("_primaries").reset_index(drop=True)
    df_mapped["uniprot_accession"] = df_mapped["_primaries"].astype(str)
    df_mapped = df_mapped.drop(columns=["_primaries", "_n_primaries"])

    out_cols = [
        "uniprot_accession",
        "ensembl_gene_id",
        "hpa_gene_symbol",
        "hpa_reliability",
        # Core flag + low-confidence gate
        "hpa_surface_flag",
        "hpa_low_confidence_only",
        # Therapeutic-delivery-relevant state columns
        "hpa_pm_accessible",
        "hpa_junctional",
        "hpa_secreted_only",
        "hpa_trafficking_associated",
        # Per-tier PM booleans
        "hpa_pm_in_enhanced",
        "hpa_pm_in_supported",
        "hpa_pm_in_approved",
        "hpa_pm_in_uncertain",
        # Per-tier junction booleans
        "hpa_cj_in_enhanced",
        "hpa_cj_in_supported",
        "hpa_cj_in_approved",
        "hpa_cj_in_uncertain",
        # Tier summaries
        "hpa_pm_reliability",
        "hpa_junction_reliability",
        # Raw provenance
        "hpa_has_extracellular",
        "hpa_locations",
        "hpa_go_ids",
        # Split-mapping ambiguity
        "hpa_split_mapping_ambiguous",
    ]
    df_out = df_mapped[out_cols].sort_values(
        ["uniprot_accession", "ensembl_gene_id"]
    ).reset_index(drop=True)

    output_tsv = out_dir / OUTPUT_TSV
    df_out.to_csv(output_tsv, sep="\t", index=False)

    summary = {
        "generated_at_utc": utc_now_iso(),
        "source_file": str(input_path.relative_to(ROOT)),
        "source_sha256": sha256_file(input_path),
        "source_size_bytes": input_path.stat().st_size,
        "n_input_rows_total": int(n_pre_pool_filter),
        "n_dropped_non_surface_pool": int(n_dropped_non_surface),
        "n_input_rows_after_pool_filter": int(n_total_input),
        "pool_filter_rule": (
            "keep row iff has PM in any tier OR has Cell Junctions in any tier "
            "OR Extracellular location is non-empty"
        ),
        "flag_rule": (
            "hpa_surface_flag = (hpa_pm_accessible OR hpa_junctional); "
            "hpa_pm_accessible = PM in Enhanced/Supported/Approved tier; "
            "hpa_junctional    = Cell Junctions in Enhanced/Supported/Approved tier"
        ),
        "n_unmapped_ensg": int(n_unmapped),
        "n_split_ensg_rows": int(n_split),
        "n_output_rows": int(len(df_out)),
        "n_unique_primaries": int(df_out["uniprot_accession"].nunique()),
        "reliability_counts": {
            str(k): int(v) for k, v in df["hpa_reliability"].value_counts(dropna=False).items()
        },
        "n_surface_flag": int(df_out["hpa_surface_flag"].sum()),
        "n_pm_accessible": int(df_out["hpa_pm_accessible"].sum()),
        "n_junctional": int(df_out["hpa_junctional"].sum()),
        "n_secreted_only": int(df_out["hpa_secreted_only"].sum()),
        "n_trafficking_associated": int(df_out["hpa_trafficking_associated"].sum()),
        "n_low_confidence_only": int(df_out["hpa_low_confidence_only"].sum()),
        "n_split_mapping_ambiguous": int(df_out["hpa_split_mapping_ambiguous"].sum()),
        "pm_reliability_counts": {
            str(k): int(v)
            for k, v in df_out["hpa_pm_reliability"].value_counts(dropna=False).items()
        },
        "junction_reliability_counts": {
            str(k): int(v)
            for k, v in df_out["hpa_junction_reliability"].value_counts(dropna=False).items()
        },
    }
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(ROOT).as_posix(),
        "source": {
            "local_path": str(input_path.relative_to(ROOT)),
            "sha256": sha256_file(input_path),
            "size_bytes": input_path.stat().st_size,
            "license": "CC-BY-SA-3.0",
        },
        "ensembl_xref_mapping": {
            "local_path": str((args.xref_dir / "ensg_to_uniprot.tsv").relative_to(ROOT)),
            "sha256": sha256_file(args.xref_dir / "ensg_to_uniprot.tsv"),
            "size_bytes": (args.xref_dir / "ensg_to_uniprot.tsv").stat().st_size,
        },
        "outputs": {
            OUTPUT_TSV: {
                "local_path": str(output_tsv.relative_to(ROOT)),
                "sha256": sha256_file(output_tsv),
                "size_bytes": output_tsv.stat().st_size,
                "n_rows": int(len(df_out)),
                "primary_key": "uniprot_accession + ensembl_gene_id (ENSG retained for provenance)",
            },
        },
        "derived_columns": [
            {"name": "hpa_pm_in_{tier}", "rule": "1 iff 'Plasma membrane' appears in the HPA '{tier}' column"},
            {"name": "hpa_cj_in_{tier}", "rule": "1 iff 'Cell Junctions' appears in the HPA '{tier}' column"},
            {"name": "hpa_pm_reliability", "rule": "highest tier (enhanced > supported > approved > uncertain) where PM appears, or ''"},
            {"name": "hpa_junction_reliability", "rule": "highest tier where Cell Junctions appears, or ''"},
            {"name": "hpa_pm_accessible", "rule": "1 iff PM is in Enhanced/Supported/Approved tier"},
            {"name": "hpa_junctional", "rule": "1 iff Cell Junctions is in Enhanced/Supported/Approved tier"},
            {"name": "hpa_secreted_only", "rule": "1 iff 'Extracellular location' is non-empty AND no PM/CJ evidence at any tier; HPA 'Extracellular location' is populated only by 'Predicted to be secreted' (SignalP-based), not IF evidence"},
            {"name": "hpa_trafficking_associated", "rule": "1 iff any of {Vesicles, Endosomes, Lysosomes} appears in Main/Additional location"},
            {"name": "hpa_surface_flag", "rule": "hpa_pm_accessible OR hpa_junctional"},
            {"name": "hpa_low_confidence_only", "rule": "1 iff hpa_surface_flag == 0 (row is in pool but not flagged; covers secreted-only and PM/CJ-only-in-Uncertain-tier cases)"},
            {"name": "hpa_split_mapping_ambiguous", "rule": "1 iff the source ENSG mapped to >=2 UniProt primaries"},
        ],
        "excluded_from_flag": [
            {"signal": "Extracellular location",
             "rule": "column is entirely populated by 'Predicted to be secreted' — a SignalP-based sequence prediction, not an HPA IF observation. Rows with only this signal (hpa_secreted_only == 1) stay in pool for provenance but do NOT set hpa_surface_flag"},
            {"signal": "Vesicles / Endosomes / Lysosomes",
             "rule": "carried via hpa_trafficking_associated for downstream LLM-stage adjudication; ABCB9-class false positives where these compartments appear as the ONLY signal are excluded from the pool entirely (no PM, no CJ)"},
            {"signal": "Focal adhesion sites",
             "rule": "inner-leaflet scaffold; not extracellularly accessible on intact cells; no pool admission"},
        ],
    }
    (out_dir / MANIFEST_JSON).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {output_tsv.relative_to(ROOT)}  ({len(df_out):,} rows, "
          f"{df_out['uniprot_accession'].nunique():,} unique UP primaries)")
    print(f"  unmapped ENSGs: {n_unmapped:,}  split-ambiguous rows: {n_split:,}")
    print(f"  n_surface_flag={summary['n_surface_flag']:,}  "
          f"n_pm_accessible={summary['n_pm_accessible']:,}  "
          f"n_junctional={summary['n_junctional']:,}  "
          f"n_secreted_only={summary['n_secreted_only']:,}  "
          f"n_trafficking_associated={summary['n_trafficking_associated']:,}")


if __name__ == "__main__":
    main()
