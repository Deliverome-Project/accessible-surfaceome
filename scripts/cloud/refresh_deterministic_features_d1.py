"""Rebuild published records' deterministic block from D1 and republish.

The deterministic features (topology, isoforms, paralogs, orthologs,
structure, SURFACE-Bind, Schweke) are baked into each record at annotate
time. The Worker only fills a block in at serve time when it is missing or
empty-and-unchecked, so a corrected D1 table never reaches a record that
already carries a stale or wrongly-empty block. This re-fetches the block
with the same loader the annotator uses and republishes — D1-direct, unlike
``refresh_record_post_llm_blocks.py`` / ``scripts/archive/patch_deterministic_*``,
which only edit committed JSON files (three remain).

Only deterministic content changes:

* ``deterministic_features`` — ``fetch_deterministic_features(uniprot_acc)``.
* ``accessibility_risks.ecd_size_assessment`` — re-attached from the canonical
  topology, as the orchestrator does.
* The six filters derived from that block (``deterministic_filters``). The rest
  of ``filters`` is left alone: ``_derive_filters`` also emits LLM-derived and
  paper-count fields it cannot rebuild from a finished record (it would reset
  ``n_papers_found`` to None).

A record is republished only when one of those parts actually changed, under
its existing ``cohort_run_id`` and ``record_generated_at``. ``publish_record``
validates, writes public D1, purges the edge cache, and archives a revision.

Each gene costs a dozen-odd public-D1 queries, so the loop is paced
(``--genes-per-second``, default 0.3) to stay well inside the shared
1,200-request / 5-minute Cloudflare API budget.

    uv run python scripts/cloud/refresh_deterministic_features_d1.py --genes NPM1,ALDOC
    uv run python scripts/cloud/refresh_deterministic_features_d1.py --genes-file targets.json --execute
"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import time
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1 import (
    d1_deterministic as _d1_deterministic,
)
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    fetch_deterministic_features,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    _attach_deterministic_ecd_size_assessment,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.surface_annotation import publish_record
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import (
    SurfaceomeRecord,
)


def deterministic_filters(det, risks) -> dict:
    """The six filters ``_derive_filters`` derives from the deterministic block.

    Mirrors ``surfaceome_v1.orchestrator._derive_filters`` exactly. It is not
    called directly because it rebuilds the whole ``Filters`` block from
    synthesizer inputs a finished record no longer carries in that form.
    """
    canon = det.canonical_topology
    paralog_ids = [
        p.ecd_pct_identity for p in det.paralogs if p.ecd_pct_identity is not None
    ]

    def canonical_species_identity(entries: list) -> float | None:
        for e in entries:
            if e.is_canonical:
                return e.ecd_pct_identity_to_human_canonical
        return None

    return {
        "ecd_accessibility_class": risks.ecd_size_assessment.ecd_accessibility_class,
        "max_paralog_ecd_pct_identity": max(paralog_ids) if paralog_ids else None,
        "mouse_ortholog_ecd_pct_identity": canonical_species_identity(
            det.orthologs.mouse
        ),
        "cyno_ortholog_ecd_pct_identity": canonical_species_identity(
            det.orthologs.cynomolgus
        ),
        "n_term_extracellular": canon.n_terminal_orientation == "extracellular",
        "c_term_extracellular": canon.c_terminal_orientation == "extracellular",
    }


def _cache_version_pickers() -> None:
    """Resolve each served-version lookup once per run, not once per gene.

    ``fetch_deterministic_features`` re-asks D1 which topology, paralog and
    ortholog-ECD versions are current on every call: 10 of its 19 queries, and
    the heaviest ones (whole-table DISTINCT / COUNT scans). The answers cannot
    change during a run, so caching them roughly halves the per-gene D1 cost.
    """
    for name in (
        "_latest_topology_version",
        "_latest_topology_version_for_cohort",
        "_latest_paralog_version",
        "_latest_ortholog_ecd_version",
    ):
        setattr(
            _d1_deterministic, name, functools.cache(getattr(_d1_deterministic, name))
        )


def _without_timestamps(obj):
    """Drop ``retrieved_at`` so a re-fetch alone never counts as a change."""
    if isinstance(obj, dict):
        return {
            k: _without_timestamps(v) for k, v in obj.items() if k != "retrieved_at"
        }
    if isinstance(obj, list):
        return [_without_timestamps(v) for v in obj]
    return obj


def refresh(raw: dict) -> tuple[dict, list[str]]:
    """Return the refreshed record dict and the names of the parts that changed."""
    record = SurfaceomeRecord.model_validate(raw)
    det = fetch_deterministic_features(record.gene.uniprot_acc)
    risks = _attach_deterministic_ecd_size_assessment(record.accessibility_risks, det)
    out = record.model_dump(mode="json")
    changed = []
    new_det = det.model_dump(mode="json")
    if _without_timestamps(new_det) != _without_timestamps(
        out["deterministic_features"]
    ):
        changed.append("deterministic_features")
        out["deterministic_features"] = new_det
    new_size = risks.model_dump(mode="json")["ecd_size_assessment"]
    if new_size != out["accessibility_risks"]["ecd_size_assessment"]:
        changed.append("ecd_size_assessment")
        out["accessibility_risks"]["ecd_size_assessment"] = new_size
    for k, v in deterministic_filters(det, risks).items():
        if v != out["filters"][k]:
            changed.append(f"filters.{k}")
            out["filters"][k] = v
    return out, changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--genes", help="comma-separated gene symbols")
    ap.add_argument(
        "--genes-file", type=Path, help="JSON list of symbols, or {name: [symbols]}"
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="republish changed records (default: dry-run)",
    )
    ap.add_argument("--genes-per-second", type=float, default=0.3)
    ap.add_argument("--log", type=Path, help="append one JSON line per gene")
    args = ap.parse_args()
    load_env()
    _cache_version_pickers()
    logging.basicConfig(level=logging.WARNING)

    genes: set[str] = set(args.genes.split(",")) if args.genes else set()
    if args.genes_file:
        data = json.loads(args.genes_file.read_text())
        genes |= (
            set(data)
            if isinstance(data, list)
            else {g for v in data.values() for g in v}
        )
    if not genes:
        raise SystemExit("pass --genes or --genes-file")

    log = args.log.open("a") if args.log else None
    tally = {"changed": 0, "unchanged": 0, "failed": 0}
    interval = 1.0 / args.genes_per_second
    with D1Client(D1Config.from_env_public()) as pub:
        for i, sym in enumerate(sorted(genes), 1):
            t0 = time.monotonic()
            entry: dict = {"gene": sym}
            try:
                row = pub.query(
                    "SELECT annotation_json, cohort_run_id FROM surface_annotation WHERE gene_symbol = ?;",
                    [sym],
                )
                if not row:
                    raise LookupError("no published record")
                out, changed = refresh(json.loads(row[0]["annotation_json"]))
                entry["changed"] = changed
                if changed:
                    tally["changed"] += 1
                    if args.execute:
                        res = publish_record(
                            SurfaceomeRecord.model_validate(out),
                            cohort_run_id=row[0]["cohort_run_id"],
                        )
                        entry["published"] = res.d1_written
                        if not res.d1_written:
                            entry["skipped_reason"] = res.skipped_reason
                            tally["failed"] += 1
                else:
                    tally["unchanged"] += 1
            except Exception as exc:  # noqa: BLE001 — log and keep going
                entry["error"] = f"{type(exc).__name__}: {exc}"
                tally["failed"] += 1
            if log:
                log.write(json.dumps(entry) + "\n")
                log.flush()
            if i % 25 == 0 or len(genes) <= 25:
                print(f"[{i}/{len(genes)}] {entry}  totals={tally}", flush=True)
            time.sleep(max(0.0, interval - (time.monotonic() - t0)))
    print(
        f"done: {tally}"
        + ("" if args.execute else "  (dry-run — pass --execute to publish)")
    )
    return 1 if tally["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
