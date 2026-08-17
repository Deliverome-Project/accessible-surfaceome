import hashlib
import typing
from datetime import UTC, datetime
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization.literature_select import (
    promote,
    select_clips,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    Selection,
    SelectionResponse,
)
from accessible_surfaceome.tools._shared import models as m
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


def _first(lit):
    return typing.get_args(lit)[0]


def _selection(clip_id="c1", claim="the receptor internalizes"):
    return Selection(
        clip_id=clip_id,
        claim=claim,
        claim_type=_first(m.ClaimType),
        evidence_type=_first(m.EvidenceType),
        evidence_tier=_first(m.EvidenceTier),
        direction=_first(m.Direction),
        confidence=_first(m.EvidenceConfidence),
        assay_context=m.AssayContext(species=_first(m.Species)),
    )


def _draft(clip="c1", quote="the receptor internalized rapidly", sid="PMID:1"):
    return EvidenceClaimDraft(
        suggested_evidence_id=clip,
        quote=quote,
        source_id=sid,
        section=_first(m.PaperSection_),
        hallmark_phrase="h",
        score=1.0,
    )


def _store_with(quote, sid="PMID:1"):
    raw = f"Methods and results. {quote} under the tested conditions."
    norm = normalize_for_quote_matching(raw)
    st = SourceText(
        source_id=sid,
        source_type="pubmed",
        url=f"https://pubmed.ncbi.nlm.nih.gov/{sid.split(':')[1]}/",
        title="t",
        raw_text=raw,
        normalized_text=norm,
        content_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        normalized_source_sha256=hashlib.sha256(norm.encode()).hexdigest(),
        retrieved_at=datetime.now(UTC),
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=datetime.now(UTC),
    )
    store = SourceTextStore()
    store.put(st)
    return store


def test_promote_selections_copies_verbatim_quote():
    from accessible_surfaceome.agents.internalization.literature_select import (
        _promote_selections,
    )

    pool = {"c1": _draft()}
    claims, warnings = _promote_selections(
        SelectionResponse(selections=[_selection()]), pool=pool
    )
    assert warnings == []
    assert claims[0].quote == "the receptor internalized rapidly"  # from the pool
    assert claims[0].evidence_id.startswith("int_evi_")


def test_promote_yields_real_span_when_quote_in_body():
    quote = "the receptor internalized rapidly"
    pool = {"c1": _draft(quote=quote)}
    ev = promote(SelectionResponse(selections=[_selection()]), pool=pool, store=_store_with(quote))
    assert len(ev) == 1
    assert ev[0].entailment_verified is True
    assert ev[0].spans and ev[0].spans[0].char_offset >= 0


def test_promote_store_miss_is_unverified():
    pool = {"c1": _draft()}
    ev = promote(SelectionResponse(selections=[_selection()]), pool=pool, store=SourceTextStore())
    assert ev[0].entailment_verified is False
    assert ev[0].spans == []


class _FakeMessages:
    def __init__(self, texts):
        self._t = list(texts)
        self.last_user: str = ""

    def create(self, **kw):
        self.last_user = kw["messages"][0]["content"]
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._t.pop(0))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def test_select_clips_parses_response():
    resp_json = SelectionResponse(selections=[_selection()], notes="").model_dump_json()
    client = _FakeClient(["```json\n" + resp_json + "\n```"])
    out = select_clips(client, pool={"c1": _draft()}, gene="TFRC", system_prompt="SYS")
    assert len(out.selections) == 1
    assert out.selections[0].clip_id == "c1"


def test_select_clips_passes_synonyms_into_user_prompt():
    resp_json = SelectionResponse(selections=[], notes="").model_dump_json()
    client = _FakeClient(["```json\n" + resp_json + "\n```"])
    select_clips(
        client,
        pool={"c1": _draft()},
        gene="TFRC",
        synonyms=["CD71", "TFR1"],
        system_prompt="SYS",
    )
    assert "Also known as: CD71, TFR1" in client.messages.last_user


def test_select_clips_empty_pool_short_circuits():
    out = select_clips(object(), pool={}, gene="TFRC", system_prompt="SYS")
    assert out.selections == []
