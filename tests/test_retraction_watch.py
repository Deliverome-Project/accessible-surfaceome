"""Tests for the Retraction Watch index parser + ``gene_literature`` integration.

Exercises:

- :class:`RetractionIndex` lookup semantics (PMID, DOI, empty).
- CSV parsing across plausible Retraction Watch column layouts (the
  upstream schema has shifted occasionally).
- ``_check_retraction`` OR-logic between PMC's ``pubTypeList`` marker and
  the index — either signal flips ``is_retracted`` to True.
- A ``Paper`` constructed from a Europe PMC record with a non-retracted
  pubTypeList but a PMID present in the index is flagged retracted.
"""

from __future__ import annotations

from accessible_surfaceome.tools._shared import retraction_watch as rw
from accessible_surfaceome.tools._shared.europepmc import (
    check_retraction as _check_retraction,
    paper_from_europepmc as _paper_from_europepmc,
)


# ---------------------------------------------------------------------------
# RetractionIndex
# ---------------------------------------------------------------------------


def test_empty_index_never_flags() -> None:
    idx = rw.empty()
    assert not idx.is_retracted(pmid=12345)
    assert not idx.is_retracted(doi="10.1000/foo")
    assert len(idx) == 0


def test_index_from_pmids_flags_listed_pmid() -> None:
    idx = rw.from_pmids([10601354, 14574404])
    assert idx.is_retracted(pmid=10601354)
    assert idx.is_retracted(pmid=14574404)
    assert not idx.is_retracted(pmid=99999)
    assert len(idx) == 2


def test_index_doi_lookup_case_insensitive() -> None:
    idx = rw.RetractionIndex(dois=frozenset({"10.1000/foo"}))
    assert idx.is_retracted(doi="10.1000/foo")
    assert idx.is_retracted(doi="10.1000/FOO")  # case-insensitive
    assert not idx.is_retracted(doi="10.1000/bar")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def test_parse_csv_extracts_pmid_columns() -> None:
    csv_body = (
        "RetractionPubMedID,OriginalPaperPubMedID,RetractionDOI,OriginalPaperDOI,Title\n"
        "20000001,10601354,10.1000/retraction,10.1000/original,Retraction notice\n"
        "20000002,14574404,10.1000/retraction2,10.1000/original2,Another retraction\n"
    )
    idx = rw._parse_csv(csv_body)
    # Both retraction-notice PMIDs and original-paper PMIDs are indexed.
    assert idx.is_retracted(pmid=10601354)
    assert idx.is_retracted(pmid=14574404)
    assert idx.is_retracted(pmid=20000001)
    assert idx.is_retracted(pmid=20000002)
    # DOIs are normalized to lowercase and indexed.
    assert idx.is_retracted(doi="10.1000/original")
    assert idx.is_retracted(doi="10.1000/Retraction".lower())


def test_parse_csv_handles_multi_pmid_cells() -> None:
    """Some Retraction Watch entries pack multiple PMIDs in one cell."""

    csv_body = (
        "OriginalPaperPubMedID,Title\n"
        '"10000001;10000002,10000003",Multi-PMID retraction\n'
    )
    idx = rw._parse_csv(csv_body)
    assert idx.is_retracted(pmid=10000001)
    assert idx.is_retracted(pmid=10000002)
    assert idx.is_retracted(pmid=10000003)


def test_parse_csv_skips_non_integer_values() -> None:
    csv_body = (
        "OriginalPaperPubMedID,Title\n"
        ",Empty PMID row\n"
        "not-a-number,Garbage row\n"
        "12345,Real row\n"
    )
    idx = rw._parse_csv(csv_body)
    assert idx.is_retracted(pmid=12345)
    assert len(idx.pmids) == 1


# ---------------------------------------------------------------------------
# _check_retraction OR-logic
# ---------------------------------------------------------------------------


def test_check_retraction_pmc_marker_alone() -> None:
    is_r, _ = _check_retraction(["Retracted Publication"], index=rw.empty())
    assert is_r is True


def test_check_retraction_index_alone() -> None:
    """No PMC marker but PMID is in the index → still retracted."""

    idx = rw.from_pmids([12345])
    is_r, _ = _check_retraction([], pmid=12345, index=idx)
    assert is_r is True


def test_check_retraction_neither_signal() -> None:
    is_r, _ = _check_retraction(["research-article"], pmid=12345, index=rw.empty())
    assert is_r is False


def test_check_retraction_default_index_none() -> None:
    """Backward-compatible default: index=None still works (no extra signal)."""

    is_r, _ = _check_retraction(["Retracted Publication"])
    assert is_r is True
    is_r2, _ = _check_retraction(["research-article"], pmid=12345)
    assert is_r2 is False


# ---------------------------------------------------------------------------
# _paper_from_europepmc — end-to-end flag propagation
# ---------------------------------------------------------------------------


def _epmc_record(pmid: int, *, pub_types: list[str], title: str = "Some paper") -> dict:
    return {
        "pmid": pmid,
        "id": str(pmid),
        "doi": None,
        "pubYear": "2020",
        "title": title,
        "abstractText": "Abstract.",
        "journalTitle": "J Test",
        "pubTypeList": {"pubType": pub_types},
        "isOpenAccess": "N",
    }


def test_paper_flagged_via_index_when_pmc_silent() -> None:
    """PMC says 'research-article' but the PMID is in the Retraction Watch
    index — the resulting Paper.is_retracted is True."""

    idx = rw.from_pmids([12345])
    record = _epmc_record(12345, pub_types=["research-article"])
    paper = _paper_from_europepmc(record, retraction_index=idx)
    assert paper.is_retracted is True
    assert paper.retraction_checked_at is not None


def test_paper_not_flagged_when_neither_signal() -> None:
    record = _epmc_record(12345, pub_types=["research-article"])
    paper = _paper_from_europepmc(record, retraction_index=rw.empty())
    assert paper.is_retracted is False


def test_paper_flagged_via_pmc_marker_alone() -> None:
    record = _epmc_record(12345, pub_types=["Retracted Publication"])
    paper = _paper_from_europepmc(record, retraction_index=rw.empty())
    assert paper.is_retracted is True
