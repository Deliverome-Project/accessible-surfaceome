"""Process-local registry of source bodies the agent has fetched in a session.

Every paper, patent, or UniProt entry the agent's tools fetch gets registered
here as a :class:`SourceText`. The orchestrator's evidence-promotion step
(``EvidenceClaim`` → ``Evidence``) consults this registry to look up the
canonical body for a ``source_id`` and run the substring check.

Two reasons this is its own layer rather than just reading ``CachedHTTP``:

1. **Semantic identity, not URL.** ``CachedHTTP`` is keyed by HTTP method +
   URL + body. The orchestrator wants a stable ``source_id`` like
   ``"PMID:10601354"`` regardless of which URL produced it (Europe PMC search
   vs. fetch_abstract vs. fetch_fulltext all yield the same paper).
2. **Pre-computed normalization + hashes.** The substring check needs the
   normalized body and its sha256; ``SourceText`` carries both so we don't
   recompute on every claim.

Process-local — one store per orchestrator run. Tool handlers register sources
as side effects; the promotion step reads.

## Source ID format

Stable, human-readable, namespaced by source type:

- ``"PMID:10601354"`` — PubMed (Europe PMC's MED source). Integer PMID.
- ``"PMC:PMC2195717"`` — PMC OA full text. The full PMC accession including
  the ``PMC`` prefix.
- ``"UniProt:Q9UBP8"`` — UniProtKB entry, keyed by accession.
- ``"WO:WO2024036333A2"`` — patent disclosure (incl. EP/US — the prefix is
  literally ``WO:`` regardless of whether the underlying number starts with
  WO/EP/US, so the format is uniform).

The agent emits these strings in ``EvidenceClaim.source_id``. New source
types add a new prefix; the prefix MUST be unique and the suffix should be
the canonical identifier the upstream service uses.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import License, PublicationType, SourceType


@dataclass(frozen=True)
class SourceText:
    """One source body with the metadata needed to construct a ``SourceRef``.

    The pair (``raw_text``, ``content_sha256``) anchors the bytes we fetched.
    The pair (``normalized_text``, ``normalized_source_sha256``) anchors the
    string the substring check ran against. Both pairs are persisted into the
    eventual ``Evidence`` record so the chain is reproducible.

    Optional ``authors``, ``year``, ``journal`` carry citation metadata not on
    the ``SourceRef`` itself — the persisted corpus needs them for citation
    formatting in any downstream display.
    """

    source_id: str
    source_type: SourceType
    url: str
    title: str | None
    raw_text: str
    normalized_text: str
    content_sha256: str
    normalized_source_sha256: str
    retrieved_at: datetime
    publication_type: PublicationType
    is_retracted: bool
    retraction_checked_at: datetime
    license: License = "unknown"
    authors: tuple[str, ...] = ()  # frozen — tuple instead of list
    year: int | None = None
    journal: str | None = None


@dataclass
class SourceTextStore:
    """In-memory registry: ``source_id`` → :class:`SourceText`.

    Tool handlers register sources as they fetch; the orchestrator's
    promotion step reads. ``put`` is idempotent — re-registering the same
    ``source_id`` is a no-op (we keep the first fetch's metadata to avoid
    timestamp churn within a session).
    """

    _records: dict[str, SourceText] = field(default_factory=dict)

    def put(self, source: SourceText) -> None:
        self._records.setdefault(source.source_id, source)

    def get(self, source_id: str) -> SourceText | None:
        return self._records.get(source_id)

    def has(self, source_id: str) -> bool:
        return source_id in self._records

    def all_source_ids(self) -> list[str]:
        return list(self._records)

    def persist_to_disk(self, out_dir: Path) -> dict[str, Path]:
        """Write every registered ``SourceText`` to ``out_dir`` as one JSON
        file per source. Returns ``{source_id: written_path}``.

        Filenames replace ``:`` with ``_`` so they're filesystem-safe across
        platforms (``PMID:10601354`` → ``PMID_10601354.json``). Atomic writes
        via tempfile + rename so a crash mid-write doesn't leave a half-baked
        record. Existing files are overwritten — content-addressable cache,
        so a divergent ``content_sha256`` means the upstream changed and the
        new fetch is canonical.
        """

        out_dir.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        for source_id, source in self._records.items():
            target = out_dir / f"{_safe_filename(source_id)}.json"
            payload = asdict(source)
            # ``authors`` is a tuple in the dataclass; serialize as list.
            payload["authors"] = list(payload.get("authors") or ())
            # datetimes → ISO strings for round-trippable JSON.
            for key in ("retrieved_at", "retraction_checked_at"):
                value = payload.get(key)
                if isinstance(value, datetime):
                    payload[key] = value.isoformat()
            _atomic_write_json(target, payload)
            written[source_id] = target
        return written


def _safe_filename(source_id: str) -> str:
    return source_id.replace(":", "_").replace("/", "_")


def _atomic_write_json(path: Path, payload: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.stem + ".", suffix=".json.tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True, default=str)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        finally:
            raise


__all__ = ["SourceText", "SourceTextStore"]
