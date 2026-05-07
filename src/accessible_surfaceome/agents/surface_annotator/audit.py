"""Opt-in claim-entailment audit + corpus round-trip verification.

Two related but separable provenance gates:

1. **Entailment audit** (:func:`make_sonnet_entailment_audit` /
   :func:`apply_entailment_audit`). Catches the failure mode the substring
   check can't see: "right citation, wrong direction" — the agent quoted
   the source correctly, but the quote *contradicts* the claim's
   ``direction`` instead of supporting it. Implemented as a separate
   Sonnet call per ``Evidence`` record, gated behind the ``--audit``
   flag (cost is ~$0.05–0.15/gene at typical evidence counts).

2. **Corpus round-trip audit** (:func:`audit_record` /
   :func:`audit_record_path`). Confirms that every persisted
   :class:`EvidenceSpan` is reproducible from the cached source body in
   ``data/sources/`` — re-normalize, re-locate the quote at
   ``char_offset``, recompute every ``sha256``. Run via
   ``accessible-surfaceome agents audit-corpus``; doesn't require the
   model.

Both audits are non-destructive: they record results into
``Evidence.entailment_audit_passed`` / a returned report dataclass without
mutating spans or rejecting records. Persist-with-flags is the
project-wide policy.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from accessible_surfaceome.tools._shared.models import (
    Evidence,
    EvidenceSpan,
    SurfaceomeRecord,
)
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.source_text import safe_filename

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entailment audit
# ---------------------------------------------------------------------------


class EntailmentAuditCallable(Protocol):
    """One-shot audit: ``(claim, direction, quote) → True | False | None``.

    ``None`` means the audit couldn't run (e.g. API error). Callers should
    treat ``None`` as "not audited" rather than "failed" so retries remain
    possible.
    """

    def __call__(self, *, claim: str, direction: str, quote: str) -> bool | None: ...


_AUDIT_SYSTEM = (
    "You are an evidence-direction validator. Given a verbatim quote from a "
    "scientific source and a claim that cites it, decide whether the quote "
    "actually supports the claim in the stated direction.\n\n"
    "Output rules:\n"
    "- supports → quote provides evidence consistent with the claim's direction\n"
    "- refutes → quote provides evidence contradicting the claim's direction\n"
    "- ambiguous → quote is on-topic but doesn't clearly support or refute\n\n"
    "If direction='supports', the audit passes only when the quote *supports* "
    "the claim. If direction='refutes', the audit passes only when the quote "
    "*refutes* the claim. If direction='ambiguous', the audit passes when the "
    "quote is on-topic (supports, refutes, or ambiguous all count).\n\n"
    "Return a JSON object: {\"entailed\": true|false, \"reasoning\": \"<one sentence>\"}."
)


_DEFAULT_AUDIT_MODEL = "claude-sonnet-4-6"


def make_sonnet_entailment_audit(
    client: Any,
    *,
    model: str = _DEFAULT_AUDIT_MODEL,
    max_tokens: int = 256,
) -> EntailmentAuditCallable:
    """Build an audit callable backed by a Sonnet ``messages.create`` call.

    ``client`` is an ``anthropic.Anthropic`` (typed loosely so this module
    doesn't have to import the SDK at module-top — it's an optional
    dependency for the audit path).

    The closure returned is safe to call concurrently as long as the
    underlying ``Anthropic`` client supports it (which it does by default
    over multiple HTTP connections).
    """

    def _audit(*, claim: str, direction: str, quote: str) -> bool | None:
        prompt = _build_audit_prompt(claim=claim, direction=direction, quote=quote)
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=_AUDIT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # network, billing, anything
            logger.warning("entailment audit call failed: %s", exc)
            return None

        text = _first_text_block(resp)
        if text is None:
            return None
        return _parse_entailment_response(text)

    return _audit


def apply_entailment_audit(
    evidence: list[Evidence],
    *,
    audit: EntailmentAuditCallable,
) -> list[Evidence]:
    """Run the audit on every verified Evidence record; mutate in place.

    Only ``entailment_verified=True`` records are audited — the others have
    no anchored quote to evaluate against. A ``None`` audit result leaves
    ``entailment_audit_passed=None`` (a transient failure shouldn't look
    the same as a hard "no, doesn't entail" failure).

    Returns the same list for chaining; callers don't need to capture the
    return value but it makes the mutation explicit.
    """

    for evi in evidence:
        if not evi.entailment_verified or not evi.spans:
            # Nothing to audit — leave entailment_audit_passed as whatever
            # the model emitted (None).
            continue
        # Use the first span's quote — there's never more than one in
        # current schema, but the field is a list so we're explicit.
        quote = evi.spans[0].quote
        result = audit(claim=evi.claim, direction=evi.direction, quote=quote)
        evi.entailment_audit_passed = result
        if result is False:
            evi.validation_warnings.append(
                "entailment audit: quote does not support the claim in the stated direction"
            )
        elif result is None:
            evi.validation_warnings.append(
                "entailment audit: not run (audit call failed or returned no parseable result)"
            )
    return evidence


def _build_audit_prompt(*, claim: str, direction: str, quote: str) -> str:
    return (
        f"claim: {claim}\n"
        f"direction: {direction}\n"
        f"quote: {quote}\n\n"
        "Does the quote support the claim in the stated direction? "
        'Reply with JSON: {"entailed": true|false, "reasoning": "<one sentence>"}.'
    )


def _first_text_block(resp: Any) -> str | None:
    """Pull the first text block out of an Anthropic ``Message`` response.

    The SDK may return ``content`` as a list of ``TextBlock`` objects with
    a ``text`` attribute; fall back to dict access for hand-rolled mocks.
    """

    content = getattr(resp, "content", None)
    if content is None and isinstance(resp, dict):
        content = resp.get("content")
    if not content:
        return None
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if isinstance(text, str):
            return text
    return None


def _parse_entailment_response(text: str) -> bool | None:
    """Pull the ``entailed`` boolean out of the Sonnet response.

    Be lenient: the model usually emits a clean JSON object, but some
    responses wrap it in prose or a markdown fence. We grab the first
    ``{...}`` substring and try to parse.
    """

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        logger.warning("entailment audit response had no JSON object: %r", text[:200])
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("entailment audit response JSON parse failed: %s", exc)
        return None
    value = payload.get("entailed")
    if isinstance(value, bool):
        return value
    return None


# ---------------------------------------------------------------------------
# Corpus round-trip audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpanAuditResult:
    """One span's verification result.

    Each boolean records the outcome of a single deterministic check; if
    any are ``False`` the span is not reproducible from the persisted
    corpus and ``mismatches`` enumerates the failed checks.
    """

    evidence_id: str
    source_id: str
    char_offset: int
    found_in_store: bool
    content_sha256_match: bool | None
    normalized_sha256_match: bool | None
    quote_sha256_match: bool | None
    char_offset_match: bool | None
    mismatches: tuple[str, ...]


@dataclass
class RecordAuditReport:
    """Roll-up of every span audit for one persisted ``SurfaceomeRecord``."""

    annotation_path: Path
    sources_dir: Path
    span_results: list[SpanAuditResult] = field(default_factory=list)

    @property
    def n_spans(self) -> int:
        return len(self.span_results)

    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.span_results if not r.mismatches)

    @property
    def n_failed(self) -> int:
        return self.n_spans - self.n_passed

    @property
    def all_passed(self) -> bool:
        return self.n_failed == 0


def audit_record_path(
    annotation_path: Path,
    *,
    sources_dir: Path,
) -> RecordAuditReport:
    """Load the persisted record at ``annotation_path`` and audit every span."""

    record = SurfaceomeRecord.model_validate_json(annotation_path.read_text())
    return audit_record(record, annotation_path=annotation_path, sources_dir=sources_dir)


def audit_record(
    record: SurfaceomeRecord,
    *,
    annotation_path: Path,
    sources_dir: Path,
) -> RecordAuditReport:
    """Walk every Evidence's spans and verify each one against the cached corpus.

    Per-span pipeline:

    1. Look up the source body at ``data/sources/<safe_source_id>.json``.
       Missing → ``found_in_store=False`` and the span is marked failed.
    2. Recompute ``content_sha256`` from the source's ``raw_text`` and
       compare to the persisted ``EvidenceSpan.source.content_sha256``.
    3. Re-normalize the source body and compare its sha256 to the
       persisted ``EvidenceSpan.normalized_source_sha256``.
    4. Recompute ``sha256(span.quote)`` and compare to
       ``EvidenceSpan.quote_sha256``.
    5. Confirm ``find_quote_in_normalized(normalize(quote), normalize(raw))``
       returns ``EvidenceSpan.char_offset``.

    Returns a :class:`RecordAuditReport` rolling each span result up. The
    function never raises on a mismatch — the report is the deliverable.
    """

    report = RecordAuditReport(annotation_path=annotation_path, sources_dir=sources_dir)
    for evi in record.evidence:
        for span in evi.spans:
            report.span_results.append(
                _audit_span(span, evidence_id=evi.evidence_id, sources_dir=sources_dir)
            )
    return report


def _audit_span(
    span: EvidenceSpan, *, evidence_id: str, sources_dir: Path
) -> SpanAuditResult:
    source_id = span.source.source_id
    body_path = sources_dir / f"{safe_filename(source_id)}.json"
    if not body_path.exists():
        return SpanAuditResult(
            evidence_id=evidence_id,
            source_id=source_id,
            char_offset=span.char_offset,
            found_in_store=False,
            content_sha256_match=None,
            normalized_sha256_match=None,
            quote_sha256_match=None,
            char_offset_match=None,
            mismatches=(f"source body missing at {body_path}",),
        )

    payload = json.loads(body_path.read_text())
    raw_text = payload.get("raw_text") or ""
    content_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    normalized = normalize_for_quote_matching(raw_text)
    normalized_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    quote_sha256 = hashlib.sha256(span.quote.encode("utf-8")).hexdigest()

    content_match = content_sha256 == span.source.content_sha256
    normalized_match = normalized_sha256 == span.normalized_source_sha256
    quote_match = quote_sha256 == span.quote_sha256

    found_offset = find_quote_in_normalized(
        normalize_for_quote_matching(span.quote), normalized
    )
    offset_match = found_offset == span.char_offset

    mismatches: list[str] = []
    if not content_match:
        mismatches.append(
            f"content_sha256 mismatch: stored={span.source.content_sha256[:12]}…, "
            f"recomputed={content_sha256[:12]}…"
        )
    if not normalized_match:
        mismatches.append(
            f"normalized_source_sha256 mismatch: stored={span.normalized_source_sha256[:12]}…, "
            f"recomputed={normalized_sha256[:12]}…"
        )
    if not quote_match:
        mismatches.append(
            f"quote_sha256 mismatch: stored={span.quote_sha256[:12]}…, "
            f"recomputed={quote_sha256[:12]}…"
        )
    if not offset_match:
        mismatches.append(
            f"char_offset mismatch: stored={span.char_offset}, recomputed={found_offset!r}"
        )

    return SpanAuditResult(
        evidence_id=evidence_id,
        source_id=source_id,
        char_offset=span.char_offset,
        found_in_store=True,
        content_sha256_match=content_match,
        normalized_sha256_match=normalized_match,
        quote_sha256_match=quote_match,
        char_offset_match=offset_match,
        mismatches=tuple(mismatches),
    )


def format_report(report: RecordAuditReport) -> str:
    """Render a human-readable summary suitable for stdout."""

    lines: list[str] = [
        f"audit: {report.annotation_path.name}",
        f"  spans: {report.n_spans}  passed: {report.n_passed}  failed: {report.n_failed}",
    ]
    for result in report.span_results:
        if result.mismatches:
            lines.append(
                f"  ✗ {result.evidence_id} ← {result.source_id} (offset={result.char_offset})"
            )
            for m in result.mismatches:
                lines.append(f"      • {m}")
        else:
            lines.append(
                f"  ✓ {result.evidence_id} ← {result.source_id} (offset={result.char_offset})"
            )
    return "\n".join(lines)


__all__ = [
    "EntailmentAuditCallable",
    "make_sonnet_entailment_audit",
    "apply_entailment_audit",
    "SpanAuditResult",
    "RecordAuditReport",
    "audit_record",
    "audit_record_path",
    "format_report",
]
