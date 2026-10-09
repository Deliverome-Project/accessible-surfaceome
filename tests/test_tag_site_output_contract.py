"""The tag-site prompt must document every field the model has to emit.

``call_builder`` validates the reply against ``TagSiteResult`` but never sends
the schema to the API — the ``messages.create`` call passes system, messages and
tools and nothing else. So a required field that the prompt does not name is a
field the model can only guess at.

That failed silently for a long time: ``uniprot_accession`` and
``sequence_length`` were required and mentioned nowhere, so every run spent its
repair budget rediscovering them, and ``functional_or_expression_impact_measured``
came back as a bool because the name reads boolean. On one control gene the
repair cascade cost a real site.

These tests pin both halves of the fix: the contract is generated from the
models (so a new field documents itself), and the fields the pipeline supplies
are not asked of the model at all.
"""
from __future__ import annotations

import typing
from pathlib import Path

from accessible_surfaceome.agents.tag_site.prompt import (
    _CODE_SET,
    _PIPELINE_SET,
    SYSTEM_PROMPT,
    format_output_contract,
)
from pydantic import BaseModel

from accessible_surfaceome.agents.internalization import models as internalization_models
from accessible_surfaceome.agents.internalization.literature_grade import LiteratureLLMOut

from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult


def _model_supplied(model: type[BaseModel]) -> list[str]:
    """Fields the MODEL is responsible for — not the ones the pipeline stamps."""
    return [
        name
        for name in model.model_fields
        if name not in _PIPELINE_SET and name not in _CODE_SET
    ]


def test_every_field_the_model_must_supply_is_named_in_the_prompt() -> None:
    missing = [n for n in _model_supplied(TagSiteProposal) if n not in SYSTEM_PROMPT]
    missing += [n for n in _model_supplied(TagSiteResult) if n not in SYSTEM_PROMPT]
    assert not missing, (
        f"{missing} must be emitted by the model but are named nowhere in the "
        f"prompt. The schema is not sent to the API, so the model cannot know "
        f"them — add them to the contract or give them a default and stamp them "
        f"in the runner."
    )


def test_no_model_supplied_field_is_required_without_being_documented() -> None:
    """A required field with no default is the expensive case: it costs a repair
    round every single run until the model guesses the name."""
    contract = format_output_contract()
    for name in _model_supplied(TagSiteProposal):
        if TagSiteProposal.model_fields[name].is_required():
            assert name in contract, f"required field {name!r} absent from the output contract"


def test_pipeline_and_code_set_fields_are_not_requested() -> None:
    """Asking the model for these invites it to assert its own quote was
    verified, or to echo back an accession we passed in."""
    contract = format_output_contract()
    body = contract.split("Emit nothing else.")[0]
    for name in (*_PIPELINE_SET, *_CODE_SET):
        assert name not in body, f"{name!r} is pipeline-set but appears in the request body"


def test_code_supplied_fields_have_defaults_so_an_omission_still_validates() -> None:
    """The runner stamps these after parsing; the model omitting them must not
    fail validation, which is what made them cost a repair round."""
    for name in _CODE_SET:
        field = TagSiteResult.model_fields.get(name) or TagSiteProposal.model_fields[name]
        assert not field.is_required(), f"{name!r} is still required of the model"
    assert not TagSiteProposal.model_fields["rank"].is_required()


def test_a_reply_without_the_code_supplied_fields_validates() -> None:
    """The exact shape the prompt now asks for, with nothing else."""
    result = TagSiteResult.model_validate(
        {
            "sites": [
                {
                    "site_type": "internal",
                    "insert_after_residue": 101,
                    "residue_before": "G",
                    "residue_after": "S",
                    "topology_state": "extracellular",
                    "tag_type": "short epitope, ALFA 15 aa, GS linkers",
                    "evidence_type": "published tag insertion at this exact site",
                    "position_evidence": "validated",
                    "evidence_detail": "surface staining, non-permeabilized",
                    "functional_or_expression_impact_measured": "adhesion assay, unchanged",
                    "rationale": "ledger line pins the junction",
                    "confidence": "high",
                }
            ],
        }
    )
    assert result.sites[0].insert_after_residue == 101
    assert result.uniprot_accession == ""  # stamped by the runner, not the model


def test_the_impact_field_is_a_string_not_a_bool() -> None:
    """Its name reads boolean, so the model sent ``true``. The contract has to
    say STRING or the repair loop pays for it on every run."""
    assert TagSiteProposal.model_fields[
        "functional_or_expression_impact_measured"
    ].annotation is str
    assert "never true/false" in format_output_contract()


# ---------------------------------------------------------------------------
# The same two invariants, applied to the internalization literature search.
#
# It already satisfies both — 16 Literal types, and every required field named
# in its prompts. These tests exist so it stays that way: the tag-site agent
# also started out fine and drifted, and nothing was watching.
# ---------------------------------------------------------------------------

_INTERNALIZATION_PROMPTS = (
    Path(internalization_models.__file__).parent / "prompts"
)


def _reachable(
    model: type[BaseModel], seen: set[type[BaseModel]] | None = None
) -> set[type[BaseModel]]:
    """Every BaseModel reachable from `model`, including through list/optional."""
    seen = seen if seen is not None else set()
    if model in seen:
        return seen
    seen.add(model)
    for field in model.model_fields.values():
        for candidate in (field.annotation, *typing.get_args(field.annotation)):
            for inner in (candidate, *typing.get_args(candidate)):
                if isinstance(inner, type) and issubclass(inner, BaseModel):
                    _reachable(inner, seen)
    return seen


def test_internalization_closed_vocabularies_are_literals() -> None:
    """A closed vocabulary typed as bare `str` accepts anything — which is how a
    tag-site record shipped `topology_state='O'` and read as not-extracellular."""
    unconstrained: list[str] = []
    for model in _reachable(LiteratureLLMOut):
        for name, field in model.model_fields.items():
            if typing.get_origin(field.annotation) is typing.Literal:
                continue
            description = field.description or ""
            if "|" in description or description.count("'") >= 4:
                unconstrained.append(f"{model.__name__}.{name}")
    assert not unconstrained, (
        f"{unconstrained} enumerate their allowed values in the description but "
        f"are not Literal, so any string validates"
    )


def test_internalization_required_fields_are_named_in_its_prompts() -> None:
    """The schema is not sent to the API here either, so a required field the
    prompts never name is one the model can only guess at."""
    blob = "\n".join(p.read_text() for p in _INTERNALIZATION_PROMPTS.glob("*.md"))
    missing = [
        f"{model.__name__}.{name}"
        for model in _reachable(LiteratureLLMOut)
        for name, field in model.model_fields.items()
        if field.is_required() and name not in blob
    ]
    assert not missing, f"required but named in no internalization prompt: {missing}"


# ---------------------------------------------------------------------------
# supporting_pmid is derived, not transcribed.
# ---------------------------------------------------------------------------


def test_supporting_pmid_is_filled_from_the_cited_ledger_line() -> None:
    """The real failure: `paper_source_id` keys a paper "PMC:<id>" ahead of
    "PMID:<id>", the ledger inherited that label and told the model to null the
    pmid, and every PMC-sourced citation lost it — 99 of 125 papers in one KCNH2
    pool. The viewer then stamped `citation: "preprint"` on peer-reviewed work.

    Uses the actual pair that broke: PMC5917007 / PMID 29725305, the Kanner 2018
    paper the benchmark cites for KCNH2 T436."""
    import types

    from accessible_surfaceome.agents.tag_site.runner import attach_source_pmids

    quote = "a BBS (13 amino acid residues) was placed between residues Thr436 and Glu437"
    evidence = [
        types.SimpleNamespace(
            spans=[
                types.SimpleNamespace(
                    quote=quote,
                    source=types.SimpleNamespace(source_id="PMC:PMC5917007"),
                )
            ]
        )
    ]
    papers = {"PMC:PMC5917007": types.SimpleNamespace(pmid="29725305", is_preprint=False)}

    site = TagSiteProposal(
        site_type="internal", insert_after_residue=436,
        residue_before="T", residue_after="E", tag_type="BBS",
        evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote=quote, rationale="r", confidence="high",
    )
    assert site.supporting_pmid is None  # the model never supplies it

    result = TagSiteResult(sites=[site])
    attach_source_pmids(result, evidence=evidence, papers_by_id=papers)
    assert result.sites[0].supporting_pmid == 29725305


def test_a_doi_only_preprint_keeps_a_null_pmid() -> None:
    """The one case "preprint" was ever meant for: no PMID exists, so null is
    correct rather than a lost identifier."""
    import types

    from accessible_surfaceome.agents.tag_site.runner import attach_source_pmids

    quote = "an HA tag was inserted between amino acids T443 and E444"
    evidence = [
        types.SimpleNamespace(
            spans=[
                types.SimpleNamespace(
                    quote=quote,
                    source=types.SimpleNamespace(source_id="DOI:10.1101/2020.02.17.952606"),
                )
            ]
        )
    ]
    papers = {
        "DOI:10.1101/2020.02.17.952606": types.SimpleNamespace(pmid=None, is_preprint=True)
    }
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=443,
        residue_before="T", residue_after="E", tag_type="HA",
        evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote=quote, rationale="r", confidence="high",
    )
    result = TagSiteResult(sites=[site])
    attach_source_pmids(result, evidence=evidence, papers_by_id=papers)
    assert result.sites[0].supporting_pmid is None
