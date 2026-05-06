"""Tests for ``SourceTextStore.persist_to_disk`` and the author plumbing.

These cover the source-corpus side of provenance: every source the agent
fetches is written to ``data/sources/<id>.json`` so a future UI (or audit
script) can render quote-in-context without re-fetching upstream.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


def _make_source(
    *,
    source_id: str = "PMID:10601354",
    raw_text: str = "Short-term cultures of proximal tubule cells expressed KAAG1.",
    title: str = "Brandle et al.",
    authors: tuple[str, ...] = ("Van Den Eynde BJ", "Gaugler B"),
    year: int | None = 1999,
    journal: str | None = "J Exp Med",
) -> SourceText:
    normalized = normalize_for_quote_matching(raw_text)
    return SourceText(
        source_id=source_id,
        source_type="pubmed",
        url="https://pubmed.ncbi.nlm.nih.gov/10601354/",
        title=title,
        raw_text=raw_text,
        normalized_text=normalized,
        content_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        normalized_source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        retrieved_at=datetime.now(UTC),
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=datetime.now(UTC),
        authors=authors,
        year=year,
        journal=journal,
    )


def test_persist_writes_one_file_per_source(tmp_path: Path) -> None:
    store = SourceTextStore()
    store.put(_make_source(source_id="PMID:10601354"))
    store.put(_make_source(source_id="WO:WO2024036333A2", raw_text="Bispecific binding agents."))

    written = store.persist_to_disk(tmp_path)

    assert set(written) == {"PMID:10601354", "WO:WO2024036333A2"}
    assert (tmp_path / "PMID_10601354.json").exists()
    assert (tmp_path / "WO_WO2024036333A2.json").exists()


def test_persist_filename_replaces_colon(tmp_path: Path) -> None:
    """Filenames must be filesystem-safe — ``:`` becomes ``_``."""

    store = SourceTextStore()
    store.put(_make_source(source_id="PMID:10601354"))

    written = store.persist_to_disk(tmp_path)
    path = written["PMID:10601354"]

    assert ":" not in path.name
    assert path.name == "PMID_10601354.json"


def test_persist_round_trips_metadata(tmp_path: Path) -> None:
    store = SourceTextStore()
    store.put(
        _make_source(
            authors=("Van Den Eynde BJ", "Gaugler B", "Boon T"),
            year=1999,
            journal="J Exp Med",
        )
    )

    store.persist_to_disk(tmp_path)
    payload = json.loads((tmp_path / "PMID_10601354.json").read_text())

    assert payload["source_id"] == "PMID:10601354"
    assert payload["authors"] == ["Van Den Eynde BJ", "Gaugler B", "Boon T"]
    assert payload["year"] == 1999
    assert payload["journal"] == "J Exp Med"
    assert payload["raw_text"].startswith("Short-term cultures")
    assert payload["normalized_text"] == normalize_for_quote_matching(payload["raw_text"])
    # datetime fields serialize as ISO strings
    assert isinstance(payload["retrieved_at"], str)
    assert isinstance(payload["retraction_checked_at"], str)


def test_persist_overwrites_existing_file(tmp_path: Path) -> None:
    """Content-addressable cache: new fetch with different bytes overwrites."""

    store = SourceTextStore()
    store.put(_make_source(raw_text="Original abstract."))
    store.persist_to_disk(tmp_path)

    target = tmp_path / "PMID_10601354.json"
    first = json.loads(target.read_text())

    store2 = SourceTextStore()
    store2.put(_make_source(raw_text="Updated abstract with new wording."))
    store2.persist_to_disk(tmp_path)
    second = json.loads(target.read_text())

    assert first["content_sha256"] != second["content_sha256"]
    assert second["raw_text"].startswith("Updated abstract")


def test_persist_empty_store_creates_dir_no_files(tmp_path: Path) -> None:
    target = tmp_path / "sources"
    store = SourceTextStore()

    written = store.persist_to_disk(target)

    assert written == {}
    assert target.exists()
    assert list(target.iterdir()) == []


def test_authors_default_empty_tuple() -> None:
    """Sources fetched without author metadata get an empty tuple, not a crash."""

    src = SourceText(
        source_id="UniProt:Q9UBP8",
        source_type="uniprot",
        url="https://rest.uniprot.org/uniprotkb/Q9UBP8.json",
        title=None,
        raw_text="entry data",
        normalized_text="entry data",
        content_sha256="x",
        normalized_source_sha256="x",
        retrieved_at=datetime.now(UTC),
        publication_type="db_entry",
        is_retracted=False,
        retraction_checked_at=datetime.now(UTC),
    )
    assert src.authors == ()
    assert src.year is None
    assert src.journal is None
