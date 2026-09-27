"""Content hashes that decide whether a served record is a new revision.

A revision is written only when one of these hashes changes, so the hash
must ignore fields that differ on every run without changing what the
record says — and nothing else. The stored bytes are always the full
response exactly as served; only the *comparison* ignores these fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Top-level record fields that change on every run without changing the
# record's content. Pinned by tests/test_record_history_hashing.py — add a
# field only after fetching one gene twice and seeing it alone differ.
VOLATILE_RECORD_FIELDS: frozenset[str] = frozenset({"record_generated_at"})

# The Markdown export's header line stamps the record's generation time
# ("*Schema v2.14.2 · generated 2026-07-06T01:33:13.907867Z · model …*").
_MD_GENERATED = re.compile(
    r"generated \d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|[+-]\d{2}:\d{2})?"
)


def canonical_json(obj: Any) -> bytes:
    """Key-sorted, whitespace-free UTF-8 JSON — stable across serializers."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash_record(body: dict[str, Any]) -> str:
    """Hash of a served ``/v1/genes/{sym}`` record, minus volatile fields."""
    stable = {k: v for k, v in body.items() if k not in VOLATILE_RECORD_FIELDS}
    return _sha256(canonical_json(stable))


def content_hash_evidence(body: dict[str, Any]) -> str:
    """Hash of a served ``/v1/genes/{sym}/evidence`` ledger (quotes + papers)."""
    return _sha256(canonical_json(body))


def content_hash_md(text: str) -> str:
    """Hash of a served ``/v1/genes/{sym}.md`` export, timestamp normalized."""
    return _sha256(_MD_GENERATED.sub("generated <ts>", text).encode("utf-8"))
