"""Audit UniProt-accession consistency across the M1 candidate-universe sources.

The candidate-universe merge (``build_candidate_universe.py``) joins seven
sources on base UniProt primary accession. That join assumes every source is
using the *current* UniProt primary accession for the same protein. In
practice old snapshots (SURFY 2018, CSPA 2015) may contain accessions that
UniProt has since merged into another entry (now *secondary* accessions), or
entries that UniProt has since deleted. HPA and JensenLab COMPARTMENTS key
on Ensembl IDs and are pre-mapped to UniProt primary via the
``uniprot_ensembl_xrefs`` snapshot before reaching the merge — the audit
therefore classifies their *mapped* primaries. Either situation would
silently create two merge rows for the same protein.

This audit cross-checks every source accession against the canonical
UniProt accession-history reference files:

- ``sec_ac.txt``   — secondary → primary accession map
- ``delac_sp.txt`` — deleted Swiss-Prot accessions

and classifies each source accession into one of:

- ``primary_current``   — present in our UniProt current snapshot
- ``primary_not_queried`` — valid-looking UniProt accession that is neither
  a secondary nor a deleted SP accession, but is not in the UniProt current
  snapshot either (for example, a reviewed entry that our query filter
  excluded, or a current TrEMBL entry we never fetched)
- ``secondary``         — listed as a secondary AC in ``sec_ac.txt``; maps to
  at least one current primary
- ``deleted_swissprot`` — listed in ``delac_sp.txt`` (entry removed)
- ``unknown``           — none of the above (most likely a deleted TrEMBL
  accession, since we do not fetch ``delac_tr.txt.gz`` by default)

The script also finds **merge-level collisions**: accessions in the
candidate-universe TSV that are secondary IDs whose current primary *also*
appears in the same TSV. Those are the rows that represent the same protein
split across two entries.

Outputs (under ``data/analysis/cross_source_uniprot_audit/``):

- ``per_source_classification.tsv``  — one row per (source, accession)
- ``merge_level_collisions.tsv``     — same-protein split rows
- ``audit_summary.json``             — headline counts per source and
  aggregate, plus counts of secondary accessions whose primary is present
  elsewhere in the candidate universe
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from surface_proteome.candidates.traceability import (  # noqa: E402
    sha256_file,
    utc_now_iso,
)
from surface_proteome.candidates.uniprot_accession_history import (  # noqa: E402
    UNIPROT_ACCESSION_RE,
    parse_delac_sp,
    parse_sec_ac,
)

_ALL_SOURCES_CACHE: set[str] | None = None

DEFAULT_HIST_DIR = ROOT / "data" / "external" / "uniprot_accession_history"
DEFAULT_OUT_DIR = ROOT / "data" / "analysis" / "cross_source_uniprot_audit"

UNIPROT_TSV = (
    ROOT / "data" / "external" / "uniprot_human_surface_candidates"
    / "uniprot_human_surface_candidates.tsv"
)
GO_TSV = (
    ROOT / "data" / "external" / "go_human_surface_annotations"
    / "go_human_surface_annotations_by_gene_product.tsv"
)
SURFY_TSV = ROOT / "data" / "processed" / "surfy" / "surfy_human_snapshot.tsv"
CSPA_TSV = ROOT / "data" / "processed" / "cspa" / "cspa_human_snapshot.tsv"
DEEPTMHMM_CAN_TSV = (
    ROOT / "data" / "processed" / "deeptmhmm" / "deeptmhmm_human_canonical.tsv"
)
DEEPTMHMM_ISO_TSV = (
    ROOT / "data" / "processed" / "deeptmhmm" / "deeptmhmm_human_isoforms.tsv"
)
HPA_TSV = ROOT / "data" / "processed" / "hpa" / "hpa_human_snapshot.tsv"
COMPARTMENTS_TSV = (
    ROOT / "data" / "processed" / "jensenlab_compartments"
    / "jensenlab_compartments_human_snapshot.tsv"
)
CANDIDATE_UNIVERSE_TSV = (
    ROOT / "data" / "processed" / "candidate_universe" / "candidate_universe.tsv"
)

def _strip_isoform(acc: str) -> str:
    """Strip a UniProt isoform suffix (``-N``) to the base accession."""
    return acc.split("-", 1)[0]


def load_source_accessions() -> dict[str, set[str]]:
    """Return ``{source_name: {base_uniprot_accession, ...}}`` for each source.

    Accessions are loaded from the same canonical snapshot files that
    ``build_candidate_universe.py`` consumes, so results reflect what the
    merge actually sees.
    """
    sources: dict[str, set[str]] = {}

    up = pd.read_csv(UNIPROT_TSV, sep="\t", dtype=str, usecols=["accession"])
    sources["uniprot"] = {_strip_isoform(a.strip()) for a in up["accession"].dropna()}

    go = pd.read_csv(GO_TSV, sep="\t", dtype=str, usecols=["DB_Object_ID"])
    sources["go"] = {_strip_isoform(a.strip()) for a in go["DB_Object_ID"].dropna()}

    surfy = pd.read_csv(SURFY_TSV, sep="\t", dtype=str, usecols=["uniprot_accession", "surfy_is_surface"])
    surfy = surfy[surfy["surfy_is_surface"].fillna("0") == "1"]
    sources["surfy"] = {_strip_isoform(a.strip()) for a in surfy["uniprot_accession"].dropna()}

    cspa = pd.read_csv(CSPA_TSV, sep="\t", dtype=str, usecols=["uniprot_accession"])
    sources["cspa"] = {_strip_isoform(a.strip()) for a in cspa["uniprot_accession"].dropna()}

    dt_accessions: set[str] = set()
    for path in (DEEPTMHMM_CAN_TSV, DEEPTMHMM_ISO_TSV):
        df = pd.read_csv(path, sep="\t", dtype=str, usecols=["uniprot_accession"])
        dt_accessions.update(_strip_isoform(a.strip()) for a in df["uniprot_accession"].dropna())
    sources["deeptmhmm"] = dt_accessions

    if HPA_TSV.exists():
        hpa = pd.read_csv(HPA_TSV, sep="\t", dtype=str, usecols=["uniprot_accession"])
        sources["hpa"] = {_strip_isoform(a.strip()) for a in hpa["uniprot_accession"].dropna()}

    if COMPARTMENTS_TSV.exists():
        cmp_df = pd.read_csv(COMPARTMENTS_TSV, sep="\t", dtype=str, usecols=["uniprot_accession"])
        sources["compartments"] = {
            _strip_isoform(a.strip()) for a in cmp_df["uniprot_accession"].dropna()
        }

    return sources


def classify(
    acc: str,
    *,
    uniprot_current: set[str],
    sec_ac: dict[str, list[str]],
    delac_sp: set[str],
) -> str:
    if acc in uniprot_current:
        return "primary_current"
    if acc in sec_ac:
        return "secondary"
    if acc in delac_sp:
        return "deleted_swissprot"
    if UNIPROT_ACCESSION_RE.match(acc):
        return "primary_not_queried"
    return "unknown"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history-dir", type=Path, default=DEFAULT_HIST_DIR)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument(
        "--candidate-universe-tsv",
        type=Path,
        default=CANDIDATE_UNIVERSE_TSV,
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    sec_ac_path = args.history_dir / "sec_ac.txt"
    delac_sp_path = args.history_dir / "delac_sp.txt"
    if not sec_ac_path.exists() or not delac_sp_path.exists():
        raise FileNotFoundError(
            "UniProt accession-history files missing. Run "
            "`uv run python src/surface_proteome/candidates/download_uniprot_accession_history.py` first."
        )

    print("parsing accession-history reference ...")
    sec_ac = parse_sec_ac(sec_ac_path)
    delac_sp = parse_delac_sp(delac_sp_path)
    print(f"  sec_ac entries:   {len(sec_ac):,}")
    print(f"  delac_sp entries: {len(delac_sp):,}")

    print("loading source accession sets ...")
    sources = load_source_accessions()
    for name, accs in sources.items():
        print(f"  {name:<10s} {len(accs):,}")
    uniprot_current = sources["uniprot"]

    # Per-source classification
    rows: list[dict[str, object]] = []
    per_source_counts: dict[str, dict[str, int]] = {}
    for name, accs in sources.items():
        counts: dict[str, int] = defaultdict(int)
        for acc in sorted(accs):
            cat = classify(
                acc,
                uniprot_current=uniprot_current,
                sec_ac=sec_ac,
                delac_sp=delac_sp,
            )
            counts[cat] += 1
            if cat in {"secondary", "deleted_swissprot", "unknown"}:
                primaries = sec_ac.get(acc, []) if cat == "secondary" else []
                rows.append(
                    {
                        "source": name,
                        "accession": acc,
                        "classification": cat,
                        "current_primaries": ";".join(primaries),
                        "primary_also_in_any_source": int(
                            any(p in _union_all_sources(sources) for p in primaries)
                        ) if primaries else 0,
                        "primary_also_in_same_source": int(
                            any(p in accs for p in primaries)
                        ) if primaries else 0,
                    }
                )
        per_source_counts[name] = dict(counts)

    df = pd.DataFrame(rows)
    per_source_tsv = out_dir / "per_source_classification.tsv"
    df.to_csv(per_source_tsv, sep="\t", index=False)
    print(f"wrote {per_source_tsv.relative_to(ROOT)}  ({len(df):,} flagged rows)")

    # Merge-level collision check: read candidate_universe.tsv and find
    # accessions that are secondary AND whose current primary is also
    # present in the merge (i.e., same protein listed twice).
    print("checking merge-level collisions ...")
    cu = pd.read_csv(args.candidate_universe_tsv, sep="\t", dtype=str,
                     usecols=["uniprot_accession", "sources_present",
                              "n_sources_surface", "gene_symbol"])
    cu_set = set(cu["uniprot_accession"].dropna().astype(str))
    collisions: list[dict[str, object]] = []
    for acc in cu_set:
        if acc in sec_ac:
            for primary in sec_ac[acc]:
                if primary in cu_set:
                    collisions.append(
                        {
                            "secondary_accession": acc,
                            "primary_accession": primary,
                            "secondary_sources_present": cu.loc[cu["uniprot_accession"] == acc, "sources_present"].iat[0],
                            "primary_sources_present": cu.loc[cu["uniprot_accession"] == primary, "sources_present"].iat[0],
                            "secondary_gene_symbol": cu.loc[cu["uniprot_accession"] == acc, "gene_symbol"].iat[0],
                            "primary_gene_symbol": cu.loc[cu["uniprot_accession"] == primary, "gene_symbol"].iat[0],
                        }
                    )
    coll_df = pd.DataFrame(collisions).sort_values(
        ["secondary_accession", "primary_accession"]
    ).reset_index(drop=True) if collisions else pd.DataFrame(
        columns=[
            "secondary_accession", "primary_accession",
            "secondary_sources_present", "primary_sources_present",
            "secondary_gene_symbol", "primary_gene_symbol",
        ]
    )
    collisions_tsv = out_dir / "merge_level_collisions.tsv"
    coll_df.to_csv(collisions_tsv, sep="\t", index=False)
    print(f"wrote {collisions_tsv.relative_to(ROOT)}  ({len(coll_df):,} collisions)")

    summary = {
        "generated_at_utc": utc_now_iso(),
        "reference_files": {
            "sec_ac": {
                "path": str(sec_ac_path.relative_to(ROOT)),
                "sha256": sha256_file(sec_ac_path),
                "n_entries": len(sec_ac),
            },
            "delac_sp": {
                "path": str(delac_sp_path.relative_to(ROOT)),
                "sha256": sha256_file(delac_sp_path),
                "n_entries": len(delac_sp),
            },
        },
        "per_source_counts": per_source_counts,
        "per_source_totals": {name: len(accs) for name, accs in sources.items()},
        "merge_level_collisions": {
            "n_collision_pairs": int(len(coll_df)),
            "n_distinct_secondaries": int(coll_df["secondary_accession"].nunique()) if len(coll_df) else 0,
            "n_distinct_primaries": int(coll_df["primary_accession"].nunique()) if len(coll_df) else 0,
        },
        "notes": [
            "TrEMBL deletions are not fetched by default; 'unknown' classifications "
            "are most likely deleted-TrEMBL accessions. Re-run the downloader with "
            "--include-trembl and extend parse_delac_tr() to resolve them.",
        ],
    }
    summary_path = out_dir / "audit_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {summary_path.relative_to(ROOT)}")

    print("\n--- per-source classification counts ---")
    for name, counts in per_source_counts.items():
        print(f"  {name}: {dict(counts)}")
    print("\n--- merge-level collision summary ---")
    print(f"  collision pairs: {len(coll_df):,}")


def _union_all_sources(sources: dict[str, set[str]]) -> set[str]:
    """Union of accession sets across all loaded sources (memoized once)."""
    global _ALL_SOURCES_CACHE
    if _ALL_SOURCES_CACHE is None:
        _ALL_SOURCES_CACHE = set().union(*sources.values())
    return _ALL_SOURCES_CACHE


if __name__ == "__main__":
    main()
