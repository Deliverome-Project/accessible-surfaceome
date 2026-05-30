"""Refresh post-LLM blocks of a committed SurfaceomeRecord JSON in place.

The deterministic-features block + the derived filters + the
``headline_risks`` scrub are all computed *after* every LLM call and
read no LLM output beyond the synthesizer draft. That means we can
update a frozen ``.runs/*.json`` (or ``data/eval/.../*.json``) record
to reflect newer post-LLM logic — fresh D1 topology, fresh filter
rules, scrubbed headline_risks — without re-running the agents or
burning a cent in Sonnet/Haiku cost.

Use this when:

* PR #29's DeepTMHMM + Compara D1 tables go live and you want a
  frozen record to show real topology + paralog + cross-species
  ortholog data instead of the old stub zeros.
* The headline-risks scrub rule changes and you want an existing
  frozen record to reflect it.
* ``_derive_filters`` gets a new field or a coherence fix.

What stays frozen: every LLM-generated block (executive_summary,
surface_evidence, biological_context, accessibility_risks, evidence
ledger, confidence, prose). What gets refreshed:

* ``deterministic_features`` — re-fetched from D1 via
  :func:`accessible_surfaceome.agents.surfaceome_v1.d1_deterministic.fetch_deterministic_features`.
* ``filters`` — re-derived from the (now-fresh) deterministic block +
  the (frozen) LLM blocks via
  :func:`accessible_surfaceome.agents.surfaceome_v1.orchestrator._derive_filters`.
* ``executive_summary.headline_risks`` — scrubbed via
  :func:`accessible_surfaceome.agents.surfaceome_v1.orchestrator.scrub_headline_risks`.
* ``primary_evidence_count`` / ``secondary_evidence_count`` /
  ``evidence_count`` — re-tallied from the (frozen) evidence ledger
  in case they drifted.

The script also re-validates the resulting :class:`SurfaceomeRecord`
to catch any cross-field invariants that the new logic might tighten
on, and bails before writing if validation fails.

Usage:

    uv run python scripts/refresh_record_post_llm_blocks.py \\
        .runs/surfaceome_v2_CD81.json

    # Glob mode — refresh every frozen record in a directory
    uv run python scripts/refresh_record_post_llm_blocks.py \\
        .runs/surfaceome_v2_*.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _derive_filters,
    scrub_headline_risks,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

logger = logging.getLogger(__name__)


def _refresh_one(path: Path, *, dry_run: bool) -> tuple[Path, bool, str]:
    """Refresh one record file in place. Returns (path, changed, summary)."""

    raw = json.loads(path.read_text())
    # Preserve top-level non-schema fields the CLI writes alongside the
    # SurfaceomeRecord dump (timing + total_elapsed_s + total_step_seconds).
    extras = {
        k: raw.get(k)
        for k in ("timing", "total_elapsed_s", "total_step_seconds")
        if k in raw
    }
    record = SurfaceomeRecord.model_validate(
        {k: v for k, v in raw.items() if k not in extras}
    )
    uniprot_acc = record.gene.uniprot_acc

    # 1) Fresh deterministic features from D1. If D1 is unreachable
    #    or the gene isn't in the sweep, fall back to the stub so we
    #    don't crash mid-refresh — but log loudly so the operator
    #    knows the record's deterministic block stayed stale.
    try:
        from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
            fetch_deterministic_features,
        )
        det_features = fetch_deterministic_features(uniprot_acc)
        det_source = (
            f"D1 (topology.tool_version={det_features.canonical_topology.tool_version})"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "D1 fetch failed for %s (%s); keeping original deterministic block",
            uniprot_acc,
            exc,
        )
        det_features = record.deterministic_features
        det_source = "STALE (D1 fetch failed; kept original)"

    # 2) Scrub headline_risks against structured backing.
    cleaned_executive = scrub_headline_risks(
        record.executive_summary, record.accessibility_risks
    )

    # 3) Re-derive filters with fresh deterministic + filters_llm. We
    #    don't have the original ``filters_llm`` slice — the synthesizer
    #    embedded it into the record's filters block. Rebuild a
    #    minimal ``SynthesizerLLMFilters`` from the LLM-driven filter
    #    fields that survived (they're untouched).
    from accessible_surfaceome.tools._shared.models import SynthesizerLLMFilters

    filters_llm = SynthesizerLLMFilters(
        expression_level=record.filters.expression_level,
        expression_breadth=record.filters.expression_breadth,
        surface_specificity=record.filters.surface_specificity,
    )
    fresh_filters = _derive_filters(
        executive_summary=cleaned_executive,
        surface_evidence=record.surface_evidence,
        biological_context=record.biological_context,
        accessibility_risks=record.accessibility_risks,
        filters_llm=filters_llm,
        deterministic_features=det_features,
        n_evidence=len(record.evidence),
    )

    # 4) Re-tally evidence counts.
    primary = sum(1 for e in record.evidence if e.evidence_tier == "primary")
    secondary = sum(1 for e in record.evidence if e.evidence_tier == "secondary")

    # 5) Build the refreshed record + re-validate.
    refreshed = record.model_copy(
        update={
            "deterministic_features": det_features,
            "filters": fresh_filters,
            "executive_summary": cleaned_executive,
            "primary_evidence_count": primary,
            "secondary_evidence_count": secondary,
            "evidence_count": len(record.evidence),
        }
    )
    # Round-trip through validation to surface any new invariants.
    SurfaceomeRecord.model_validate(refreshed.model_dump(mode="json"))

    out: dict[str, object] = refreshed.model_dump(mode="json")
    for k, v in extras.items():
        if v is not None:
            out[k] = v

    summary_lines = [
        f"  gene: {record.gene.hgnc_symbol} ({uniprot_acc})",
        f"  deterministic: {det_source}",
        f"    tm_helix_count: "
        f"{record.deterministic_features.canonical_topology.tm_helix_count} → "
        f"{det_features.canonical_topology.tm_helix_count}",
        f"    ecd_length_residues: "
        f"{record.deterministic_features.canonical_topology.ecd_length_residues} → "
        f"{det_features.canonical_topology.ecd_length_residues}",
        f"    n_paralogs: {len(record.deterministic_features.paralogs)} → "
        f"{len(det_features.paralogs)}",
        f"    n_orthologs (mouse+rat+cyno): "
        f"{len(record.deterministic_features.orthologs.mouse) + len(record.deterministic_features.orthologs.rat) + len(record.deterministic_features.orthologs.cynomolgus)} → "
        f"{len(det_features.orthologs.mouse) + len(det_features.orthologs.rat) + len(det_features.orthologs.cynomolgus)}",
        f"  headline_risks: {list(record.executive_summary.headline_risks)} → "
        f"{list(cleaned_executive.headline_risks)}",
    ]
    summary = "\n".join(summary_lines)

    if dry_run:
        return path, False, summary
    path.write_text(json.dumps(out, indent=2))
    return path, True, summary


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="One or more SurfaceomeRecord JSON paths (globs supported by the shell)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute refresh + print summary but do not overwrite the file.",
    )
    args = parser.parse_args(argv)

    for path in args.paths:
        if not path.exists():
            logger.warning("skipping %s — file not found", path)
            continue
        try:
            out_path, changed, summary = _refresh_one(path, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to refresh %s: %s", path, exc)
            continue
        verb = "DRY-RUN" if args.dry_run else ("WROTE" if changed else "SKIPPED")
        print(f"\n=== {verb}: {out_path} ===")
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
