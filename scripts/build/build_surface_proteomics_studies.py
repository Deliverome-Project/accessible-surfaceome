"""Build the viewer's surface-proteomics study index and per-protein presence table.

Source: the S3E8 cross-method surfaceome study compendium (deliverome-analysis,
``analysis/sprint3/s3e8-cross-method-surfaceome/``). One published snapshot holds
every human-only study arm we ingested, with the review decision for each:

* ``manifest.json`` — one entry per study arm: paper, method family, cell/tissue
  context, review role (core / provisional / hold / below_adjusted_screen /
  complementary) and whether the labeling chemistry reached intact cells.
* ``detections_long.tsv`` — one row per (arm, current UniProt accession). The
  accessions are already mapped through UniProt's secondary-accession history.
* ``method_audit.json`` — the per-paper methods-section audit (committed in the
  analysis repo, not in the snapshot). Its ``intact_cell_labeling`` field
  overrides the manifest's ``surface_accessibility_evidence`` flag when present.
  An arm split out of a parent study (``recovery_parent_study``) inherits the
  parent's audit entry.
* ``sources.json`` — the analysis repo's study registry. An arm it lists that
  the snapshot manifest lacks is added from its banked source table (George
  2026 was wired in after the sweep and is missing from the sweep-v5 manifest).
  A registry id the snapshot split into several arms becomes an alias, so a
  link to the parent id (``?arm=vilen-2022``) opens all of its arms.

Outputs (committed; the viewer serves them as static files):

* ``viewer/public/data/surface-proteomics/studies.json`` — snapshot provenance
  plus one entry per arm (``arms[i]`` is the arm with index ``i``).
* ``viewer/public/data/surface-proteomics/presence/{NN}.json`` — the presence
  table, sharded by :func:`shard_of` so a gene page fetches one ~30 KB file
  instead of the whole table. Each shard maps a base UniProt accession to
  ``{"s": symbol, "d": 1 if it has a deep-dive page, "a": [arm indices],
  "n": HGNC full name, "v": number of the five source databases listing it,
  "t": deep-dive tier}`` (``n`` / ``v`` / ``t`` omitted when unknown). Reported
  accessions are first normalized to the gene's canonical accession through the
  HGNC-ID path (:func:`normalize_accessions`).

Only arms with an ``admitted`` review decision (core / provisional) count as
surface detections. Held arms (e.g. a fully imputed published matrix, where per-
sample detection can't be recovered), arms below the reference-overlap screen,
and comparators (membrane fractionation, inner-leaflet labeling) are kept and
labeled so the viewer can show them as "listed, not counted".

Whole-lysate arms are not published at all: an arm whose measurement is neither
on intact cells nor on a membrane fraction (per :func:`method_class` — for
example hydrazide or boronic-acid N-glycopeptide capture from whole-cell or
whole-tumor lysate) is dropped from both outputs. Their ids are recorded in
``studies.json`` under ``excluded_arms``.

Joins are on UniProt accession with isoform suffixes stripped, never on gene
symbols. Symbols are display-only, taken from the public catalog (falling back
to the study's own symbol column when the catalog has no row for the accession).

Nothing from the analysis repo's ``outreach/`` prefix, and no author contact
details, are read or written. Free-text review notes are not exported either:
the viewer gets structured fields only.

Run (S3 credentials as in deliverome-analysis's ``.env``)::

    uv run python scripts/build/build_surface_proteomics_studies.py \\
        --env-file ~/git/deliverome-analysis/.env \\
        --analysis-repo ~/git/deliverome-analysis \\
        --analysis-ref origin/becca/s3e8-fractionation-family

or from local copies of the three inputs with ``--source-dir DIR`` (holding
``manifest.json``, ``detections_long.tsv`` and ``method_audit.json``).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import io
import json
import logging
import re
import shutil
import statistics
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surface-proteomics"
HGNC_TSV = REPO_ROOT / "data" / "external" / "hgnc" / "hgnc_complete_set.tsv"

SNAPSHOT = "2026-11-02-sweep-v5"
PROCESSED_PREFIX = "sprint3/s3e8-cross-method-surfaceome"
ANALYSIS_DIR = "analysis/sprint3/s3e8-cross-method-surfaceome"
METHOD_AUDIT_PATH = f"{ANALYSIS_DIR}/method_audit.json"
SOURCES_PATH = f"{ANALYSIS_DIR}/sources.json"
API_BASE = "https://api.deliverome.org/surfaceome"

# Must match ``shardOf`` in viewer/lib/surface-proteomics.ts.
N_SHARDS = 32

# Review roles as the analysis names them → the viewer's status buckets.
STATUS_BY_ROLE = {
    "core": "core",
    "provisional": "provisional",
    "hold": "held",
    "below_adjusted_screen": "below_screen",
    "complementary": "comparator",
    # sources.json's role for an arm the registry admits as a primary input.
    "primary": "core",
}

# Curated cell-type group for every published arm (the viewer's cell-type filter).
# The build fails if an arm is missing, so a new arm must be classified here.
CELL_GROUPS: dict[str, tuple[str, ...]] = {
    "blood_cancer": (
        "george-aml-2026",
        "sanchez-jurkat-2026",
        "ho-k562-csc-2026",
        "ho-k562-conaey-2026",
        "ho-k562-wgaey-2026",
        "ho-k562-choley-2026",
        "ho-k562-nbaey-2026",
        "ho-k562-cscey-2026",
        "ho-k562-snhs-2026",
        "ho-k562-wgahrp-2026",
        "sucam-2026",
        "xu-thp1-surface-2026",
        "cyssurf-yan",
        "cd38-myeloma-2024",
        "lasa-2024",
        "ferguson-2022",
        "optimized-csc-aml-2022",
        "anderson-2022",
        "nix-ball-2021",
        "myeloma-csc-2020",
        "leung-2019",
        "schmidt-aml-2018",
        "perna-2017",
        "haverland-2017",
    ),
    "solid_cancer": (
        "salmela-cscc-2026",
        "porter-gbm-2026",
        "glyco-pdx-csc-2026",
        "slezak-hct116apex-2026",
        "stehn-mpnst-2026",
        "cattaneo-crc-2026",
        "mooney-os-2026",
        "chen-pc3-2026",
        "laurent-gsc-2026",
        "kuffa-crcpolar-2026",
        "sucam-jhh4-carboxyl-2026",
        "sucam-jhh4-glyco-2026",
        "sucam-jhh4-multiplex-2026",
        "friedlova-cervix-2025",
        "martins-crc3d-2025",
        "furan-biotin",
        "khan-chordoma-2024",
        "mooney-ewing-2024",
        "gasf-wang-2024",
        "hypoxic-gbm-2024",
        "hamilton-nb-2024",
        "reeves-2024",
        "calligaris-chs-2023",
        "pandey-dipg-2023",
        "rms-2023",
        "vilen-apex-2022",
        "vilen-sia-2022",
        "sbiosite-2023",
        "fielding-a549-pmp-2022",
        "capdeville-daoy-2022",
        "gangras-shsy5y-2022",
        "lazar-skbr3shaving-2022",
        "lazar-skbr3amine-2022",
        "lazar-skbr3glyco-2022",
        "orfanou-breast-2021",
        "li-npc-2021",
        "kong-lung-2020",
        "xiao-mcf7-2017",
        "posthumadeboer-os-2013",
        "zhang-os-2010",
    ),
    "immune": (
        "laccid-2025",
        "udeshi-2024",
        "veneer-2024",
        "byrnes-2022",
        "soday-2021",
        "ravenhill-2020",
        "kalxdorf-2017",
    ),
    "neural": (
        "nash-i3neuron-2026",
        "holmes-2025",
        "breyer-2025",
        "nicholson-gm2-2025",
        "lorenz-muller-2021",
        "tyleckova-npc-2016",
        "english-brain-2012",
    ),
    "stem_stromal": (
        "wojdyla-2020",
        "matta-2019",
        "hepatic-endoderm-2017",
        "niehage-dpsc-2016",
        "holley-msc-2015",
        "boheler-2014",
        "msc-hoflack-2011",
    ),
    "other_normal": (
        "dusailly-ec-2026",
        "rethore-huvec-2026",
        "mazzone-rpe1-2026",
        "taggi-bbb-2025",
        "thorup-nge",
        "thorup-wgahrp",
        "hunter-hfff-pmp-2024",
        "deng-2024",
        "cellsurfer-2023",
        "depierreux-hfff-pmp-2022",
        "kirkemo-2022",
        "myc-wells-2021",
        "ito-bbb-2020",
        "soh-hacat-pmp-2020",
        "leung-2020",
        "giovani-pdl-2019",
        "mallanna-2016",
        "jung-colonorg-2015",
    ),
    "multi": (
        "cspa-2015",
        "autocsc-2019",
    ),
}

# Arms whose banked source table has one column per cell line; the gene page
# shows which lines detected a protein. (accession column, non-line columns)
PER_LINE_TABLES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "george-aml-2026": (
        "cell-surface-proteomics/2026-09-19-george-v1/biotin-amine/george-aml-2026/surface_mean_abundance.tsv",
        "Accession",
        ("Gene_Symbol", "SPC"),
    ),
}

# Columns a banked source table may carry its UniProt accessions in.
ACCESSION_COLUMNS = ("uniprot_accession", "Accession", "accession")
GENE_COLUMNS = ("gene_symbol", "Gene_Symbol", "gene")

# Method families: intact-cell labeling chemistries vs. fractionation / lysate.
FAMILY_LABEL = {
    "biotin-amine": "Amine biotinylation",
    "glycoprotein-capture": "Glycoprotein capture",
    "glycopeptide-capture": "Glycopeptide capture",
    "peroxidase-proximity": "Peroxidase proximity labeling",
    "other-chemoproteomic": "Other chemoproteomic labeling",
    "membrane-fractionation": "Membrane fractionation",
}


def shard_of(acc: str) -> int:
    """Stable shard for a base accession: 31-polynomial hash of its bytes."""
    h = 0
    for ch in acc:
        h = (h * 31 + ord(ch)) % 1_000_003
    return h % N_SHARDS


def base_accession(acc: str) -> str:
    return acc.strip().split("-")[0].upper()


def method_class(entry: dict[str, Any], intact: bool) -> str:
    """intact_cell | fractionation | lysate — the axis the viewer colors on."""
    if entry["method_group"] == "membrane-fractionation":
        return "fractionation"
    return "intact_cell" if intact else "lysate"


def _read_s3(bucket: str, key: str) -> bytes:
    import os

    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
        region_name=os.environ.get("S3_REGION") or None,
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
    )
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _git_show(args: argparse.Namespace, path: str) -> str:
    return subprocess.run(
        ["git", "-C", args.analysis_repo, "show", f"{args.analysis_ref}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def load_inputs(args: argparse.Namespace) -> tuple[dict, list[dict], dict, dict]:
    if args.source_dir:
        src = Path(args.source_dir)
        manifest = json.loads((src / "manifest.json").read_text())
        detections_text = (src / "detections_long.tsv").read_text()
        audit = json.loads((src / "method_audit.json").read_text())
        sources_path = src / "sources.json"
        sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    else:
        import os

        bucket = os.environ["S3_BUCKET_PROCESSED"]
        prefix = f"{PROCESSED_PREFIX}/{args.snapshot}"
        manifest = json.loads(_read_s3(bucket, f"{prefix}/manifest.json"))
        detections_text = _read_s3(bucket, f"{prefix}/detections_long.tsv").decode()
        audit = json.loads(_git_show(args, METHOD_AUDIT_PATH))
        sources = json.loads(_git_show(args, SOURCES_PATH))
    detections = list(csv.DictReader(io.StringIO(detections_text), delimiter="\t"))
    return manifest, detections, audit, sources


def _pick(columns: list[str], wanted: tuple[str, ...], first: str | None) -> str | None:
    for c in ((first,) if first else ()) + wanted:
        if c in columns:
            return c
    return None


def add_registry_arms(
    manifest: dict,
    detections: list[dict],
    sources: dict,
    read_table: Any,
) -> dict[str, list[str]]:
    """Fold registry arms the snapshot manifest lacks into ``manifest``/``detections``.

    Returns ``{parent_id: [arm ids]}`` for registry ids the snapshot split into
    several arms; those are aliases, not arms of their own.
    """
    in_manifest = {d["study_id"] for d in manifest["datasets"]}
    children: dict[str, list[str]] = defaultdict(list)
    for d in manifest["datasets"]:
        if d.get("recovery_parent_study"):
            children[d["recovery_parent_study"]].append(d["study_id"])
    aliases: dict[str, list[str]] = {}
    cutoff = (manifest.get("inclusion_policy") or {}).get("base_overlap_cutoff", 0.2)
    for e in sources.get("datasets", []):
        sid = e["study_id"]
        if sid in in_manifest:
            continue
        if children.get(sid):
            aliases[sid] = sorted(children[sid])
            continue
        if not e.get("sources") or not e.get("extractions"):
            logger.warning("registry arm %s has no banked source table; skipped", sid)
            continue
        ext = e["extractions"][0]
        rows = read_table(e["sources"][ext.get("source", 0)]["key"])
        cols = list(rows[0]) if rows else []
        acc_col = _pick(cols, ACCESSION_COLUMNS, ext.get("accession"))
        gene_col = _pick(cols, GENE_COLUMNS, ext.get("gene"))
        if not acc_col:
            raise RuntimeError(f"{sid}: no accession column in {cols[:6]}")
        accs: dict[str, str] = {}
        for r in rows:
            acc = base_accession(r[acc_col] or "")
            if re.fullmatch(r"[A-Z][A-Z0-9]{5,9}", acc):
                accs.setdefault(acc, (r.get(gene_col) or "") if gene_col else "")
        role = e.get("review_role") or "hold"
        entry = dict(e)
        entry["admitted"] = (
            STATUS_BY_ROLE.get(role) in ("core", "provisional")
            and bool(e.get("surface_accessibility_evidence"))
            and float(e.get("pct_in_surf") or 0) >= cutoff
        )
        entry["paper"] = dict(e.get("paper") or {})
        manifest["datasets"].append(entry)
        for acc, gene in accs.items():
            detections.append(
                {"uniprot_accession": acc, "gene_symbol": gene, "study_id": sid}
            )
        logger.info("added registry arm %s: %d proteins", sid, len(accs))
    return aliases


csv.field_size_limit(1 << 30)  # some banked tables carry very long free-text cells


def _read_external_table(key: str) -> list[dict[str, str]]:
    import os

    text = _read_s3(os.environ["S3_BUCKET_EXTERNAL"], key).decode()
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def _get_json(client: httpx.Client, url: str) -> Any:
    for attempt in range(6):
        r = client.get(url)
        if r.status_code == 200:
            return r.json()
        wait = float(r.headers.get("retry-after") or 10 * (attempt + 1))
        logger.warning("GET %s → %s; retrying in %.0fs", url, r.status_code, wait)
        time.sleep(wait)
    raise RuntimeError(f"GET {url} kept failing")


def load_symbols(
    api_base: str,
) -> tuple[dict[str, str], set[str], dict[str, int], dict[str, str]]:
    """Accession → display symbol, the deep-dived set, accession → 5-DB votes,
    and accession → deep-dive tier (the Worker's ``deep_dive_tier``)."""
    headers = {"User-Agent": "accessible-surfaceome build (surface-proteomics studies)"}
    with httpx.Client(timeout=120, headers=headers) as client:
        catalog = _get_json(client, f"{api_base}/v1/catalog")
        genes = _get_json(client, f"{api_base}/v1/genes")
    symbols: dict[str, str] = {}
    votes: dict[str, int] = {}
    tiers: dict[str, str] = {}
    for row in catalog["rows"]:
        acc = base_accession(row.get("uniprot") or "")
        if acc and acc not in symbols:
            symbols[acc] = row["symbol"]
            if isinstance(row.get("n_sources"), int):
                votes[acc] = row["n_sources"]
            if row.get("deep_dive") and row.get("deep_dive_tier"):
                tiers[acc] = row["deep_dive_tier"]
    deep: set[str] = set()
    for g in genes["genes"]:
        acc = base_accession(g.get("uniprot_acc") or "")
        if acc:
            deep.add(acc)
            symbols[acc] = g["gene_symbol"]
    return symbols, deep, votes, tiers


def load_canonical() -> tuple[dict[str, str], str]:
    """hgnc_id → canonical UniProt accession, from public D1 ``gene_identifier_public``.

    This is the stable-ID cache the HGNC-ID resolver (``resolve_by_hgnc_id``)
    writes, and the only sanctioned source for a gene's canonical accession.
    """
    from accessible_surfaceome.cloud.d1_client import D1Client

    rows: list[dict[str, Any]] = []
    with D1Client.public() as d1:
        offset = 0
        while True:
            page = d1.query(
                "SELECT hgnc_id, uniprot_acc, resolver_version FROM gene_identifier_public"
                " ORDER BY hgnc_id LIMIT 2000 OFFSET ?;",
                [offset],
            )
            rows += page
            offset += 2000
            if len(page) < 2000:
                break
    versions = sorted(
        {r["resolver_version"] for r in rows if r.get("resolver_version")}
    )
    canonical = {
        r["hgnc_id"]: base_accession(r["uniprot_acc"])
        for r in rows
        if r.get("uniprot_acc")
    }
    return canonical, ",".join(versions)


def load_hgnc_xrefs(path: Path) -> dict[str, set[str]]:
    """UniProt accession → HGNC ids that cross-reference it (HGNC ``uniprot_ids``)."""
    out: dict[str, set[str]] = defaultdict(set)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            for acc in (row.get("uniprot_ids") or "").split("|"):
                if acc.strip():
                    out[base_accession(acc)].add(row["hgnc_id"])
    return out


def load_uniprot_hgnc(accs: list[str]) -> tuple[dict[str, set[str]], str | None]:
    """UniProt's own HGNC cross-reference for accessions HGNC doesn't list.

    Mostly unreviewed TrEMBL entries for a gene whose canonical entry differs.
    Human entries only.
    """
    out: dict[str, set[str]] = {}
    release = None
    headers = {"User-Agent": "accessible-surfaceome build (surface-proteomics studies)"}
    url = "https://rest.uniprot.org/uniprotkb/accessions"
    with httpx.Client(timeout=120, headers=headers) as client:
        for i in range(0, len(accs), 500):
            batch = accs[i : i + 500]
            r = client.get(
                url,
                params={
                    "accessions": ",".join(batch),
                    "fields": "accession,organism_id,xref_hgnc",
                    "format": "tsv",
                    "size": 500,
                },
            )
            r.raise_for_status()
            release = r.headers.get("x-uniprot-release") or release
            for row in csv.DictReader(io.StringIO(r.text), delimiter="\t"):
                if row.get("Organism (ID)") != "9606":
                    continue
                ids = {x for x in (row.get("HGNC") or "").split(";") if x.strip()}
                if ids:
                    out[row["Entry"]] = ids
    return out, release


def normalize_accessions(
    accs: set[str],
    canonical: dict[str, str],
    hgnc_xrefs: dict[str, set[str]],
    uniprot_hgnc: Any,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Map each reported accession to its gene's canonical accession.

    Accession → HGNC id (HGNC's own ``uniprot_ids`` xref first, then UniProt's
    HGNC xref) → canonical accession from ``gene_identifier_public``. Never via a
    symbol. An accession that reaches no gene, or more than one, is kept as
    reported.
    """
    canonical_accs = set(canonical.values())
    hgnc_of: dict[str, set[str]] = {}
    for acc in accs:
        if acc not in canonical_accs and acc in hgnc_xrefs:
            hgnc_of[acc] = hgnc_xrefs[acc]
    rest = sorted(a for a in accs if a not in canonical_accs and a not in hgnc_of)
    from_uniprot, release = uniprot_hgnc(rest) if rest else ({}, None)
    hgnc_of.update(from_uniprot)
    mapping: dict[str, str] = {}
    n_mapped = n_ambiguous = 0
    for acc in accs:
        if acc in canonical_accs:
            continue
        targets = {canonical[h] for h in hgnc_of.get(acc, ()) if h in canonical}
        if len(targets) == 1:
            mapping[acc] = targets.pop()
            n_mapped += 1
        elif len(targets) > 1:
            n_ambiguous += 1
    stats = {
        "n_reported": len(accs),
        "n_already_canonical": len(accs & canonical_accs),
        "n_mapped_to_canonical": n_mapped,
        "n_ambiguous_kept": n_ambiguous,
        "n_unmapped_kept": len(accs)
        - len(accs & canonical_accs)
        - n_mapped
        - n_ambiguous,
        "uniprot_release": release,
    }
    return mapping, stats


def load_per_line(
    arms: list[dict[str, Any]],
    index: dict[str, int],
    mapping: dict[str, str],
    read_table: Any,
) -> dict[str, dict[str, list[int]]]:
    """Per-cell-line detection for arms in PER_LINE_TABLES.

    Sets ``arm["lines"]`` to the line names and returns
    ``{canonical acc: {str(arm index): [line indices]}}`` (value > 0 = detected).
    Accessions go through the same normalization as the detections.
    """
    out: dict[str, dict[str, list[int]]] = defaultdict(dict)
    for sid, (key, acc_col, skip) in PER_LINE_TABLES.items():
        if sid not in index:
            continue
        rows = read_table(key)
        line_cols = [c for c in rows[0] if c != acc_col and c not in skip]
        arms[index[sid]]["lines"] = line_cols
        hits: dict[str, set[int]] = defaultdict(set)
        for r in rows:
            acc = base_accession(r[acc_col] or "")
            if not re.fullmatch(r"[A-Z][A-Z0-9]{5,9}", acc):
                continue
            acc = mapping.get(acc, acc)
            for j, c in enumerate(line_cols):
                try:
                    if float(r[c] or 0) > 0:
                        hits[acc].add(j)
                except ValueError:
                    pass
        for acc, js in hits.items():
            if js:
                out[acc][str(index[sid])] = sorted(js)
        logger.info("per-line detail for %s: %d lines", sid, len(line_cols))
    return dict(out)


# Count columns a list-style table may carry when no per-sample quantity is
# recorded, most specific first: (column, unit label).
COUNT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("# PSMs", "PSMs"),
    ("Number of PSMs", "PSMs"),
    ("total_spectral_count", "spectral counts"),
    ("MS/MS Count", "MS/MS spectra"),
    ("# Unique Peptides", "unique peptides"),
    ("Number of Unique Peptides", "unique peptides"),
    ("n_peptides", "peptides"),
    ("n_probe_peptides", "probe-labeled peptides"),
    ("# Peptides", "peptides"),
    ("Number of Peptides", "peptides"),
    ("Number of peptides", "peptides"),
    ("Peptides", "peptides"),
    ("peptides", "peptides"),
)


def quant_unit(columns: list[str], kinds: set[str], scale: str) -> str:
    """Plain-language unit for a dataset's per-sample quantity columns."""
    text = " ".join(columns + sorted(kinds)).lower()
    rules = (
        ("ibaq", "iBAQ intensity"),
        ("lfq", "LFQ intensity"),
        ("tmt", "TMT reporter abundance"),
        ("log2auc", "log2 peptide AUC"),
        ("numspectra", "spectral counts"),
        ("spectral", "spectral counts"),
        ("psm", "PSMs"),
        ("prot_matches", "protein matches"),
        ("unique peptides", "unique peptides"),
        ("peptide", "peptides"),
        ("peak area", "peak area"),
        ("area", "peak area"),
        ("pg.quantity", "DIA protein quantity"),
        ("ms2quant", "DIA protein quantity"),
        ("dia", "DIA protein quantity"),
        ("intensity", "MS intensity"),
        ("abundance", "reported abundance"),
    )
    if scale.startswith("log2"):
        # A log2 column is an intensity unless a more specific measure is named.
        specific = ("lfq", "tmt", "ibaq", "log2auc")
        unit = next(
            (label for key, label in rules if key in specific and key in text),
            "intensity",
        )
        return unit if unit.startswith("log2") else f"log2 {unit}"
    return next((label for key, label in rules if key in text), "reported abundance")


def _num(v: Any) -> float | None:
    try:
        x = float(v)
    except TypeError, ValueError:
        return None
    return x if x == x else None  # drop NaN


def load_quant(
    manifest: dict,
    arms: list[dict[str, Any]],
    index: dict[str, int],
    mapping: dict[str, str],
    read_table: Any,
) -> dict[str, dict[str, list[float]]]:
    """Per-protein quantity and within-dataset percentile, for each arm.

    The quantity is the dataset's own measure, from its banked control table:
    the mean over the extraction recipe's sample-group columns (missing and,
    on linear scales, zero values skipped), or else a count column (PSMs,
    peptides). Sets ``arm["quant_unit"]`` / ``arm["quant_note"]`` and returns
    ``{canonical acc: {str(arm index): [value, percentile]}}``, the percentile
    being the share of the dataset's quantified proteins with a lower value
    (0-100). Values are not comparable across datasets; percentiles are.
    """
    by_id = {d["study_id"]: d for d in manifest["datasets"]}
    out: dict[str, dict[str, list[float]]] = defaultdict(dict)
    for sid, i in index.items():
        d = by_id.get(sid)
        key = (d or {}).get("control_tsv_key")
        per_line = PER_LINE_TABLES.get(sid)
        if per_line and not key:
            key = per_line[0]
        if not d or not key:
            continue
        try:
            rows = read_table(key)
        except Exception as e:  # a missing banked table is a gap, not a failure
            logger.warning("no control table for %s: %s", sid, e)
            continue
        if not rows:
            continue
        header = list(rows[0])
        groups = [
            g
            for e in d.get("extractions") or []
            for g in e.get("sample_groups") or []
            if g.get("use_for_membership", True)
        ]
        cols = [c for g in groups for c in g["columns"] if c in header]
        scale = next((g.get("scale") or "linear" for g in groups), "linear")
        if not cols and per_line:
            # Per-line atlas tables: one abundance column per cell line.
            cols = [c for c in header if c != per_line[1] and c not in per_line[2]]
            groups = [{"replicate_kind": "abundance"}]
        if cols:
            unit = quant_unit(
                cols, {g.get("replicate_kind") or "" for g in groups}, scale
            )
            note = (
                f"mean over the samples where it was detected (of {len(cols)})"
                if len(cols) > 1
                else "one sample"
            )
        else:
            hit = next(((c, u) for c, u in COUNT_COLUMNS if c in header), None)
            if not hit:
                continue
            cols, unit, note, scale = [hit[0]], hit[1], "as reported", "linear"
        log = scale.startswith("log2")
        acc_col = next(
            (
                c
                for c in ("uniprot_accession", per_line[1] if per_line else "")
                if c in header
            ),
            None,
        )
        if not acc_col:
            continue
        values: dict[str, float] = {}
        for r in rows:
            acc = base_accession(r.get(acc_col) or "")
            if not acc:
                continue
            acc = mapping.get(acc, acc)
            xs = [
                x
                for x in (_num(r.get(c)) for c in cols)
                if x is not None and (log or x > 0)
            ]
            if xs:
                v = sum(xs) / len(xs)
                values[acc] = max(values.get(acc, v), v)
        if len(values) < 10:
            continue
        ordered = sorted(values.values())
        n = len(ordered)
        for acc, v in values.items():
            below = bisect.bisect_left(ordered, v)
            out[acc][str(i)] = [float(f"{v:.3g}"), round(100 * below / n)]
        arms[i]["quant_unit"] = unit
        arms[i]["quant_note"] = note
        arms[i]["n_quantified"] = n
    logger.info(
        "quantities for %d of %d arms",
        sum(1 for a in arms if a.get("quant_unit")),
        len(arms),
    )
    return dict(out)


# Whole-proteome reference for the surface-preference score: ProCan
# (Goncalves et al. 2022, PMID 35839778), DIA across 949 cancer cell lines,
# log2 intensities (comparable across proteins, unlike CCLE's relative TMT).
PROCAN_KEY = "procan-depmapsanger/goncalves-2022/ProCan-DepMapSanger_protein_matrix_8498_averaged.txt"
MIN_SURFACE_VALUES = 5
MIN_MEMBRANE_VALUES = 3


def load_procan_percentiles(mapping: dict[str, str]) -> dict[str, float]:
    """Canonical acc -> percentile (0-100) of mean ProCan intensity across lines."""
    import os

    text = _read_s3(os.environ["S3_BUCKET_EXTERNAL"], PROCAN_KEY).decode()
    lines = text.splitlines()
    header = lines[0].split("\t")[1:]
    sums = [0.0] * len(header)
    ns = [0] * len(header)
    for line in lines[1:]:
        for j, v in enumerate(line.split("\t")[1:]):
            x = _num(v) if v else None
            if x is not None:
                sums[j] += x
                ns[j] += 1
    means: dict[str, float] = {}
    for j, col in enumerate(header):
        if not ns[j]:
            continue
        acc = base_accession(col.split(";")[0])
        acc = mapping.get(acc, acc)
        means[acc] = max(means.get(acc, -1e9), sums[j] / ns[j])
    ordered = sorted(means.values())
    n = len(ordered)
    return {
        acc: 100
        * (bisect.bisect_left(ordered, v) + bisect.bisect_right(ordered, v))
        / (2 * n)
        for acc, v in means.items()
    }


def surface_preference(
    quant: dict[str, dict[str, list[float]]],
    arms: list[dict[str, Any]],
    procan: dict[str, float],
) -> dict[str, list[int | None]]:
    """Per protein: [median percentile in counted surface datasets, median in
    membrane-fraction datasets, ProCan whole-proteome percentile].

    Only proteins quantified in at least MIN_SURFACE_VALUES counted datasets get
    a score; the membrane median needs MIN_MEMBRANE_VALUES fraction datasets.
    Surface minus each reference is the protein's surface preference: positive
    when it ranks higher in surface preps than in that reference.
    """
    counted = {
        str(i) for i, a in enumerate(arms) if a["admitted"] and a.get("quant_unit")
    }
    membrane = {
        str(i)
        for i, a in enumerate(arms)
        if a["method_class"] == "fractionation" and a.get("quant_unit")
    }
    out: dict[str, list[int | None]] = {}
    for acc, q in quant.items():
        surf = [v[1] for k, v in q.items() if k in counted]
        if len(surf) < MIN_SURFACE_VALUES:
            continue
        frac = [v[1] for k, v in q.items() if k in membrane]
        out[acc] = [
            round(statistics.median(surf)),
            round(statistics.median(frac))
            if len(frac) >= MIN_MEMBRANE_VALUES
            else None,
            round(procan[acc]) if acc in procan else None,
        ]
    return out


def preference_auroc(
    pref: dict[str, list[int | None]], tiers: dict[str, str]
) -> dict[str, float]:
    """How well each score separates Canonical from Low / Not surface (documentation
    only; the score itself never reads the tiers)."""

    def auroc(pos: list[float], neg: list[float]) -> float | None:
        if not pos or not neg:
            return None
        allv = sorted(pos + neg)
        rank = {}
        for idx, v in enumerate(allv):
            rank.setdefault(v, []).append(idx + 1)
        r = {v: sum(x) / len(x) for v, x in rank.items()}
        return round(
            (sum(r[v] for v in pos) - len(pos) * (len(pos) + 1) / 2)
            / (len(pos) * len(neg)),
            3,
        )

    scores: dict[str, tuple[list[float], list[float]]] = {
        "vs_procan": ([], []),
        "vs_membrane": ([], []),
    }
    for acc, (surf, frac, wp) in pref.items():
        t = tiers.get(acc)
        if t not in ("canonical", "low", "no") or surf is None:
            continue
        side = 0 if t == "canonical" else 1
        if wp is not None:
            scores["vs_procan"][side].append(surf - wp)
        if frac is not None:
            scores["vs_membrane"][side].append(surf - frac)
    return {
        k: a for k, (pos, neg) in scores.items() if (a := auroc(pos, neg)) is not None
    }


def write_downloads(
    out: Path, arms: list[dict[str, Any]], shards: list[dict[str, Any]]
) -> None:
    """Whole-compendium downloads: a protein x dataset matrix and dataset metadata."""
    counted = [i for i, a in enumerate(arms) if a["admitted"]]
    with (out / "surface_proteomics_matrix.tsv").open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "uniprot_acc",
                "symbol",
                "name",
                "surfaceome_tier",
                "db_votes_of_5",
                "n_counted_datasets",
                "surface_pct_median",
                "membrane_fraction_pct_median",
                "procan_whole_proteome_pct",
                *[a["id"] for a in arms],
            ]
        )
        entries = sorted(
            ((acc, e) for shard in shards for acc, e in shard.items()),
            key=lambda x: x[0],
        )
        for acc, e in entries:
            hit = set(e["a"])
            w.writerow(
                [
                    acc,
                    e["s"],
                    e.get("n", ""),
                    e.get("t", "not_deep_dived" if not e["d"] else ""),
                    e.get("v", ""),
                    sum(1 for i in counted if i in hit),
                    *[
                        ("" if x is None else x)
                        for x in (e.get("p") or [None, None, None])
                    ],
                    *["1" if i in hit else "0" for i in range(len(arms))],
                ]
            )
    # Ends on always-present columns: a trailing empty field would leave a
    # trailing tab, which whitespace-trimming tools (and pre-commit) strip.
    cols = [
        "id", "name", "first_author", "year", "journal", "pmid", "doi", "repository",
        "repository_ids", "method_class", "family", "family_label", "cell_group",
        "sample", "reference_overlap", "n_proteins", "admitted", "status",
    ]  # fmt: skip
    with (out / "surface_proteomics_datasets.tsv").open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(cols)
        for a in arms:
            w.writerow(
                [
                    ";".join(a[c])
                    if isinstance(a.get(c), list)
                    else str(a.get(c) if a.get(c) is not None else "").strip()
                    for c in cols
                ]
            )


def counted_hist(
    presence: dict[str, set[int]], arms: list[dict[str, Any]]
) -> list[int]:
    counted = {i for i, a in enumerate(arms) if a["admitted"]}
    hist = [0] * (len(counted) + 1)
    for idx in presence.values():
        k = len(idx & counted)
        if k:
            hist[k] += 1
    return hist


def cohort_hists(
    presence: dict[str, set[int]],
    arms: list[dict[str, Any]],
    deep: set[str],
    tiers: dict[str, str],
) -> dict[str, list[int]]:
    counted = {i for i, a in enumerate(arms) if a["admitted"]}
    out: dict[str, list[int]] = defaultdict(lambda: [0] * (len(counted) + 1))
    for acc in deep:
        k = len(presence.get(acc, set()) & counted)
        out["all"][k] += 1
        if acc in tiers:
            out[tiers[acc]][k] += 1
    return dict(out)


def load_names(path: Path) -> dict[str, str]:
    """Accession → approved full name, from HGNC's ``uniprot_ids`` column.

    Keyed on the accession HGNC cross-references, never on a symbol. Display only.
    """
    names: dict[str, str] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            for acc in (row.get("uniprot_ids") or "").split("|"):
                acc = base_accession(acc)
                if acc and row.get("name"):
                    names.setdefault(acc, row["name"])
    return names


def load_pubmed(pmids: list[str]) -> dict[str, dict[str, Any]]:
    """First author, year, journal and title from NCBI esummary (one batched call).

    The manifest's paper block uses mixed author formats and is missing for a few
    older inputs, so PubMed is the single citation source whenever it has the PMID.
    """
    if not pmids:
        return {}
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {"db": "pubmed", "retmode": "json", "id": ",".join(sorted(set(pmids)))}
    headers = {"User-Agent": "accessible-surfaceome build (surface-proteomics studies)"}
    r = httpx.post(url, data=params, headers=headers, timeout=120)
    r.raise_for_status()
    result = r.json()["result"]
    out: dict[str, dict[str, Any]] = {}
    for pmid in result.get("uids", []):
        e = result[pmid]
        year = (e.get("pubdate") or "")[:4]
        out[pmid] = {
            "first_author": e.get("sortfirstauthor") or None,
            "year": int(year) if year.isdigit() else None,
            "journal": e.get("source") or None,
            "title": (e.get("title") or "").rstrip(".") or None,
            "doi": next(
                (
                    i["value"]
                    for i in e.get("articleids", [])
                    if i.get("idtype") == "doi"
                ),
                None,
            ),
        }
    return out


# The viewer uses American spelling. Our own curated descriptions (arm names,
# sample text) are normalized; published paper titles are left as published.
_AMERICAN = (
    ("leukaemia", "leukemia"),
    ("Leukaemia", "Leukemia"),
    ("haemat", "hemat"),
    ("Haemat", "Hemat"),
    ("tumour", "tumor"),
    ("Tumour", "Tumor"),
    ("labelling", "labeling"),
    ("Labelling", "Labeling"),
    ("labelled", "labeled"),
    ("polarised", "polarized"),
    ("immortalised", "immortalized"),
    ("Immortalised", "Immortalized"),
    ("characterised", "characterized"),
    ("oesophag", "esophag"),
    ("Oesophag", "Esophag"),
    ("haemoglobin", "hemoglobin"),
)


def americanize(text: str | None) -> str | None:
    if not text:
        return text
    for a, b in _AMERICAN:
        text = text.replace(a, b)
    return text


# What the authors limited their list to, when they pre-filtered it.
FILTER_UNIVERSE_LABEL = {
    "topology": "transmembrane or signal-peptide proteins",
    "broad": "membrane- or surface-annotated proteins",
    "broad_surf": "membrane- or surface-annotated proteins",
    "surfy": "SURFY-predicted surface proteins",
    "pm": "plasma-membrane-annotated proteins",
}

# Held reasons, matched in order against the review note (lower-cased). The
# note itself is not exported; only this short structured label is.
HELD_REASONS = (
    ("imput", "values are imputed, so detection can't be read per protein"),
    ("does not match", "the deposited table doesn't match the paper's design"),
    ("channel", "the sample-to-condition map is unpublished"),
    ("reported surface set", "only the authors' pre-selected surface list is public"),
    (
        "restricted to the original",
        "only the authors' pre-selected surface list is public",
    ),
    ("no-biotin control recovers", "the no-label control recovers the same signal"),
    ("ratio threshold", "only proteins above an enrichment cutoff are reported"),
    ("background control", "no background control in the deposit"),
    ("barcoded", "samples can't be separated in the published table"),
    ("pool", "conditions are pooled in one list, with no separable baseline"),
    ("biological", "only biological comparisons are published, not a baseline list"),
)


def status_reason(d: dict[str, Any], status: str, base: float) -> str | None:
    """Short, plain reason for any status other than Core."""
    pct = d.get("pct_in_surf")
    universe = d.get("filter_universe")
    filtered = universe not in (None, "human")
    if status == "provisional":
        if filtered:
            what = FILTER_UNIVERSE_LABEL.get(universe, "annotated surface proteins")
            return f"author pre-filtered to {what}"
        if pct is not None and pct < base:
            return f"just under the {base:.0%} bar ({pct:.1%})"
        return "built from a partial author export (peptide-level table)"
    if status == "below_screen":
        if filtered and pct is not None:
            return f"pre-filtered list below its raised bar ({pct:.0%} vs {(d.get('adjusted_overlap_cutoff') or base):.0%})"
        return (
            f"{pct:.0%} known surface proteins, under {base:.0%}"
            if pct is not None
            else None
        )
    if status == "held":
        note = (d.get("reason") or "").lower()
        return next(
            (label for key, label in HELD_REASONS if key in note),
            "per-protein detection can't be recovered from the table",
        )
    if status == "comparator":
        if d.get("method_group") == "membrane-fractionation":
            return "membrane fractionation, not intact-cell labeling"
        if "inner-leaflet" in (d.get("reason") or "").lower():
            return "labeling reaches the inner side of the membrane"
        return "not intact-cell surface labeling"
    return None


def _strip_citation(name: str) -> str:
    """Drop a trailing "(Author Year)" — the viewer shows the citation separately."""
    return re.sub(r"\s*\([^()]*\b(?:19|20)\d{2}\)\s*$", "", name).strip() or name


def build_arms(
    manifest: dict,
    audit: dict,
    counts: dict[str, int],
    pubmed: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    audit_ds = audit.get("datasets", {})
    base_cutoff = float(
        (manifest.get("inclusion_policy") or {}).get("base_overlap_cutoff", 0.2)
    )
    arms: list[dict[str, Any]] = []
    for d in manifest["datasets"]:
        sid = d["study_id"]
        paper = dict(d.get("paper") or {})
        pmid = paper.get("pmid") or (
            str(d["publication_id"])
            if str(d.get("publication_id") or "").isdigit()
            else None
        )
        for k, v in pubmed.get(pmid or "", {}).items():
            if v is not None and (k != "doi" or not paper.get("doi")):
                paper[k] = v
        paper["pmid"] = pmid
        a = (
            audit_ds.get(sid)
            or audit_ds.get(d.get("recovery_parent_study") or "")
            or {}
        )
        icl = a.get("intact_cell_labeling")
        intact = (
            icl == "yes"
            if icl in ("yes", "no")
            else bool(d.get("surface_accessibility_evidence"))
        )
        role = d["review_role"]
        arms.append(
            {
                "id": sid,
                "name": americanize(_strip_citation(d["name"])),
                "publication": str(d.get("publication_id") or paper.get("pmid") or sid),
                "first_author": paper.get("first_author"),
                "year": paper.get("year"),
                "journal": paper.get("journal"),
                "title": paper.get("title"),
                "pmid": paper.get("pmid"),
                "doi": paper.get("doi") or d.get("doi"),
                "family": d["method_group"],
                "family_label": FAMILY_LABEL.get(d["method_group"], d["method_group"]),
                "method_class": method_class(d, intact),
                "intact_cell_labeling": "yes" if intact else "no",
                "intact_cell_verified": icl in ("yes", "no"),
                "sample": americanize(
                    d.get("human_sample_type") or d.get("cell_or_tissue_type")
                ),
                "status": STATUS_BY_ROLE.get(role, role),
                "status_reason": status_reason(
                    d, STATUS_BY_ROLE.get(role, role), base_cutoff
                ),
                "admitted": bool(d.get("admitted")),
                "n_proteins": counts.get(sid, 0),
                "reference_overlap": d.get("pct_in_surf"),
                "repository": (d.get("accession") or {}).get("repository"),
                "repository_ids": (d.get("accession") or {}).get("ids") or [],
            }
        )
    # Newest first, then by name — the order the viewer lists arms in.
    return sorted(arms, key=lambda a: (-int(a["year"] or 0), str(a["name"])))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--snapshot", default=SNAPSHOT)
    p.add_argument(
        "--source-dir",
        help="Local dir with manifest.json, detections_long.tsv, method_audit.json",
    )
    p.add_argument("--env-file", type=Path, help=".env holding the S3_* credentials")
    p.add_argument(
        "--analysis-repo", default=str(Path.home() / "git" / "deliverome-analysis")
    )
    p.add_argument("--analysis-ref", default="origin/main")
    p.add_argument("--api-base", default=API_BASE)
    p.add_argument("--out", type=Path, default=OUT_DIR)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env(args.env_file)

    manifest, detections, audit, sources = load_inputs(args)
    aliases = add_registry_arms(manifest, detections, sources, _read_external_table)
    canonical, resolver_version = load_canonical()
    mapping, norm_stats = normalize_accessions(
        {base_accession(r["uniprot_accession"]) for r in detections},
        canonical,
        load_hgnc_xrefs(HGNC_TSV),
        load_uniprot_hgnc,
    )
    norm_stats["resolver_version"] = resolver_version
    for row in detections:
        acc = base_accession(row["uniprot_accession"])
        row["uniprot_accession"] = mapping.get(acc, acc)
    logger.info("accession normalization: %s", norm_stats)
    counts: dict[str, set[str]] = defaultdict(set)
    for row in detections:
        counts[row["study_id"]].add(base_accession(row["uniprot_accession"]))
    pmids = [
        str(d.get("paper", {}).get("pmid") or d.get("publication_id") or "")
        for d in manifest["datasets"]
    ]
    pubmed = load_pubmed([p for p in pmids if p.isdigit()])
    built = build_arms(manifest, audit, {k: len(v) for k, v in counts.items()}, pubmed)
    # Whole-lysate arms measure neither intact cells nor a membrane fraction.
    excluded = sorted(a["id"] for a in built if a["method_class"] == "lysate")
    arms = [a for a in built if a["method_class"] != "lysate"]
    group_of = {sid: g for g, ids in CELL_GROUPS.items() for sid in ids}
    missing = [a["id"] for a in arms if a["id"] not in group_of]
    if missing:
        raise SystemExit(f"add these arms to CELL_GROUPS: {', '.join(missing)}")
    for a in arms:
        a["cell_group"] = group_of[a["id"]]
    index = {a["id"]: i for i, a in enumerate(arms)}
    aliases = {k: [c for c in v if c in index] for k, v in aliases.items()}
    aliases = {k: v for k, v in aliases.items() if v}
    logger.info("excluded %d whole-lysate arms: %s", len(excluded), ", ".join(excluded))

    symbols, deep, votes, tiers = load_symbols(args.api_base)
    names = load_names(HGNC_TSV)
    presence: dict[str, set[int]] = defaultdict(set)
    fallback_symbol: dict[str, str] = {}
    for row in detections:
        if row["study_id"] not in index:
            continue
        acc = base_accession(row["uniprot_accession"])
        presence[acc].add(index[row["study_id"]])
        if row.get("gene_symbol"):
            fallback_symbol.setdefault(acc, row["gene_symbol"])

    per_line = load_per_line(arms, index, mapping, _read_external_table)
    quant = load_quant(manifest, arms, index, mapping, _read_external_table)
    pref = surface_preference(quant, arms, load_procan_percentiles(mapping))

    shards: list[dict[str, Any]] = [{} for _ in range(N_SHARDS)]
    for acc in sorted(presence):
        entry: dict[str, Any] = {
            "s": symbols.get(acc) or fallback_symbol.get(acc) or "",
            "d": 1 if acc in deep else 0,
            "a": sorted(presence[acc]),
        }
        if acc in names:
            entry["n"] = names[acc]
        if acc in votes:
            entry["v"] = votes[acc]
        if acc in tiers:
            entry["t"] = tiers[acc]
        if acc in per_line:
            entry["l"] = per_line[acc]
        if acc in quant:
            entry["q"] = quant[acc]
        if acc in pref:
            entry["p"] = pref[acc]
        shards[shard_of(acc)][acc] = entry

    admitted = [a for a in arms if a["admitted"]]
    meta = {
        "_generated_by": "scripts/build/build_surface_proteomics_studies.py",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "snapshot": args.snapshot,
        "source": f"S3E8 cross-method surfaceome compendium, processed snapshot {args.snapshot}",
        "n_shards": N_SHARDS,
        "n_arms": len(arms),
        "n_publications": len({a["publication"] for a in arms}),
        "n_admitted_arms": len(admitted),
        "n_admitted_publications": len({a["publication"] for a in admitted}),
        "n_accessions": len(presence),
        "n_accessions_admitted": sum(
            1 for s in presence.values() if any(arms[i]["admitted"] for i in s)
        ),
        # counted_detection_hist[k] = proteins detected in exactly k counted arms
        # (k >= 1), so the viewer can say where one protein's count ranks.
        "counted_detection_hist": counted_hist(presence, arms),
        "surface_preference": {
            "reference": "ProCan (Goncalves et al. 2022, PMID 35839778), mean log2 intensity across 949 cancer cell lines",
            "min_surface_values": MIN_SURFACE_VALUES,
            "min_membrane_values": MIN_MEMBRANE_VALUES,
            "n_scored": len(pref),
            "auroc_canonical_vs_low_or_not": preference_auroc(pref, tiers),
        },
        # Same, over the deep-dived cohort including proteins no counted arm
        # detected (k = 0), overall and per deep-dive tier.
        "cohort_detection_hist": cohort_hists(presence, arms, deep, tiers),
        "accession_normalization": norm_stats,
        "aliases": aliases,
        "excluded_arms": excluded,
        "arms": arms,
    }

    if args.out.exists():
        shutil.rmtree(args.out)
    (args.out / "presence").mkdir(parents=True)
    (args.out / "studies.json").write_text(
        json.dumps(meta, indent=1, ensure_ascii=False) + "\n"
    )
    for i, shard in enumerate(shards):
        (args.out / "presence" / f"{i:02d}.json").write_text(
            json.dumps(shard, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
    write_downloads(args.out, arms, shards)
    logger.info(
        "wrote %d arms (%d publications; %d admitted arms / %d publications), %d accessions (%d in admitted arms) → %s",
        meta["n_arms"],
        meta["n_publications"],
        meta["n_admitted_arms"],
        meta["n_admitted_publications"],
        meta["n_accessions"],
        meta["n_accessions_admitted"],
        args.out,
    )


if __name__ == "__main__":
    main()
