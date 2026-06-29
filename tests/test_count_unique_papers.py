"""Unit tests for ``_count_unique_papers``.

The helper walks ``Evidence.spans[i].source.source_id`` to dedupe
papers across the evidence list. Concerned about three regression
classes:

  1. None semantics — ``None`` evidence (caller doesn't know) must
     return ``None``; an empty list (real measurement) must return ``0``.
  2. Span-walking — a row with no spans (entailment_verified=False)
     must not crash; multiple spans on one row must dedupe; multiple
     rows pointing at the same paper must dedupe.
  3. Source-id presence — a span with ``source=None`` or
     ``source.source_id=None`` must be skipped silently.

These are the exact span shapes the viewer's understudied-genes filter
depends on getting right.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _count_unique_papers,
)
from accessible_surfaceome.tools._shared.models import Evidence


def _span(source_id: str | None) -> SimpleNamespace:
    """Minimal duck-typed Evidence.spans[i] shape — the helper only
    reads ``span.source.source_id`` via ``getattr``, so we don't need
    a full pydantic Evidence instance."""
    if source_id is None:
        return SimpleNamespace(source=None)
    return SimpleNamespace(source=SimpleNamespace(source_id=source_id))


def _ev(*source_ids: str | None) -> Evidence:
    """Build an Evidence-shaped object with the given source_ids on
    successive spans. Pass no args for an empty-spans row
    (entailment_verified=False shape).

    Cast to ``Evidence`` so ``ty`` accepts these duck-typed mocks as
    valid args to ``_count_unique_papers(list[Evidence] | None)`` —
    the helper only does ``getattr`` reads on ``span.source.source_id``
    and never invokes a pydantic method, so the cast is structurally
    sound at runtime."""
    obj: Any = SimpleNamespace(spans=[_span(s) for s in source_ids])
    return cast(Evidence, obj)


def test_none_evidence_returns_none() -> None:
    """``None`` evidence = caller doesn't know. Distinct from empty
    list, which is a real-zero measurement."""
    assert _count_unique_papers(None) is None


def test_empty_evidence_list_returns_zero() -> None:
    """Empty list is a real measurement, not 'unknown' — the agent
    surfaced 0 unique papers for this gene."""
    assert _count_unique_papers([]) == 0


def test_single_paper_single_span() -> None:
    assert _count_unique_papers([_ev("PMID:12345")]) == 1


def test_dedupes_across_rows() -> None:
    """Two evidence rows backed by the same paper count as one."""
    assert _count_unique_papers([_ev("PMID:12345"), _ev("PMID:12345")]) == 1


def test_dedupes_within_row() -> None:
    """Multiple spans on one row backed by the same paper count as one."""
    assert _count_unique_papers([_ev("PMID:12345", "PMID:12345")]) == 1


def test_different_papers_count_distinctly() -> None:
    assert _count_unique_papers([
        _ev("PMID:12345"),
        _ev("PMID:67890"),
        _ev("DOI:10.1/abc"),
    ]) == 3


def test_evidence_row_without_spans_skipped() -> None:
    """``entailment_verified=False`` rows have empty spans; they must
    not crash the walk."""
    assert _count_unique_papers([_ev(), _ev("PMID:12345")]) == 1


def test_span_with_no_source_skipped() -> None:
    """A span whose ``source`` is None (unrecoverable provenance)
    contributes nothing — match the doc invariant that only
    verified-anchor rows count."""
    assert _count_unique_papers([_ev(None, "PMID:99")]) == 1


def test_all_spanless_rows_returns_zero() -> None:
    """Several rows with no usable spans → 0 (real measurement that
    nothing anchored), NOT None."""
    assert _count_unique_papers([_ev(), _ev(), _ev(None)]) == 0
