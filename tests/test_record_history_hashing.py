"""Pins the content hash that decides whether a served record is a new revision."""

from __future__ import annotations

from accessible_surfaceome.cloud.record_history.hashing import (
    VOLATILE_RECORD_FIELDS,
    canonical_json,
    content_hash_evidence,
    content_hash_md,
    content_hash_record,
)


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json({"b": 1, "a": [1, {"d": 2, "c": 3}]}) == canonical_json(
        {"a": [1, {"c": 3, "d": 2}], "b": 1}
    )


def test_canonical_json_keeps_unicode_verbatim() -> None:
    assert canonical_json({"q": "TGFβ"}) == '{"q":"TGFβ"}'.encode()


def test_record_hash_ignores_only_volatile_fields() -> None:
    a = {
        "gene": {"hgnc_symbol": "X"},
        "confidence": "high",
        "record_generated_at": "2026-01-01T00:00:00Z",
    }
    b = {**a, "record_generated_at": "2026-09-27T12:00:00Z"}
    c = {**a, "confidence": "low"}
    assert content_hash_record(a) == content_hash_record(b)
    assert content_hash_record(a) != content_hash_record(c)


def test_volatile_field_list_is_pinned() -> None:
    # Adding a field here hides real changes from history; do it only after
    # fetching one gene twice and seeing the field differ with nothing else.
    assert VOLATILE_RECORD_FIELDS == frozenset({"record_generated_at"})


def test_evidence_hash_covers_everything() -> None:
    a = {"gene": "X", "evidence": [{"id": "e1"}], "papers": {}}
    b = {**a, "papers": {"PMID:1": {"title": "t"}}}
    assert content_hash_evidence(a) != content_hash_evidence(b)


def test_md_hash_ignores_the_generated_timestamp_only() -> None:
    head = "*Schema v2.14.2 · generated {ts} · model `claude-sonnet-4-6`*\n\nBody"
    a = head.format(ts="2026-07-06T01:33:13.907867Z")
    b = head.format(ts="2026-09-27T10:00:00Z")
    assert content_hash_md(a) == content_hash_md(b)
    assert content_hash_md(a) != content_hash_md(a.replace("Body", "Changed"))


def test_hashes_are_sha256_hex() -> None:
    h = content_hash_record({"a": 1})
    assert len(h) == 64 and all(ch in "0123456789abcdef" for ch in h)
