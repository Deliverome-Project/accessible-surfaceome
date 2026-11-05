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

Outputs (committed; the viewer serves them as static files):

* ``viewer/public/data/surface-proteomics/studies.json`` — snapshot provenance
  plus one entry per arm (``arms[i]`` is the arm with index ``i``).
* ``viewer/public/data/surface-proteomics/presence/{NN}.json`` — the presence
  table, sharded by :func:`shard_of` so a gene page fetches one ~30 KB file
  instead of the whole table. Each shard maps a base UniProt accession to
  ``{"s": symbol, "d": 1 if it has a deep-dive page, "a": [arm indices]}``.

Only arms with an ``admitted`` review decision (core / provisional) count as
surface detections. Held arms (e.g. a fully imputed published matrix, where per-
sample detection can't be recovered), arms below the reference-overlap screen,
and comparators (membrane fractionation, whole-lysate glycoproteomes) are kept
and labelled so the viewer can show them as "listed, not counted".

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
import csv
import io
import json
import logging
import shutil
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

SNAPSHOT = "2026-11-02-sweep-v5"
PROCESSED_PREFIX = "sprint3/s3e8-cross-method-surfaceome"
METHOD_AUDIT_PATH = "analysis/sprint3/s3e8-cross-method-surfaceome/method_audit.json"
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
}

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
    """intact_cell | fractionation | lysate — the axis the viewer colours on."""
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


def load_inputs(args: argparse.Namespace) -> tuple[dict, list[dict], dict]:
    if args.source_dir:
        src = Path(args.source_dir)
        manifest = json.loads((src / "manifest.json").read_text())
        detections_text = (src / "detections_long.tsv").read_text()
        audit = json.loads((src / "method_audit.json").read_text())
    else:
        import os

        bucket = os.environ["S3_BUCKET_PROCESSED"]
        prefix = f"{PROCESSED_PREFIX}/{args.snapshot}"
        manifest = json.loads(_read_s3(bucket, f"{prefix}/manifest.json"))
        detections_text = _read_s3(bucket, f"{prefix}/detections_long.tsv").decode()
        audit = json.loads(
            subprocess.run(
                [
                    "git",
                    "-C",
                    args.analysis_repo,
                    "show",
                    f"{args.analysis_ref}:{METHOD_AUDIT_PATH}",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
    detections = list(csv.DictReader(io.StringIO(detections_text), delimiter="\t"))
    return manifest, detections, audit


def _get_json(client: httpx.Client, url: str) -> Any:
    for attempt in range(6):
        r = client.get(url)
        if r.status_code == 200:
            return r.json()
        wait = float(r.headers.get("retry-after") or 10 * (attempt + 1))
        logger.warning("GET %s → %s; retrying in %.0fs", url, r.status_code, wait)
        time.sleep(wait)
    raise RuntimeError(f"GET {url} kept failing")


def load_symbols(api_base: str) -> tuple[dict[str, str], set[str]]:
    """Accession → display symbol (whole-proteome catalog) and the deep-dived set."""
    headers = {"User-Agent": "accessible-surfaceome build (surface-proteomics studies)"}
    with httpx.Client(timeout=120, headers=headers) as client:
        catalog = _get_json(client, f"{api_base}/v1/catalog")
        genes = _get_json(client, f"{api_base}/v1/genes")
    symbols: dict[str, str] = {}
    for row in catalog["rows"]:
        acc = base_accession(row.get("uniprot") or "")
        if acc and acc not in symbols:
            symbols[acc] = row["symbol"]
    deep: set[str] = set()
    for g in genes["genes"]:
        acc = base_accession(g.get("uniprot_acc") or "")
        if acc:
            deep.add(acc)
            symbols[acc] = g["gene_symbol"]
    return symbols, deep


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


def build_arms(
    manifest: dict,
    audit: dict,
    counts: dict[str, int],
    pubmed: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    audit_ds = audit.get("datasets", {})
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
        a = audit_ds.get(sid) or {}
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
                "name": d["name"],
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
                "sample": d.get("human_sample_type") or d.get("cell_or_tissue_type"),
                "status": STATUS_BY_ROLE.get(role, role),
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

    manifest, detections, audit = load_inputs(args)
    counts: dict[str, set[str]] = defaultdict(set)
    for row in detections:
        counts[row["study_id"]].add(base_accession(row["uniprot_accession"]))
    pmids = [
        str(d.get("paper", {}).get("pmid") or d.get("publication_id") or "")
        for d in manifest["datasets"]
    ]
    pubmed = load_pubmed([p for p in pmids if p.isdigit()])
    arms = build_arms(manifest, audit, {k: len(v) for k, v in counts.items()}, pubmed)
    index = {a["id"]: i for i, a in enumerate(arms)}

    symbols, deep = load_symbols(args.api_base)
    presence: dict[str, set[int]] = defaultdict(set)
    fallback_symbol: dict[str, str] = {}
    for row in detections:
        acc = base_accession(row["uniprot_accession"])
        presence[acc].add(index[row["study_id"]])
        if row.get("gene_symbol"):
            fallback_symbol.setdefault(acc, row["gene_symbol"])

    shards: list[dict[str, Any]] = [{} for _ in range(N_SHARDS)]
    for acc in sorted(presence):
        shards[shard_of(acc)][acc] = {
            "s": symbols.get(acc) or fallback_symbol.get(acc) or "",
            "d": 1 if acc in deep else 0,
            "a": sorted(presence[acc]),
        }

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
