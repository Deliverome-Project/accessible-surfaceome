"""The synthesis stage gets a Python REPL.

The model is handed the canonical sequence, but it cannot reliably compute over
it: given a bare topology string it read a 26-residue signal-peptide run as 18
and shifted every boundary it derived. Deterministic code now covers the checks
we knew to write (residue identity, topology, landmarks), but not the open-ended
one -- when a paper states a position in a DIFFERENT numbering frame (mature
protein, an isoform, an ortholog), finding the offset is a search over the
sequence, which is exactly what code is for and prose reasoning is not.

Code execution is a server-side tool: declared in `tools`, resolved inside the
same `create` call, no client-side loop -- the same shape as the web_search the
repo already runs through `call_builder`.
"""
from accessible_surfaceome.agents.tag_site.runner import CODE_EXECUTION_TOOL


def test_the_tool_recipe_is_the_server_side_code_execution_tool():
    (tool,) = CODE_EXECUTION_TOOL
    assert tool["type"].startswith("code_execution_")
    assert tool["name"] == "code_execution"


def test_the_synthesis_call_is_given_the_repl(monkeypatch, tmp_path):
    """The tool reaches the synthesis call, not just the module."""
    import types
    from typing import cast

    from anthropic import Anthropic

    from accessible_surfaceome.agents.tag_site import runner as R
    from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult
    from accessible_surfaceome.tools._shared.http import CachedHTTP

    SEQ = "M" + "A" * 99 + "K" + "G" + "A" * 198   # K101, G102
    site = TagSiteProposal(
        rank=1, site_type="internal", insert_after_residue=101,
        residue_before="K", residue_after="G", topology_state="extracellular",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="x",
        supporting_quote="ALFA inserted after K101.", rationale="r", confidence="high",
    )
    span = types.SimpleNamespace(
        source=types.SimpleNamespace(source_id="PMID:1"), quote="ALFA inserted after K101.")
    evi = types.SimpleNamespace(evidence_id="tag_evi_1", claim="c",
                                spans=[span], entailment_verified=True)
    paper = types.SimpleNamespace(pmid=1, doi=None, pmc_id=None, title="t",
                                  abstract="", year=None, is_preprint=False)

    monkeypatch.setattr(R, "DISCOVERY_CACHE_DIR", tmp_path)
    monkeypatch.setattr(R, "discover_tag_site_papers", lambda **k: {"PMID:1": paper})
    monkeypatch.setattr(R, "web_discover_papers", lambda *a, **k: [])
    monkeypatch.setattr(R, "triage_abstracts", lambda *a, **k: [])
    monkeypatch.setattr(R, "build_pool", lambda *a, **k: ({}, []))
    monkeypatch.setattr(R, "build_source_store", lambda *a, **k: object())
    monkeypatch.setattr(R, "select_clips", lambda *a, **k: object())
    monkeypatch.setattr(R, "promote", lambda *a, **k: [evi])

    seen: dict = {}

    def fake_call_builder(client, **kw):
        seen.update(kw)
        return TagSiteResult(gene_symbol="X", uniprot_accession="Q0",
                             sequence_length=len(SEQ), sites=[site])

    monkeypatch.setattr(R, "call_builder", fake_call_builder)
    R.run_tag_site_agent(
        gene_symbol="X", protein_name="X protein", uniprot_accession="Q0",
        aliases=["x"], sequence=SEQ, topology="O" * len(SEQ),
        client=cast(Anthropic, object()), http=cast(CachedHTTP, object()))

    tools = seen.get("tools") or []
    assert any(t.get("name") == "code_execution" for t in tools), tools


def test_the_prompt_tells_the_model_it_can_compute():
    from accessible_surfaceome.agents.tag_site.prompt import SYSTEM_PROMPT
    low = SYSTEM_PROMPT.lower()
    assert "python" in low
    assert "numbering" in low
