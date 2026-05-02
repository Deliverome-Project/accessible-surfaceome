"""Fetch human cell-surface / plasma-membrane GO annotations via GOATOOLS + GAF.

Replaces an earlier QuickGO-based implementation: the QuickGO
``downloadSearch`` endpoint silently ignores the ``page`` parameter at sizes
needed for this union query, so any multi-page pull is broken. Instead this
script downloads the canonical GO artifacts directly from
``current.geneontology.org`` and filters with GOATOOLS:

    http://current.geneontology.org/ontology/go-basic.obo
    http://current.geneontology.org/annotations/goa_human.gaf.gz

Pipeline
--------
1. Download ``go-basic.obo`` and ``goa_human.gaf.gz`` with traceability.
2. Parse the ontology with ``goatools.obo_parser.GODag`` loaded with
   ``optional_attrs={'relationship'}`` and, for each configured surface root,
   expand the descendant set following both ``is_a`` (via
   ``GOTerm.get_all_children()``) and ``part_of`` (via the reverse
   ``relationship_rev`` adjacency). This matches QuickGO's default
   ``goUsage=descendants`` with ``goUsageRelationships=is_a,part_of``
   (``occurs_in`` is a process-graph relationship and does not apply to the
   CC/MF roots used here).
3. Parse the human GAF line-by-line (format is stable; DB, DB_ID, DB_Symbol,
   Qualifier, GO_ID, DB:Reference, Evidence_Code, With/From, Aspect,
   DB_Object_Name, Synonyms, DB_Object_Type, Taxon, Date, Assigned_By,
   Annotation_Extension, Gene_Product_Form_ID).
4. Keep rows whose ``GO_ID`` is in the union descendant set and whose
   ``Qualifier`` is not negated (``NOT ...``). Tag each row with the set of
   configured roots it hits, the evidence-code tier, and the source term's
   aspect/label.
5. Emit a TSV (one row per retained annotation) + a per-gene-product summary
   TSV + a traceability manifest capturing both artifact SHA256s, the GAF
   header (including the ``!date-generated`` / ``!generated-by`` lines), and
   the exact configured root set with expanded-descendant counts.

Divergences from the plan's draft term list
-------------------------------------------
``GO:0031225``, ``GO:0046658``, ``GO:0031226``, ``GO:0005615`` are obsolete in
the current GO release (verified against ``/ontology/go/terms/GO:<id>``).
GPI-anchor signal is captured via UniProt ``ft_lipid`` in the companion
``download_uniprot_human_surface_candidates.py`` pull, intrinsic-component PM
is covered by parent ``GO:0005886``, and extracellular space is covered by
parent ``GO:0005576``. These obsolete IDs are recorded in the manifest under
``obsolete_terms_excluded`` for traceability.

No evidence-code filter is applied at retention time — every annotation is
kept with its ``Evidence_Code`` so downstream synthesis can tier as needed
(experimental / curated / sequence / electronic).
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from surface_proteome.candidates.traceability import (
    build_file_record,
    download_binary,
    sha256_file,
    utc_now_iso,
    write_manifest,
)

from surface_proteome.paths import REPO_ROOT as ROOT

DATASET = "go_human_surface_annotations"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "external" / DATASET

GO_OBO_URL = "http://current.geneontology.org/ontology/go-basic.obo"
GOA_HUMAN_GAF_URL = "http://current.geneontology.org/annotations/goa_human.gaf.gz"

OBO_FILENAME = "go-basic.obo"
GAF_FILENAME = "goa_human.gaf.gz"
ANNOTATIONS_TSV = f"{DATASET}.tsv"
SUMMARY_TSV = f"{DATASET}_by_gene_product.tsv"
TERM_METADATA_JSON = "go_term_metadata.json"

# Live GO terms (cellular-component only, updated 2026-04-18): roots whose
# members are definitional plasma-membrane / cell-surface proteins under
# the one-pager's definition of surface = accessible on the extracellular
# face of an intact cell. See docs/plans/2026-04-16-surface-proteome-annotation.md.
#
#   GO:0009986 cell surface
#   GO:0009897 external side of plasma membrane
#   GO:0005887 integral component of plasma membrane
#
# Each root is expanded with its is_a + part_of descendants; the resulting
# TSV preserves the specific GO_ID each annotation carries.
#
# Dropped 2026-04-18: GO:0038023 (signaling receptor activity) and
# GO:0004888 (TM signaling receptor activity). These are molecular-
# function terms, not location terms. In GO they admit endosomal
# pattern-recognition receptors (TLR3/7/8/9) and other intracellular-
# membrane signaling receptors based on activity annotation alone, which
# conflicts with the "accessible on the extracellular face" definition
# used downstream. Surface receptors with genuine plasma-membrane
# residence are picked up via the cellular-component roots.
#
# Tier C (dropped 2026-04-17): GO:0005886 (plasma membrane — too broad),
# GO:0005576 (extracellular region — secreted, not cell-surface-attached,
# 16% SURFY overlap), GO:0022857 (TM transporter activity — mixes
# organellar TM proteins), GO:0098552 (side of membrane — includes
# cytoplasmic face), GO:0098797 (PM protein complex — redundant).
#
# Obsolete-in-current-GO (excluded explicitly):
#   GO:0031225 (anchored component of membrane)            → UniProt ft_lipid
#   GO:0046658 (anchored component of plasma membrane)     → UniProt ft_lipid
#   GO:0031226 (intrinsic component of plasma membrane)    → parent GO:0005886
#   GO:0005615 (extracellular space)                       → parent GO:0005576
SURFACE_GO_TERMS: list[tuple[str, str, str]] = [
    # (goId, aspect, configured_label)
    ("GO:0009986", "cellular_component", "cell surface"),
    ("GO:0009897", "cellular_component", "external side of plasma membrane"),
    ("GO:0005887", "cellular_component", "integral component of plasma membrane"),
]

OBSOLETE_GO_TERMS_NOTED: list[tuple[str, str, str]] = [
    ("GO:0031225", "anchored component of membrane", "covered via UniProt ft_lipid"),
    ("GO:0046658", "anchored component of plasma membrane", "covered via UniProt ft_lipid"),
    ("GO:0031226", "intrinsic component of plasma membrane", "parent GO:0005886 retained"),
    ("GO:0005615", "extracellular space", "covered by parent GO:0005576"),
]

# GAF v2.x column order (17 cols through v2.2). We parse manually to avoid
# goatools-internal API churn; the spec is stable.
# https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/
GAF_COLUMNS: list[str] = [
    "DB",
    "DB_Object_ID",
    "DB_Object_Symbol",
    "Qualifier",
    "GO_ID",
    "DB_Reference",
    "Evidence_Code",
    "With_From",
    "Aspect",
    "DB_Object_Name",
    "DB_Object_Synonym",
    "DB_Object_Type",
    "Taxon",
    "Date",
    "Assigned_By",
    "Annotation_Extension",
    "Gene_Product_Form_ID",
]

# Evidence-code tiering. Downstream synthesis may use whichever tiers fit.
EXPERIMENTAL_EC = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP"}
CURATED_EC = {"IBA", "IBD", "IKR", "IRD", "TAS", "NAS", "IC"}
SEQUENCE_EC = {"ISS", "ISO", "ISA", "ISM", "IGC", "RCA"}
ELECTRONIC_EC = {"IEA"}


def _tier_for_ec(ec: str) -> str:
    if ec in EXPERIMENTAL_EC:
        return "experimental"
    if ec in CURATED_EC:
        return "curated"
    if ec in SEQUENCE_EC:
        return "sequence"
    if ec in ELECTRONIC_EC:
        return "electronic"
    return "other"


def download_if_missing(url: str, dest: Path) -> tuple[str, dict[str, str]]:
    """Download ``url`` to ``dest`` if missing. Return (status, headers)."""
    if dest.exists():
        return "reused", {}
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    data, headers = download_binary(url, timeout=600)
    dest.write_bytes(data)
    return "downloaded", headers


def read_gaf_header(path: Path, max_lines: int = 200) -> list[str]:
    """Return the ``!``-prefixed header lines at the top of a (gzip) GAF."""
    opener = gzip.open if path.suffix == ".gz" else open
    out: list[str] = []
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for i, line in enumerate(handle):
            if not line.startswith("!"):
                break
            out.append(line.rstrip("\n"))
            if i >= max_lines:
                break
    return out


def _expand_is_a_and_part_of(godag: Any, root_id: str) -> set[str]:
    """BFS closure following is_a children + ``part_of`` reverse edges.

    The ``relationship_rev`` attribute (populated when GODag is loaded with
    ``optional_attrs={'relationship'}``) maps ``rel_type -> set(parent terms
    reached via that rel)``. For ``part_of`` specifically, ``relationship_rev``
    on term X contains the set of terms Y such that ``Y part_of X``, i.e. the
    part-of children of X.
    """
    seen: set[str] = {root_id}
    stack = [root_id]
    while stack:
        cur_id = stack.pop()
        term = godag.get(cur_id)
        if term is None:
            continue
        # is_a children (direct)
        for child in getattr(term, "children", []) or []:
            cid = child.id
            if cid not in seen:
                seen.add(cid)
                stack.append(cid)
        # part_of children via relationship_rev
        rev = getattr(term, "relationship_rev", {}) or {}
        for child in rev.get("part_of", set()) or set():
            cid = child.id
            if cid not in seen:
                seen.add(cid)
                stack.append(cid)
    return seen


def build_descendant_index(
    godag: Any, roots: list[tuple[str, str, str]]
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Return (go_id -> configured-root-ids it rolls up to, per-term metadata).

    Expansion follows both ``is_a`` and ``part_of`` to match QuickGO's default
    descendant traversal for CC/MF surface terms.
    """
    membership: dict[str, set[str]] = defaultdict(set)
    term_meta: list[dict[str, Any]] = []
    for go_id, configured_aspect, label in roots:
        term = godag.get(go_id)
        if term is None:
            term_meta.append({
                "goId": go_id,
                "configured_aspect": configured_aspect,
                "configured_label": label,
                "status": "not_in_obo",
            })
            continue
        if term.is_obsolete:
            term_meta.append({
                "goId": go_id,
                "name": term.name,
                "namespace": term.namespace,
                "configured_aspect": configured_aspect,
                "configured_label": label,
                "status": "obsolete_in_obo",
                "isObsolete": True,
            })
            continue
        ids = _expand_is_a_and_part_of(godag, go_id)
        for gid in ids:
            membership[gid].add(go_id)
        term_meta.append({
            "goId": go_id,
            "name": term.name,
            "namespace": term.namespace,
            "configured_aspect": configured_aspect,
            "configured_label": label,
            "status": "ok",
            "isObsolete": False,
            "n_including_self": len(ids),
        })
    return {k: sorted(v) for k, v in membership.items()}, term_meta


def parse_gaf_rows(gaf_path: Path, membership: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Yield kept annotation rows filtered to the membership GO ids.

    Skips GAF comment lines (``!``), negated annotations (``Qualifier`` starts
    with ``NOT``), and non-9606 taxa (safety check — the ``goa_human.gaf`` is
    human, but there are a handful of cross-species annotation rows).
    """
    kept: list[dict[str, Any]] = []
    opener = gzip.open if gaf_path.suffix == ".gz" else open
    n_read = 0
    n_kept = 0
    n_negated = 0
    n_non_uniprot = 0
    with opener(gaf_path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("!") or not line.strip():
                continue
            n_read += 1
            flds = line.rstrip("\n").split("\t")
            if len(flds) < 15:
                continue
            # Restrict to protein annotations keyed by UniProtKB primary accession.
            # goa_human.gaf also contains ComplexPortal (CPX-*) and RNAcentral
            # (URS*) rows; those are not individual proteins and would pollute a
            # per-UniProt snapshot.
            if flds[0] != "UniProtKB":
                n_non_uniprot += 1
                continue
            go_id = flds[4]
            if go_id not in membership:
                continue
            qualifier = flds[3]
            if qualifier.startswith("NOT"):
                n_negated += 1
                continue
            taxon = flds[12]
            if "taxon:9606" not in taxon:
                continue
            ec = flds[6]
            row = dict(zip(GAF_COLUMNS, flds + [""] * (len(GAF_COLUMNS) - len(flds)), strict=False))
            row["configured_roots"] = "|".join(membership[go_id])
            row["evidence_tier"] = _tier_for_ec(ec)
            kept.append(row)
            n_kept += 1
    print(
        f"  GAF rows read={n_read}  kept={n_kept}  "
        f"negated_skipped={n_negated}  non_uniprot_skipped={n_non_uniprot}"
    )
    return kept


def write_annotations_tsv(rows: list[dict[str, Any]], path: Path) -> int:
    """Write one row per retained annotation."""
    header = [*GAF_COLUMNS, "configured_roots", "evidence_tier"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write("\t".join(header) + "\n")
        for r in rows:
            out.write("\t".join(str(r.get(col, "")) for col in header) + "\n")
    return len(rows)


def write_summary_tsv(rows: list[dict[str, Any]], path: Path) -> int:
    """Collapse to one row per (DB, DB_Object_ID, DB_Object_Symbol) with
    aggregated GO IDs, configured-root hits, evidence codes, and tier flags.
    """
    agg: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        key = (r["DB"], r["DB_Object_ID"], r["DB_Object_Symbol"])
        entry = agg.setdefault(key, {
            "DB": r["DB"],
            "DB_Object_ID": r["DB_Object_ID"],
            "DB_Object_Symbol": r["DB_Object_Symbol"],
            "DB_Object_Name": r["DB_Object_Name"],
            "Taxon": r["Taxon"],
            "go_ids": set(),
            "configured_roots_hit": set(),
            "evidence_codes": set(),
            "evidence_tiers": set(),
            "n_annotations": 0,
        })
        entry["go_ids"].add(r["GO_ID"])
        for root in r["configured_roots"].split("|"):
            if root:
                entry["configured_roots_hit"].add(root)
        entry["evidence_codes"].add(r["Evidence_Code"])
        entry["evidence_tiers"].add(r["evidence_tier"])
        entry["n_annotations"] += 1

    header = [
        "DB", "DB_Object_ID", "DB_Object_Symbol", "DB_Object_Name", "Taxon",
        "n_annotations", "n_go_ids", "n_configured_roots_hit",
        "go_ids", "configured_roots_hit", "evidence_codes", "evidence_tiers",
        "has_experimental", "has_curated", "has_sequence", "has_electronic",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        out.write("\t".join(header) + "\n")
        for key in sorted(agg.keys()):
            e = agg[key]
            tiers = e["evidence_tiers"]
            out.write("\t".join([
                e["DB"], e["DB_Object_ID"], e["DB_Object_Symbol"], e["DB_Object_Name"], e["Taxon"],
                str(e["n_annotations"]),
                str(len(e["go_ids"])),
                str(len(e["configured_roots_hit"])),
                "|".join(sorted(e["go_ids"])),
                "|".join(sorted(e["configured_roots_hit"])),
                "|".join(sorted(e["evidence_codes"])),
                "|".join(sorted(tiers)),
                "1" if "experimental" in tiers else "0",
                "1" if "curated" in tiers else "0",
                "1" if "sequence" in tiers else "0",
                "1" if "electronic" in tiers else "0",
            ]) + "\n")
    return len(agg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--force-redownload",
        action="store_true",
        help="Re-fetch the OBO and GAF even if present in the output dir.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    obo_path = out_dir / OBO_FILENAME
    gaf_path = out_dir / GAF_FILENAME

    if args.force_redownload:
        for p in (obo_path, gaf_path):
            if p.exists():
                p.unlink()

    print("[1/4] fetching GO artifacts ...")
    started_at = utc_now_iso()
    obo_status, obo_headers = download_if_missing(GO_OBO_URL, obo_path)
    gaf_status, gaf_headers = download_if_missing(GOA_HUMAN_GAF_URL, gaf_path)
    print(f"  {OBO_FILENAME}: {obo_status}  ({obo_path.stat().st_size:,} bytes)")
    print(f"  {GAF_FILENAME}: {gaf_status}  ({gaf_path.stat().st_size:,} bytes)")

    print("[2/4] parsing ontology + expanding configured roots ...")
    from goatools.obo_parser import GODag  # local import: heavy
    godag = GODag(str(obo_path), optional_attrs={"relationship"}, prt=None)
    membership, term_meta = build_descendant_index(godag, SURFACE_GO_TERMS)
    print(f"  union GO id set (roots + is_a descendants): {len(membership):,} terms")
    for m in term_meta:
        n = m.get("n_including_self", "-")
        ns = m.get("namespace", "?")
        print(f"    {m['goId']:<14} {m.get('status','?'):<14} [{ns}] n={n}  {m.get('name','')}")

    print("[3/4] filtering GAF rows ...")
    kept_rows = parse_gaf_rows(gaf_path, membership)

    print("[4/4] writing outputs ...")
    anno_path = out_dir / ANNOTATIONS_TSV
    summary_path = out_dir / SUMMARY_TSV
    terms_path = out_dir / TERM_METADATA_JSON
    manifest_path = out_dir / "download_traceability.json"

    n_rows = write_annotations_tsv(kept_rows, anno_path)
    n_products = write_summary_tsv(kept_rows, summary_path)
    terms_path.write_text(
        json.dumps({"terms": term_meta}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    gaf_header_lines = read_gaf_header(gaf_path)
    gaf_generated_by = next((ln for ln in gaf_header_lines if ln.startswith("!generated-by")), "")
    gaf_date_generated = next((ln for ln in gaf_header_lines if ln.startswith("!date-generated")), "")
    gaf_version = next((ln for ln in gaf_header_lines if ln.startswith("!gaf-version")), "")

    finished_at = utc_now_iso()

    records = [
        build_file_record(
            repo_root=ROOT, file_path=obo_path, source_url=GO_OBO_URL,
            dataset=DATASET, status=obo_status,
            response_headers=obo_headers or None,
            note="GO basic ontology (is_a + part_of + regulates closure; no cross-aspect xrefs).",
        ),
        build_file_record(
            repo_root=ROOT, file_path=gaf_path, source_url=GOA_HUMAN_GAF_URL,
            dataset=DATASET, taxid="9606", species="Homo sapiens", status=gaf_status,
            response_headers=gaf_headers or None,
            note="Canonical human GO annotations (GAF v2.x).",
        ),
        build_file_record(
            repo_root=ROOT, file_path=anno_path,
            source_url=f"derived from {GOA_HUMAN_GAF_URL}",
            dataset=DATASET, taxid="9606", species="Homo sapiens", status="derived",
            note=(
                "One row per retained annotation; columns match GAF v2.2 plus "
                "configured_roots (|-joined root IDs this row rolls up to) and "
                "evidence_tier (experimental/curated/sequence/electronic/other)."
            ),
        ),
        build_file_record(
            repo_root=ROOT, file_path=summary_path,
            source_url=f"derived from {GOA_HUMAN_GAF_URL}",
            dataset=DATASET, taxid="9606", species="Homo sapiens", status="derived",
            note=(
                "One row per (DB, DB_Object_ID, DB_Object_Symbol); aggregates "
                "GO IDs, configured-roots hit, and per-tier evidence flags."
            ),
        ),
        build_file_record(
            repo_root=ROOT, file_path=terms_path,
            source_url=f"derived from {GO_OBO_URL}",
            dataset=DATASET, status="derived",
            note="Per-root ontology metadata (name, namespace, obsolete flag, descendant count).",
        ),
    ]

    write_manifest(
        manifest_path,
        dataset=DATASET,
        script=Path(__file__).as_posix(),
        records=records,
        extras={
            "source_urls": {"obo": GO_OBO_URL, "gaf": GOA_HUMAN_GAF_URL},
            "configured_roots": [
                {"goId": go_id, "configured_aspect": aspect, "configured_label": label}
                for go_id, aspect, label in SURFACE_GO_TERMS
            ],
            "obsolete_terms_excluded": [
                {"goId": go_id, "name": name, "disposition": note}
                for go_id, name, note in OBSOLETE_GO_TERMS_NOTED
            ],
            "descendant_expansion": "BFS closure over is_a (via term.children) + part_of (via term.relationship_rev)",
            "taxon_filter": "taxon:9606 (rows containing this token in column 13)",
            "negation_filter": "skip rows where Qualifier startswith NOT",
            "evidence_filter": "none (downstream tiers via evidence_tier column)",
            "evidence_tiers": {
                "experimental": sorted(EXPERIMENTAL_EC),
                "curated": sorted(CURATED_EC),
                "sequence": sorted(SEQUENCE_EC),
                "electronic": sorted(ELECTRONIC_EC),
            },
            "gaf_header": {
                "gaf_version": gaf_version,
                "generated_by": gaf_generated_by,
                "date_generated": gaf_date_generated,
                "all_header_lines": gaf_header_lines,
            },
            "n_union_go_ids": len(membership),
            "n_annotations_retained": n_rows,
            "n_gene_products": n_products,
            "fetch_started_at_utc": started_at,
            "fetch_finished_at_utc": finished_at,
            "obo_sha256": sha256_file(obo_path),
            "gaf_sha256": sha256_file(gaf_path),
            "note_obsolete_term_divergence": (
                "Plan's GO:0031225 is obsolete; also GO:0046658, GO:0031226, "
                "GO:0005615. GPI-anchor signal sourced from UniProt ft_lipid; "
                "intrinsic-component PM covered by parent GO:0005886; "
                "extracellular space covered by parent GO:0005576."
            ),
        },
    )
    print(f"annotations: {anno_path}  ({n_rows:,} rows)")
    print(f"summary:     {summary_path}  ({n_products:,} gene products)")
    print(f"terms:       {terms_path}")
    print(f"manifest:    {manifest_path}")


if __name__ == "__main__":
    main()
