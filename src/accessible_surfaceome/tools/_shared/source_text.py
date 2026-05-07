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

    def put(self, source: SourceText, *, replace: bool = False) -> None:
        """Register a source body.

        Default is first-write-wins (idempotent — re-registering the same
        ``source_id`` from a duplicate tool call is a no-op). Pass
        ``replace=True`` when the new fetch carries strictly richer content
        than what's already registered — e.g. a UniProt summary body
        (function_text + tissue_specificity_text + subcellular_locations)
        replacing a UniProt skeleton body from an earlier ``resolve`` call.

        Without this escape hatch, the agent's first ``gene_lookup mode=resolve``
        registers a thin body, and any later ``mode=uniprot_summary`` is
        silently dropped — leaving the substring check matching against
        the wrong body and verbatim UniProt quotes failing for no
        observable reason.
        """

        if replace or source.source_id not in self._records:
            self._records[source.source_id] = source

    def get(self, source_id: str) -> SourceText | None:
        return self._records.get(source_id)

    def has(self, source_id: str) -> bool:
        return source_id in self._records

    def all_source_ids(self) -> list[str]:
        return list(self._records)

    @classmethod
    def load_from_disk(cls, in_dir: Path) -> SourceTextStore:
        """Inverse of :meth:`persist_to_disk` — rehydrate a store from a
        directory of per-source JSON files.

        Used by re-promotion paths: when the schema evolves and we want to
        re-run substring + audit against an already-emitted draft without
        re-calling the agent. The bodies in ``data/sources/`` are content-
        addressable, so re-loading them produces an identical store to the
        one the original run had in memory.

        Skips files whose contents don't deserialize as a :class:`SourceText`
        (defensive — a partially-written file from an old crash shouldn't
        sink the whole reload).
        """

        store = cls()
        if not in_dir.exists():
            return store
        for path in sorted(in_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text())
                source = _source_from_payload(payload)
            except Exception:
                continue
            store.put(source)
        return store

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
            target = out_dir / f"{safe_filename(source_id)}.json"
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


def _source_from_payload(payload: dict) -> SourceText:
    """Reconstruct a ``SourceText`` from its persisted JSON form.

    Inverse of the dict produced by ``persist_to_disk``: ``authors`` lifts
    back into a tuple, datetime ISO strings parse back to ``datetime``.
    """

    authors = tuple(payload.get("authors") or ())
    retrieved_at = _parse_datetime(payload["retrieved_at"])
    retraction_checked_at = _parse_datetime(payload["retraction_checked_at"])
    return SourceText(
        source_id=payload["source_id"],
        source_type=payload["source_type"],
        url=payload["url"],
        title=payload.get("title"),
        raw_text=payload["raw_text"],
        normalized_text=payload["normalized_text"],
        content_sha256=payload["content_sha256"],
        normalized_source_sha256=payload["normalized_source_sha256"],
        retrieved_at=retrieved_at,
        publication_type=payload["publication_type"],
        is_retracted=payload["is_retracted"],
        retraction_checked_at=retraction_checked_at,
        license=payload.get("license", "unknown"),
        authors=authors,
        year=payload.get("year"),
        journal=payload.get("journal"),
    )


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def safe_filename(source_id: str) -> str:
    """Map a ``source_id`` to a filesystem-safe filename stem.

    ``PMID:10601354`` → ``PMID_10601354``. The mapping is one-way (we never
    invert), so anything in the source_id beyond ``:`` and ``/`` survives
    unchanged. Used both by ``persist_to_disk`` and by the corpus audit
    walker to find the body for a given source_id.
    """

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


__all__ = ["SourceText", "SourceTextStore", "safe_filename"]
