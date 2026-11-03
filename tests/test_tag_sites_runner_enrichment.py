"""Wiring the enrichment pieces into ``run_tag_site_agent``.

Four things have to reach the run, and one thing has to stop it:

* the member's loop inventory, in the USER prompt, so the model is told which
  extracellular regions exist in THIS construct's numbering and that terminal
  sites are out of scope;
* the prior run's cited clips, seeded into the pool, so a paper that degraded
  to abstract-only this run cannot take a known site with it;
* the covered-position filter, so menu budget is not spent restating junctions
  we already publish;
* the emitted sites, persisted into the run archive — the depth spike had to
  reconstruct its junctions from log prose because only counts were kept.

And the pause gate: when nothing new survives, the run returns BEFORE the
selector and the synthesizer, which is the expensive half.

Every enrichment parameter defaults to inert, so the control-panel path
(`regenerate_tag_site_lit.py` on a single gene) behaves exactly as before.
"""

from __future__ import annotations

import types

import pytest

from accessible_surfaceome.agents.tag_site import runner as R
from accessible_surfaceome.agents.tag_site.enrichment import seen_key
from accessible_surfaceome.agents.tag_site.prior_ledger import PriorClip
from accessible_surfaceome.agents.tag_site.schema import TagSiteResult
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft
from accessible_surfaceome.tools._shared.source_text import SourceTextStore


@pytest.fixture(autouse=True)
def _isolate_discovery_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DISCOVERY_CACHE_DIR", tmp_path / "discovery")


def _paper(**kw):
    base = dict(pmid=None, doi=None, pmc_id=None, title="", abstract="", year=None,
                is_preprint=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _evi(quote, *, source_id="PMID:11"):
    span = types.SimpleNamespace(
        source=types.SimpleNamespace(source_id=source_id), quote=quote
    )
    return types.SimpleNamespace(
        evidence_id="tag_evi_1", claim="tag inserted", spans=[span],
        entailment_verified=True,
    )


def _draft(clip_id: str, quote: str, source_id: str = "PMC:PMC1") -> EvidenceClaimDraft:
    return EvidenceClaimDraft(
        suggested_evidence_id=clip_id, quote=quote, source_id=source_id,
        section="methods", hallmark_phrase="x", score=1.0,
    )


SEQ = "MKTAYIAKQTGQISFVKSHFK" + "A" * 200
TOPO = "O" * 21 + "M" * 20 + "I" * 20 + "M" * 20 + "O" * 140


class Harness:
    """Stubs the whole pipeline and records what each stage was handed."""

    def __init__(self, pool: dict[str, EvidenceClaimDraft]):
        self.pool = pool
        self.selected_pool: dict | None = None
        self.select_kwargs: dict | None = None
        self.builder_prompt: str | None = None
        self.builder_called = False

    def install(self, monkeypatch, *, sites=(), ledger_quote="tag inserted after T10"):
        monkeypatch.setattr(R, "discover_tag_site_papers",
                            lambda **k: {"PMID:1": _paper(pmid=1)})
        monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])
        monkeypatch.setattr(R, "triage_abstracts", lambda *a, **k: [])
        monkeypatch.setattr(R, "build_pool", lambda *a, **k: (dict(self.pool), []))
        monkeypatch.setattr(R, "build_source_store",
                            lambda *a, **k: SourceTextStore())
        monkeypatch.setattr(R, "boost_residue_clips", lambda *a, **k: {})

        def fake_select(client, *, pool, **kw):
            self.selected_pool = dict(pool)
            self.select_kwargs = kw
            return object()

        monkeypatch.setattr(R, "select_clips", fake_select)
        # The entailment gate drops a site whose supporting_quote is not in the
        # ledger, so a fixture testing anything downstream has to put it there.
        monkeypatch.setattr(R, "promote", lambda *a, **k: [_evi(ledger_quote)])

        def fake_call_builder(client, **kw):
            self.builder_called = True
            self.builder_prompt = kw["user_prompt"]
            kw.get("meta_sink", {}).update({"n_repair_attempts": 0})
            return TagSiteResult(gene_symbol="GENEX", sites=list(sites))

        monkeypatch.setattr(R, "call_builder", fake_call_builder)
        monkeypatch.setattr(R, "apply_geometry_pass", lambda sites, **k: (list(sites), []))


def _run(**over):
    kw = dict(
        gene_symbol="GENEX", protein_name="Gene X", uniprot_accession="P1",
        aliases=[], sequence=SEQ, topology=TOPO, client=object(),
        http=object(), intermediates={},
    )
    kw.update(over)
    return kw


# --------------------------------------------------------------------------
# the loop inventory
# --------------------------------------------------------------------------


def test_the_loop_inventory_reaches_the_synthesis_prompt(monkeypatch) -> None:
    h = Harness({"c1": _draft("c1", "a fresh sentence")})
    h.install(monkeypatch)
    inter: dict = {}
    R.run_tag_site_agent(
        **_run(
            intermediates=inter,
            loop_inventory="This construct has NO extracellular terminus. Loops: 62-81 (20 aa).",
        )
    )
    assert h.builder_prompt is not None
    assert "NO extracellular terminus" in h.builder_prompt
    assert "62-81" in h.builder_prompt


def test_no_loop_inventory_leaves_the_prompt_unchanged(monkeypatch) -> None:
    """Inert by default: the single-gene control path must not acquire a
    sentence about loops it was never given."""
    h = Harness({"c1": _draft("c1", "a fresh sentence")})
    h.install(monkeypatch)
    R.run_tag_site_agent(**_run())
    assert h.builder_prompt is not None
    assert "extracellular terminus" not in h.builder_prompt


# --------------------------------------------------------------------------
# seeding
# --------------------------------------------------------------------------


def test_prior_clips_are_seeded_into_the_pool_before_selection(monkeypatch) -> None:
    h = Harness({"c1": _draft("c1", "a fresh sentence")})
    h.install(monkeypatch)
    R.run_tag_site_agent(
        **_run(
            prior_clips=[
                PriorClip(source_id="PMC:PMC9", claim="c",
                          quote="the clip whose paper 500'd today", run_id="v1")
            ]
        )
    )
    assert h.selected_pool is not None
    quotes = {d.quote for d in h.selected_pool.values()}
    assert "the clip whose paper 500'd today" in quotes
    assert len(h.selected_pool) == 2


# --------------------------------------------------------------------------
# the covered-position filter
# --------------------------------------------------------------------------


def test_a_clip_restating_a_published_junction_is_dropped_before_selection(
    monkeypatch,
) -> None:
    h = Harness(
        {
            "covered": _draft("covered", "a tag was inserted after Thr-10"),
            "fresh": _draft("fresh", "surface expression was measured"),
        }
    )
    h.install(monkeypatch)
    R.run_tag_site_agent(**_run(covered_junctions={10}))
    assert h.selected_pool is not None
    assert set(h.selected_pool) == {"fresh"}


# --------------------------------------------------------------------------
# the pause gate
# --------------------------------------------------------------------------


def test_the_run_stops_before_the_selector_when_nothing_is_new(monkeypatch) -> None:
    """The expensive half is the selector plus the synthesizer. A gene whose
    every clip an earlier run already examined has a known answer."""
    h = Harness({"old": _draft("old", "examined before", "PMC:PMC7")})
    h.install(monkeypatch)
    inter: dict = {}
    result = R.run_tag_site_agent(
        **_run(
            intermediates=inter,
            seen_keys={seen_key("PMC:PMC7", "examined before")},
        )
    )
    assert h.selected_pool is None, "selector was called"
    assert h.builder_called is False, "synthesizer was called"
    assert result.sites == []
    assert inter["n_new_clips"] == 0
    assert inter["outcome"] == "no_new_evidence"


def test_the_gate_is_inert_without_enrichment_inputs(monkeypatch) -> None:
    h = Harness({"c1": _draft("c1", "a fresh sentence")})
    h.install(monkeypatch)
    inter: dict = {}
    R.run_tag_site_agent(**_run(intermediates=inter))
    assert h.builder_called is True
    assert inter["n_new_clips"] == 1
    assert inter["outcome"] == "synthesized"


# --------------------------------------------------------------------------
# what the archive keeps
# --------------------------------------------------------------------------


def test_the_emitted_sites_are_persisted(monkeypatch) -> None:
    """The depth spike could not verify its own junctions afterwards: the
    archive kept n_sites and the log kept residue labels, so the positions had
    to be reconstructed from prose. A sweep that cannot be checked afterwards
    cannot be trusted afterwards."""
    from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal

    site = TagSiteProposal(
        rank=1, site_type="internal", insert_after_residue=10,
        residue_before="T", residue_after="G", topology_state="extracellular",
        tag_type="HA", rationale="in the loop",
        evidence_type="published tag insertion at this exact site",
        validation_level="surface_and_function", position_evidence="validated",
        source_tier="paper", supporting_quote="a tag was inserted after Thr-10",  # noqa: E501
        confidence="high", evidence_detail="flow cytometry on intact cells",
        functional_or_expression_impact_measured="transport retained",
    )
    h = Harness({"c1": _draft("c1", "a tag was inserted after Thr-10")})
    h.install(monkeypatch, sites=[site],
              ledger_quote="a tag was inserted after Thr-10")
    inter: dict = {}
    R.run_tag_site_agent(**_run(intermediates=inter, numbered_against="deadbeef"))
    assert inter["numbered_against"] == "deadbeef"
    assert len(inter["sites"]) == 1
    assert inter["sites"][0]["insert_after_residue"] == 10


def test_batching_is_off_unless_asked_for(monkeypatch) -> None:
    """The selector is shared with the internalization track."""
    h = Harness({"c1": _draft("c1", "a fresh sentence")})
    h.install(monkeypatch)
    R.run_tag_site_agent(**_run())
    assert h.select_kwargs is not None
    assert h.select_kwargs.get("max_batches", 1) == 1

    h2 = Harness({"c1": _draft("c1", "a fresh sentence")})
    h2.install(monkeypatch)
    R.run_tag_site_agent(**_run(select_max_batches=4))
    assert h2.select_kwargs is not None
    assert h2.select_kwargs["max_batches"] == 4
