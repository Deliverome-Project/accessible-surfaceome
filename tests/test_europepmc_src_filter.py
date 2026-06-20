"""Regression tests for the Europe PMC source filter on discovery searches.

Production used to hard-code ``AND SRC:MED`` on every Europe PMC search,
which hard-excludes preprints (``SRC:PPR``). The result: preprint-server
papers were invisible to the discovery layer until they got published-to-
journal + PubMed-mirrored (a 6-12 month lag). The expansion to
``AND SRC:(MED OR PPR)`` widens the search to Europe PMC-partnered
preprint servers (bioRxiv, medRxiv, ChemRxiv, ResearchSquare,
Preprints.org, SSRN-Health, arXiv-q-bio) while keeping the rest of the
chain unchanged — PPR records carry the same JATS-shaped full text.

PMID-keyed Europe PMC lookups elsewhere intentionally stay ``SRC:MED``
because PPR records don't have numeric PMIDs — adding PPR there would
be a no-op at best and a silent recall regression at worst.
"""
from __future__ import annotations

from typing import Any, cast

import pytest

from accessible_surfaceome.tools import evidence_retrieval as er
from accessible_surfaceome.tools import gene_literature as gl
from accessible_surfaceome.tools._shared import europepmc as epmc
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IdentifierBundle


def _capture_query(monkeypatch: pytest.MonkeyPatch, target_module: Any) -> list[str]:
    """Monkeypatch ``europepmc_search`` on the calling module to capture the
    query string and return an empty result set so the caller exits cleanly."""
    captured: list[str] = []

    def _fake_search(*, http: Any, query: str, page_size: int = 0, **_: Any) -> Any:
        captured.append(query)
        return {"resultList": {"result": []}}

    monkeypatch.setattr(target_module, "europepmc_search", _fake_search)
    return captured


def test_europepmc_discovery_includes_preprints(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_europepmc_discovery`` (evidence_retrieval's category search) must
    union SRC:MED with SRC:PPR so preprints flow into the candidate pool."""
    queries = _capture_query(monkeypatch, er)
    bundle = IdentifierBundle(
        uniprot_acc="Q9NZD1", hgnc_id="HGNC:1", hgnc_symbol="GPRC5D"
    )
    # _CategorySpec exposes query_clauses — pick a real one from the registry
    # so the test exercises the same code path production uses.
    spec = er._CATEGORY_SPECS["flow_cytometry"]
    er._europepmc_discovery(
        bundle=bundle,
        spec=spec,
        max_papers=5,
        http=cast(CachedHTTP, object()),
        retraction_index=cast(Any, None),
    )
    assert queries, "europepmc_search was not called"
    q = queries[0]
    assert "SRC:(MED OR PPR)" in q, f"PPR not unioned: {q}"
    assert "SRC:MED " not in q and not q.endswith("SRC:MED"), (
        f"bare SRC:MED still present (would exclude preprints): {q}"
    )


def test_topic_search_includes_preprints(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_topic_search`` (gene_literature's standing-axis search) must also
    union SRC:MED with SRC:PPR — same reason as above, different call site."""
    queries = _capture_query(monkeypatch, gl)
    # Try a few real topic anchors; we only need one that the registry
    # accepts so the query gets emitted.
    for anchor in ("surface_expression", "topology", "shedding"):
        try:
            gl._topic_search(
                http=cast(CachedHTTP, object()),
                uniprot_acc=None,
                hgnc_symbol="GPRC5D",
                aliases=[],
                previous_symbols=[],
                topic_anchors=[anchor],
                max_results=5,
                retraction_index=cast(Any, None),
            )
            break
        except (ValueError, KeyError):
            continue
    assert queries, "europepmc_search was not called for any tested anchor"
    q = queries[0]
    assert "SRC:(MED OR PPR)" in q, f"PPR not unioned: {q}"
    assert "SRC:MED " not in q and not q.endswith("SRC:MED"), (
        f"bare SRC:MED still present (would exclude preprints): {q}"
    )


def test_pmid_keyed_lookup_stays_med_only() -> None:
    """``europepmc_bulk_by_pmid`` queries by ``EXT_ID:`` (PMID), and PPR
    records don't carry numeric PMIDs — adding PPR would be a no-op and
    invites surprise drift if the upstream ID convention ever changes.
    Lock in that the bulk-by-PMID call stays SRC:MED-only by inspecting
    the function's source. (Run-time monkeypatch would require simulating
    the full Europe PMC bulk fetch; a source check is the lighter assert.)
    """
    import inspect
    src = inspect.getsource(epmc.europepmc_bulk_by_pmid)
    assert "SRC:MED" in src
    assert "SRC:(MED OR PPR)" not in src, (
        "europepmc_bulk_by_pmid was widened to PPR — PPR records have no "
        "numeric PMID so this would be a silent no-op. Keep this call SRC:MED."
    )
