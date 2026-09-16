"""Pin the NCBI→``paper_metadata`` field derivations.

``build_paper_metadata_table.py`` turns an E-utilities ``esummary`` docsum
into the citation line the evidence drawer renders. Everything the reader
actually sees — the byline, the journal/year, the title — is produced by
these small pure helpers, so they're worth pinning: a regression here is
invisible in CI (the table still fills, the Worker still joins) and shows
up only as a wrong-looking citation on the gene page.

The two shapes matter because the two E-utilities databases answer
differently: ``db=pmc`` reports the PubMed id under ``pmid`` in
``articleids``, ``db=pubmed`` under ``pubmed``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build"
    / "build_paper_metadata_table.py"
)
_spec = importlib.util.spec_from_file_location("build_paper_metadata_table", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


# ── uid parsing ───────────────────────────────────────────────────────────


def test_numeric_uid_strips_both_prefixes() -> None:
    # E-utilities wants a bare uid; the record's source_id carries the
    # scheme prefix AND (for PMC) a second 'PMC' inside the accession.
    assert _mod._numeric_uid("PMC:PMC6199259") == "6199259"
    assert _mod._numeric_uid("PMID:40482031") == "40482031"


def test_split_by_db_partitions_by_prefix() -> None:
    pmc, pmid, other = _mod._split_by_db(
        ["PMC:PMC1", "PMID:2", "PMC:PMC3", "DOI:10.1/x"]
    )
    assert pmc == ["PMC:PMC1", "PMC:PMC3"]
    assert pmid == ["PMID:2"]
    # Anything we can't route to an E-utilities db is reported, not fetched
    # under a guessed db — a wrong guess would silently mis-key the row.
    assert other == ["DOI:10.1/x"]


# ── byline ────────────────────────────────────────────────────────────────


def test_surname_drops_initials_but_keeps_compound_names() -> None:
    assert _mod._surname("Bock C") == "Bock"
    assert _mod._surname("van der Berg AB") == "van der Berg"
    # A collective/corporate author has no initials token to strip.
    assert _mod._surname("WHO Expert Committee") == "WHO Expert Committee"


def test_authors_short_shape_by_count() -> None:
    assert _mod._authors_short([]) is None
    assert _mod._authors_short(["Bock C"]) == "Bock"
    assert _mod._authors_short(["Bock C", "Löhr F"]) == "Bock & Löhr"
    assert _mod._authors_short(["Bock C", "Löhr F", "Tumulka F"]) == "Bock et al."


# ── title + year ──────────────────────────────────────────────────────────


def test_clean_title_strips_markup_and_one_trailing_period() -> None:
    assert (
        _mod._clean_title("Insights into <i>TAPL</i> targeting.")
        == "Insights into TAPL targeting"
    )
    # A question-mark ending is the title's own punctuation — don't touch it.
    assert _mod._clean_title("Is the receptor internalized?") == (
        "Is the receptor internalized?"
    )
    assert _mod._clean_title(None) is None
    assert _mod._clean_title("   ") is None


def test_year_parses_from_free_text_pubdate() -> None:
    assert _mod._year("2018 Oct 23") == 2018
    assert _mod._year("2025/06/24 00:00") == 2025
    assert _mod._year(None) is None
    assert _mod._year("in press") is None


# ── docsum → row ──────────────────────────────────────────────────────────


def _pmc_docsum() -> dict:
    return {
        "uid": "6199259",
        "pubdate": "2018 Oct 23",
        "source": "Sci Rep",
        "fulljournalname": "Scientific reports",
        "title": "Structural insights into the transporter TAPL.",
        "authors": [
            {"name": "Bock C", "authtype": "Author"},
            {"name": "Löhr F", "authtype": "Author"},
            {"name": "Tumulka F", "authtype": "Author"},
        ],
        "articleids": [
            {"idtype": "pmid", "value": "30353140"},
            {"idtype": "pmcid", "value": "PMC6199259"},
            {"idtype": "doi", "value": "10.1038/s41598-018-33841-w"},
        ],
    }


def test_row_from_pmc_docsum() -> None:
    row = _mod._row_from_docsum("PMC:PMC6199259", _pmc_docsum(), "pmc")
    # Keyed on the verbatim source_id — that's the string the Worker joins on.
    assert row["source_id"] == "PMC:PMC6199259"
    assert row["pmid"] == "30353140"
    assert row["pmc_id"] == "PMC6199259"
    assert row["doi"] == "10.1038/s41598-018-33841-w"
    assert row["title"] == "Structural insights into the transporter TAPL"
    assert row["authors_short"] == "Bock et al."
    assert json.loads(row["authors_json"]) == ["Bock C", "Löhr F", "Tumulka F"]
    assert row["n_authors"] == 3
    # NLM abbreviation, not the long form — a citation line wants "Sci Rep".
    assert row["journal"] == "Sci Rep"
    assert row["year"] == 2018
    assert row["source_db"] == "pmc"


def test_row_from_pubmed_docsum_reads_pubmed_idtype() -> None:
    # db=pubmed labels its own uid 'pubmed'; db=pmc labels it 'pmid'. Both
    # must land in the same column.
    docsum = {
        "source": "Cell Rep",
        "sortpubdate": "2025/06/24 00:00",
        "title": "Three cryo-EM structures of a protease inhibitor.",
        "authors": [{"name": "Almeida AV"}, {"name": "Jensen KT"}],
        "articleids": [
            {"idtype": "pubmed", "value": "40482031"},
            {"idtype": "doi", "value": "10.1016/j.celrep.2025.115787"},
        ],
    }
    row = _mod._row_from_docsum("PMID:40482031", docsum, "pubmed")
    assert row["pmid"] == "40482031"
    assert row["pmc_id"] is None
    assert row["authors_short"] == "Almeida & Jensen"
    assert row["year"] == 2025


def test_row_from_sparse_docsum_is_all_nulls_not_a_crash() -> None:
    # NCBI can answer with a near-empty docsum. Every field is nullable in
    # the table, and the drawer falls back to the bare accession — so this
    # must produce a row rather than raise.
    row = _mod._row_from_docsum("PMC:PMC1", {}, "pmc")
    assert row["source_id"] == "PMC:PMC1"
    assert row["title"] is None
    assert row["authors_short"] is None
    assert row["authors_json"] is None
    assert row["n_authors"] is None
    assert row["journal"] is None
    assert row["year"] is None


def test_upsert_batch_stays_under_d1_bound_param_cap() -> None:
    # D1 rejects a query with more than 100 bound parameters. The multi-row
    # INSERT binds one param per column per row, so the chunk size and the
    # column count are coupled — this is the guard on that coupling.
    assert len(_mod._COLUMNS) * _mod.UPSERT_CHUNK <= 100
