"""Render a persisted ``SurfaceomeRecord`` as a human-readable Evidence chain.

Output format mirrors ``audit-corpus`` so the two commands feel like a
matched pair: ``view`` shows the full claim + quote + deep-link for every
Evidence record, ``audit-corpus`` re-verifies the same chain against the
cached source corpus.

The deep-links use the W3C text-fragment spec
(:func:`accessible_surfaceome.tools._shared.source_links.highlight_url`)
to scroll-to-and-highlight the verbatim quote on the source's rendered
page. PMID quotes route to Europe PMC (more reliable than PubMed for
fragment matching); UniProt topology quotes drop the fragment and use a
section anchor (since the synthesized topology rendering doesn't appear
verbatim on UniProt's website).
"""

from __future__ import annotations

from pathlib import Path

from accessible_surfaceome.tools._shared.models import SurfaceomeRecord
from accessible_surfaceome.tools._shared.source_links import highlight_url_for_span


def format_record(annotation_path: Path) -> str:
    """Load the record at ``annotation_path`` and format it for stdout."""

    record = SurfaceomeRecord.model_validate_json(annotation_path.read_text())
    return _render(record, annotation_path=annotation_path)


def _render(record: SurfaceomeRecord, *, annotation_path: Path) -> str:
    lines: list[str] = []
    lines.append(f"view: {annotation_path.name}  (schema={record.schema_version})")
    lines.append(
        f"  {record.gene.hgnc_symbol} ({record.gene.uniprot_acc}) — "
        f"tier={record.targetability.tier}, "
        f"surface={record.surface_biology.surface_status}, "
        f"topology={record.surface_biology.topology}"
    )
    verified = sum(1 for e in record.evidence if e.entailment_verified)
    audited_pass = sum(1 for e in record.evidence if e.entailment_audit_passed is True)
    audited_fail = sum(1 for e in record.evidence if e.entailment_audit_passed is False)
    lines.append(
        f"  evidence: {len(record.evidence)} ({verified} substring-verified, "
        f"{audited_pass} audit-passed, {audited_fail} audit-failed)"
    )
    lines.append("")

    for evi in record.evidence:
        verified_mark = "✓" if evi.entailment_verified else "✗"
        if evi.entailment_audit_passed is True:
            audit_mark = "✓"
        elif evi.entailment_audit_passed is False:
            audit_mark = "✗"
        else:
            audit_mark = "—"
        lines.append(
            f"[verified={verified_mark} audit={audit_mark}] {evi.evidence_id} "
            f"({evi.claim_type}, {evi.direction}, {evi.evidence_tier}/{evi.confidence})"
        )
        lines.append(f"  claim: {evi.claim}")
        if evi.spans:
            span = evi.spans[0]
            lines.append(f"  source: {span.source.source_id}  section={span.section}")
            lines.append(f"  quote: \"{span.quote}\"")
            lines.append(f"  link: {highlight_url_for_span(span)}")
        else:
            lines.append(f"  source: {evi.claim_type} (no anchored span)")
        for w in evi.validation_warnings:
            lines.append(f"  ⚠ {w}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["format_record"]
