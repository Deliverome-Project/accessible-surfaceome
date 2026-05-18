"""Tests for ``gene_literature(mode="recent_corpus")``.

Three behaviors that have to hold or the SRC regression test
(Delaveris 2026) will silently miss the verdict-shifter:

1. PubTator is called with ``sort="date desc"`` across all pages.
2. The pagination loop bails early when a page returns zero new PMIDs.
3. The abstract pre-filter keeps papers that mention surface/membrane
   vocabulary and drops papers that don't.
"""

from __future__ import annotations

from typing import Any, cast

from accessible_surfaceome.tools import gene_literature as gl
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import LiteraturePack


PUBTATOR_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"


class _DispatchHTTP:
    """Routes get_json by URL substring so PubTator + EuropePMC can be faked together."""

    def __init__(
        self,
        *,
        pubtator_pages: list[dict[str, Any]],
        epmc_bulk_payload: dict[str, Any],
    ):
        self._pubtator_pages = list(pubtator_pages)
        self._epmc = epmc_bulk_payload
        self.pubtator_calls: list[dict[str, Any]] = []
        self.epmc_calls: list[dict[str, Any]] = []

    def get_json(self, url: str, *, source: str, ttl_days: int, params: dict | None = None) -> Any:
        if "pubtator" in url:
            self.pubtator_calls.append({"url": url, "params": params})
            idx = int((params or {}).get("page", "1")) - 1
            if idx < len(self._pubtator_pages):
                return self._pubtator_pages[idx]
            return {"count": 0, "current": idx + 1, "results": []}
        if "europepmc" in url or "ebi.ac.uk" in url:
            self.epmc_calls.append({"url": url, "params": params})
            return self._epmc
        raise AssertionError(f"unexpected URL: {url}")


def _pubtator_hit(pmid: int) -> dict[str, Any]:
    return {
        "pmid": pmid,
        "pmcid": None,
        "doi": None,
        "title": f"Paper {pmid}",
        "journal": "J Test",
        "date": "2026-03-12T00:00:00Z",
        "score": 0.5,
        "authors": [],
    }


def _epmc_record(pmid: int, title: str, abstract: str) -> dict[str, Any]:
    return {
        "id": str(pmid),
        "source": "MED",
        "pmid": str(pmid),
        "title": title,
        "abstractText": abstract,
        "authorString": "Author A, Author B",
        "journalTitle": "J Test",
        "pubYear": "2026",
        "pubTypeList": {"pubType": ["research-article"]},
    }


def test_recent_corpus_sends_sort_date_desc_to_every_page() -> None:
    pages = [
        {"count": 30, "current": 1, "results": [_pubtator_hit(p) for p in (101, 102, 103)]},
        {"count": 30, "current": 2, "results": [_pubtator_hit(p) for p in (201, 202, 203)]},
    ]
    epmc = {"resultList": {"result": []}}
    http = _DispatchHTTP(pubtator_pages=pages, epmc_bulk_payload=epmc)

    pack = gl.gene_literature(
        mode="recent_corpus",
        hgnc_symbol="SRC",
        http=cast(CachedHTTP, http),
    )
    assert isinstance(pack, LiteraturePack)
    # Every PubTator call must request date-sorted results — that's what
    # the entire mode exists to do. The query suffix is a one-word
    # surface-vocabulary term that biases PubTator's relevance ranking
    # toward surface-relevant papers without starving orphan-gene results.
    assert http.pubtator_calls, "no PubTator calls were issued"
    for call in http.pubtator_calls:
        assert call["params"]["sort"] == "date desc", call
        assert call["params"]["text"] == "@GENE_SRC surface"


def test_recent_corpus_bails_early_when_page_returns_no_new_pmids() -> None:
    # Page 1 returns 3 hits; page 2 returns the SAME 3 hits (zero new
    # PMIDs). The loop should stop before page 3.
    hits = [_pubtator_hit(p) for p in (101, 102, 103)]
    pages = [
        {"count": 3, "current": 1, "results": hits},
        {"count": 3, "current": 2, "results": hits},
    ]
    epmc = {"resultList": {"result": []}}
    http = _DispatchHTTP(pubtator_pages=pages, epmc_bulk_payload=epmc)

    pack = gl.gene_literature(
        mode="recent_corpus",
        hgnc_symbol="SRC",
        http=cast(CachedHTTP, http),
    )
    assert isinstance(pack, LiteraturePack)
    # Two pages issued, third (no-op) should not be requested.
    assert len(http.pubtator_calls) == 2


def test_recent_corpus_abstract_filter_keeps_surface_and_drops_signaling() -> None:
    # Delaveris-shaped paper: title mentions "cell surface", abstract
    # mentions "plasma membrane". Should be kept.
    keep_record = _epmc_record(
        pmid=4181_8370,
        title="Autophagolysosomal exocytosis inverts Src kinase onto the cell surface in cancer",
        abstract="We show that Src is displayed on the outer plasma membrane.",
    )
    # Pure signaling-pathway paper: no surface/membrane vocabulary. Drop.
    drop_record = _epmc_record(
        pmid=9999_9999,
        title="Src in T-cell receptor signaling cascade",
        abstract="The intracellular kinase activity of Src phosphorylates downstream substrates.",
    )
    pages = [
        {
            "count": 2,
            "current": 1,
            "results": [_pubtator_hit(41818370), _pubtator_hit(99999999)],
        }
    ]
    epmc = {"resultList": {"result": [keep_record, drop_record]}}
    http = _DispatchHTTP(pubtator_pages=pages, epmc_bulk_payload=epmc)

    pack = gl.gene_literature(
        mode="recent_corpus",
        hgnc_symbol="SRC",
        http=cast(CachedHTTP, http),
    )
    assert isinstance(pack, LiteraturePack)
    pmids_kept = {p.pmid for p in pack.papers}
    assert pmids_kept == {41818370}
    assert pack.n_total == 2
    assert pack.n_returned == 1
    assert pack.mode == "recent_corpus"


def test_recent_corpus_resolves_uniprot_to_hgnc_when_only_acc_given(monkeypatch) -> None:
    # The mode accepts uniprot_acc and resolves it through gene_lookup.
    # Stub _resolve to avoid the real network round-trip.
    from accessible_surfaceome.tools._shared.models import IdentifierBundle

    fake_bundle = IdentifierBundle(
        hgnc_symbol="SRC",
        hgnc_id="HGNC:11283",
        uniprot_acc="P12931",
        ncbi_gene_id=6714,
        ensembl_gene="ENSG00000197122",
    )
    monkeypatch.setattr(gl, "_resolve", lambda _acc, http: fake_bundle)

    pages = [{"count": 0, "current": 1, "results": []}]
    http = _DispatchHTTP(pubtator_pages=pages, epmc_bulk_payload={"resultList": {"result": []}})

    pack = gl.gene_literature(
        mode="recent_corpus",
        uniprot_acc="P12931",
        http=cast(CachedHTTP, http),
    )
    assert isinstance(pack, LiteraturePack)
    assert pack.hgnc_symbol == "SRC"
    assert http.pubtator_calls[0]["params"]["text"] == "@GENE_SRC surface"
