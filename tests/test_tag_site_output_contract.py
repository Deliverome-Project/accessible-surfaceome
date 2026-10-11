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

import json
import types
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


# ---------------------------------------------------------------------------
# Prompt provenance + recorded rejections.
# ---------------------------------------------------------------------------


def test_every_llm_record_carries_the_three_mandatory_provenance_fields() -> None:
    """CLAUDE.md: a pipeline whose LLM output is persisted must stamp the model
    id, the prompt_sha and the prompt_version. Tag-site records carried none;
    internalization's literature track carried two of three. Four prompt edits
    in one day produced records that could not be told apart afterwards."""
    from accessible_surfaceome.agents.internalization.models import (
        LiteratureTrack,
        ModelPriorTrack,
    )
    from accessible_surfaceome.agents.tag_site.schema import TagSiteResult as TSR

    required = ("prompt_sha", "prompt_version", "model")
    for model in (TSR, LiteratureTrack, ModelPriorTrack):
        missing = [f for f in required if f not in model.model_fields]
        assert not missing, f"{model.__name__} is missing provenance fields: {missing}"
    assert "schema_version" in TSR.model_fields


def test_the_prompt_sha_tracks_the_prompt_text() -> None:
    """The fingerprint has to change when the prompt does, or a stale record
    reads as current — the whole point of the version guard."""
    from accessible_surfaceome.agents.tag_site import prompt as tag_prompt

    before = tag_prompt.prompt_sha()
    original = tag_prompt.SYSTEM_PROMPT
    try:
        tag_prompt.SYSTEM_PROMPT = original + "\n(an edit)"
        assert tag_prompt.prompt_sha() != before
    finally:
        tag_prompt.SYSTEM_PROMPT = original
    assert tag_prompt.prompt_sha() == before


def test_an_overcomplete_quote_is_recovered_rather_than_dropped() -> None:
    """The KCNH2 T436 case: clips are truncated at extraction, so a model that
    reproduces the whole sentence yields a string no clip contains. That is a
    MORE faithful citation and the gate was deleting it."""
    from accessible_surfaceome.agents.tag_site.runner import (
        recover_overcomplete_quotes,
        verify_entailment,
    )

    clip = (
        "A 13-residue bungarotoxin-binding site (BBS; "
        "TGGCGGTACTACGAGAGCAGCCTGGAGCCCTACCCCGAC) ( Sekine-Aizawa and Huga"
    )
    evidence = [types.SimpleNamespace(spans=[types.SimpleNamespace(quote=clip)])]
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=436,
        residue_before="T", residue_after="E", tag_type="BBS",
        evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote=clip + "nir, 2004) was placed between Thr436 and Glu437.",
        rationale="r", confidence="high",
    )
    result = TagSiteResult(sites=[site])

    verify_entailment(result, evidence=evidence)
    assert not result.sites[0].entailment_verified  # the old behaviour: dropped

    recover_overcomplete_quotes(result, evidence=evidence)
    verify_entailment(result, evidence=evidence)
    assert result.sites[0].entailment_verified
    assert result.sites[0].supporting_quote == clip  # stores what it verified


def test_an_invented_quote_is_still_dropped() -> None:
    """The recovery must not become a way for fabricated text to pass. Moving
    `upgrade_quotes` ahead of the gate would have done exactly that — it falls
    back to ANY probative ledger quote, so an invented citation would have
    survived wearing a real but unrelated one."""
    from accessible_surfaceome.agents.tag_site.runner import (
        recover_overcomplete_quotes,
        verify_entailment,
    )

    evidence = [
        types.SimpleNamespace(
            spans=[
                types.SimpleNamespace(
                    quote="An ALFA tag was inserted after G101 of the ectodomain loop."
                )
            ]
        )
    ]
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=777,
        residue_before="A", residue_after="A", tag_type="ALFA",
        evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote="A sentence that appears in no clip whatsoever.",
        rationale="r", confidence="high",
    )
    result = TagSiteResult(sites=[site])
    recover_overcomplete_quotes(result, evidence=evidence)
    verify_entailment(result, evidence=evidence)
    assert not result.sites[0].entailment_verified


# ---------------------------------------------------------------------------
# Typographic punctuation must not break entailment.
# ---------------------------------------------------------------------------


def test_a_curly_apostrophe_does_not_break_entailment() -> None:
    """The real KCNH2 T436 failure, with the real strings.

    The agent proposed the site and ranked it FIRST. Its 448-character quote
    differed from the ledger clip in ONE character: the publisher writes
    "manufacturer’s" with U+2019 and the model transcribed U+0027. NFKC does not
    fold those together, so the most faithful possible citation failed the
    entailment gate and the site was deleted silently.

    This normalizer is shared by every pipeline that span-verifies a quote, so
    the same drop was available to the deep dive and internalization too."""
    from accessible_surfaceome.agents.tag_site.literature_discovery import quote_supported

    ledger = (
        "A 13-residue bungarotoxin-binding site (BBS; "
        "TGGCGGTACTACGAGAGCAGCCTGGAGCCCTACCCCGAC) was then introduced between "
        "residues T436/E437 in the extracellular S1–S2 loop of hERG using the "
        "Quik-Change Lightning Site-Directed Mutagenesis Kit (Stratagene) "
        "according to the manufacturer’s instructions."
    )
    model_transcription = ledger.replace("’", "'").replace("–", "-")
    assert model_transcription != ledger
    assert quote_supported(model_transcription, ledger)


def test_typographic_folding_is_idempotent() -> None:
    """`normalize_for_quote_matching` documents f(f(x)) == f(x); every folded
    target is ASCII and maps to itself, but assert it rather than assume it."""
    from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching

    for raw in (
        "the manufacturer’s “protocol” — see Fig. 1…",
        "residues T436–E437",
        "plain ascii text with 'quotes' and - dashes",
    ):
        once = normalize_for_quote_matching(raw)
        assert normalize_for_quote_matching(once) == once


def test_folding_does_not_collapse_genuinely_different_quotes() -> None:
    """Folding is strictly more permissive, so the risk it carries is a FALSE
    match. Two sentences that differ in words must still not entail."""
    from accessible_surfaceome.agents.tag_site.literature_discovery import quote_supported

    a = "A FLAG tag was inserted between Gln43 and Thr44 of the extracellular loop."
    b = "A FLAG tag was inserted between Gln97 and Thr98 of the extracellular loop."
    assert not quote_supported(a, b)


# ---------------------------------------------------------------------------
# Evidence that cannot be pinned to a junction must still be kept.
# ---------------------------------------------------------------------------


def test_an_n_terminal_prepend_is_a_valid_junction() -> None:
    """insert_after_residue=0 puts the tag BEFORE residue 1. It is the only
    extracellular terminus a GPCR without a signal peptide has, and two control
    rows use it — but check_residues called it "outside the sequence", so the
    geometry gate deleted a site the model had proposed at exactly the position
    the benchmark expected (ADORA1)."""
    from accessible_surfaceome.agents.tag_site.geometry import check_residues

    seq = "MPPSISAFQAAYIGIEVLIALV"
    assert check_residues(sequence=seq, residue=0, before="", after="M") is None
    assert check_residues(sequence=seq, residue=0, before="", after="K")  # wrong after
    assert check_residues(sequence=seq, residue=0, before="A", after="M")  # has no before
    assert check_residues(sequence=seq, residue=-1, before="", after="M")  # still invalid


def test_a_region_level_site_survives_the_geometry_pass() -> None:
    """A paper that reports a tag in a named loop without giving the junction is
    real evidence. It used to be discarded whole; now it is kept with `region`
    set and no junction claimed, rather than a junction being invented."""
    from accessible_surfaceome.agents.tag_site.geometry import apply_geometry_pass

    site = TagSiteProposal(
        site_type="internal", region="ECL4", tag_type="HiBiT",
        evidence_type="published tag insertion in the same loop or domain",
        position_evidence="inferred",
        evidence_detail="HiBiT knock-in into ECL4, surface display confirmed",
        functional_or_expression_impact_measured="NOT MEASURED",
        rationale="the paper names ECL4 but no junction", confidence="medium",
    )
    kept, rejected = apply_geometry_pass(
        [site], sequence="MPPSISAFQAAYIGIEVLIALV", topology="O" * 22, sp_end=0
    )
    assert len(kept) == 1 and not rejected
    assert kept[0].residue_label == "ECL4"
    assert kept[0].insert_after_residue is None


def test_a_region_level_site_is_not_re_judged_against_a_residue() -> None:
    """enforce_position_claims compares the quote against n-1/n/n+1. A region
    site has no n, and arithmetic on None is how that surfaced."""
    from accessible_surfaceome.agents.tag_site.runner import enforce_position_claims

    site = TagSiteProposal(
        site_type="internal", region="ECL4", tag_type="HiBiT",
        evidence_type="published tag insertion in the same loop or domain",
        position_evidence="inferred", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote="HiBiT was knocked into the ECL4 of WT-CFTR",
        rationale="r", confidence="medium",
    )
    result = TagSiteResult(sites=[site])
    enforce_position_claims(result, sequence="MPPSISAFQAAYIGIEVLIALV")
    assert result.sites[0].position_evidence == "inferred"


def test_an_empty_result_still_carries_its_provenance() -> None:
    """Three early returns bypassed the stamping at the end of the runner, so a
    gene that ran and legitimately found nothing came out indistinguishable
    from one that never ran. ITGB5 did exactly that in a 24-gene sweep: no
    prompt_sha, while VANGL1 — also zero sites — carried one because it reached
    the normal path. A zero that cannot be dated has to be re-run to be
    trusted, which defeats the point of recording it."""
    import inspect

    from accessible_surfaceome.agents.tag_site import runner

    src = inspect.getsource(runner.run_tag_site_agent)
    empty = src[src.index("def _empty()") : src.index("# 1. Discovery")]
    for field in ("prompt_sha", "prompt_version", "model", "generated_at"):
        assert field in empty, (
            f"_empty() does not stamp {field!r} — an empty result would be "
            f"indistinguishable from a gene that never ran"
        )


# ---------------------------------------------------------------------------
# A terminal site the topology pins, and the claim it is allowed to make.
# ---------------------------------------------------------------------------


def test_an_unvalidated_position_cannot_claim_an_exact_site_citation() -> None:
    """The prompt couples these — exact-site evidence_type requires a validated
    position — but nothing enforced it. enforce_position_claims downgrades
    position_evidence and left evidence_type alone, so TFRC's C-terminal site
    shipped saying "I inferred this position" and "a tag was published at this
    exact site" at once. The site is kept; only the claim is corrected."""
    from accessible_surfaceome.agents.tag_site.runner import enforce_evidence_type_coupling

    def site(pos_ev):
        return TagSiteProposal(
            site_type="terminal_c", insert_after_residue=760, residue_before="F",
            residue_after="", tag_type="V5",
            evidence_type="published tag insertion at this exact site",
            position_evidence=pos_ev, evidence_detail="d",
            functional_or_expression_impact_measured="NOT MEASURED",
            rationale="r", confidence="medium",
        )

    result = TagSiteResult(sites=[site("inferred"), site("topology_derived"), site("validated")])
    enforce_evidence_type_coupling(result)
    inferred, derived, validated = result.sites
    assert inferred.evidence_type == "published tag insertion in the same loop or domain"
    assert derived.evidence_type == "published tag insertion in the same loop or domain"
    assert validated.evidence_type == "published tag insertion at this exact site"
    # all three SURVIVE — this corrects a label, it does not drop a site
    assert len(result.sites) == 3


def test_topology_derived_is_its_own_standing() -> None:
    """A position computed from a sole extracellular terminus is stronger than
    'I picked a spot in a loop'. Collapsing both into 'inferred' loses that."""
    import typing

    vals = typing.get_args(TagSiteProposal.model_fields["position_evidence"].annotation)
    assert set(vals) == {"validated", "inferred", "topology_derived"}


def test_a_wrong_letter_is_repaired_without_moving_the_junction() -> None:
    """SLC5A6 lost a real published site — an EL3 ALFA tag with two corroborating
    ledger lines — because the model wrote T at 484 where the sequence has P,
    while naming 483 and its M correctly. The NUMBER was corroborated; only a
    descriptive letter was wrong."""
    from accessible_surfaceome.agents.tag_site.geometry import check_residues, repair_proposal

    seq = "AAAAAMPPSPSNGS"          # M at 6, P at 7; "MT" occurs nowhere
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=6, residue_before="M", residue_after="T",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED", rationale="r", confidence="high",
    )
    assert check_residues(sequence=seq, residue=6, before="M", after="T")      # fails first
    assert repair_proposal(site, sequence=seq, sp_end=0) == "letter_only"
    assert site.insert_after_residue == 6, "the junction must not move"
    assert site.residue_after == "P"
    assert check_residues(sequence=seq, residue=6, before="M", after="P") is None


def test_the_repair_refuses_when_the_number_is_not_corroborated() -> None:
    """If residue_before does not match either, nothing corroborates the number
    and correcting the other letter would launder a fabricated position."""
    from accessible_surfaceome.agents.tag_site.geometry import repair_proposal

    site = TagSiteProposal(
        site_type="internal", insert_after_residue=6, residue_before="Q", residue_after="Q",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED", rationale="r", confidence="high",
    )
    assert repair_proposal(site, sequence="AAAAAMPPSPSNGS", sp_end=0) is None


def test_the_repair_refuses_when_the_claimed_pair_exists_elsewhere() -> None:
    """Then the model may have meant that other junction, and choosing between
    them is exactly the guesswork repair_proposal refuses to do."""
    from accessible_surfaceome.agents.tag_site.geometry import repair_proposal

    seq = "AAAAAMPPSMTNGS"          # M|P at 6, but "MT" also occurs at 10
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=6, residue_before="M", residue_after="T",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED", rationale="r", confidence="high",
    )
    assert repair_proposal(site, sequence=seq, sp_end=0) is None


# ---------------------------------------------------------------------------
# The blind position verifier.
# ---------------------------------------------------------------------------


def test_the_verifier_is_blind_to_what_it_is_verifying() -> None:
    """The guard exists because the model overclaims, so asking the model "did
    your quote support your claim?" would be worthless. The verifier is shown
    the sentence and nothing else — no gene, no claimed residue, no hint that a
    claim is under review — so it cannot rubber-stamp a position it does not
    know is wanted."""
    from accessible_surfaceome.agents.tag_site import position_verify as pv

    system = pv._SYSTEM.lower()
    for leak in ("claim", "validate", "verify", "review", "correct", "expected"):
        assert leak not in system, f"the verifier's prompt mentions {leak!r}"

    captured = {}

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                captured.update(kw)
                return types.SimpleNamespace(content=[types.SimpleNamespace(text="484")])

    pv.verify_position_blind("residues 484-516 were replaced", client=_Client, max_residue=700)
    sent = json.dumps(captured, default=str)
    assert "483" not in sent and "gene" not in sent.lower()


def test_the_verifier_can_only_upgrade() -> None:
    """A verifier that could also downgrade would be a second way to lose a
    correct site. The deterministic path already decides that."""
    import inspect

    from accessible_surfaceome.agents.tag_site import runner

    src = inspect.getsource(runner.enforce_position_claims)
    after = src[src.index("verify_position_blind") :]
    assert 'continue' in after, "a successful verification must keep the claim"
    assert 'position_evidence = "validated"' not in after, "it must not promote"


def test_a_failed_verifier_leaves_the_deterministic_verdict_alone() -> None:
    """No client, an API error or an unparseable reply must all be inert."""
    from accessible_surfaceome.agents.tag_site.position_verify import verify_position_blind

    class _Boom:
        class messages:  # noqa: N801
            @staticmethod
            def create(**_):
                raise RuntimeError("api down")

    assert verify_position_blind("residues 484-516 replaced", client=None) is None
    assert verify_position_blind("residues 484-516 replaced", client=_Boom) is None
    assert verify_position_blind("", client=_Boom) is None


def test_a_position_outside_the_protein_is_rejected() -> None:
    """A reply of 9999 for a 700-residue protein is not a position."""
    from accessible_surfaceome.agents.tag_site.position_verify import verify_position_blind

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**_):
                return types.SimpleNamespace(content=[types.SimpleNamespace(text="9999")])

    assert verify_position_blind("x" * 40, client=_Client, max_residue=700) is None


# ---------------------------------------------------------------------------
# Citing a ledger line by id instead of retyping its quote.
# ---------------------------------------------------------------------------


def test_the_quote_is_resolved_from_the_cited_id_not_retyped() -> None:
    """Every quote failure today was a transcription artifact — a curly
    apostrophe against a straight one, a sentence reproduced more completely
    than the clip stored. None can occur when the text is never retyped: it
    comes back out of the same ledger it went in as.

    This is the pattern the clip-SELECT stage has always used ("you only pick
    and classify by clip_id, you never retype the quote")."""
    from accessible_surfaceome.agents.tag_site.runner import fill_quotes_from_ledger

    ledger = [
        types.SimpleNamespace(spans=[types.SimpleNamespace(quote="FIRST clip text, verbatim.")]),
        types.SimpleNamespace(spans=[types.SimpleNamespace(quote="SECOND clip text, verbatim.")]),
    ]
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=101, residue_before="G", residue_after="S",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_clip_id="L2", rationale="r", confidence="high",
    )
    result = TagSiteResult(sites=[site])
    fill_quotes_from_ledger(result, evidence=ledger)
    assert result.sites[0].supporting_quote == "SECOND clip text, verbatim."


def test_a_site_citing_no_id_keeps_its_own_quote() -> None:
    """Backward compatible: the entailment gate still has something to judge."""
    from accessible_surfaceome.agents.tag_site.runner import fill_quotes_from_ledger

    ledger = [types.SimpleNamespace(spans=[types.SimpleNamespace(quote="ledger text")])]
    site = TagSiteProposal(
        site_type="internal", insert_after_residue=101, residue_before="G", residue_after="S",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence="validated", evidence_detail="d",
        functional_or_expression_impact_measured="NOT MEASURED",
        supporting_quote="the model wrote this one", rationale="r", confidence="high",
    )
    result = TagSiteResult(sites=[site])
    fill_quotes_from_ledger(result, evidence=ledger)
    assert result.sites[0].supporting_quote == "the model wrote this one"


def test_an_out_of_range_or_malformed_id_is_ignored() -> None:
    from accessible_surfaceome.agents.tag_site.runner import fill_quotes_from_ledger

    ledger = [types.SimpleNamespace(spans=[types.SimpleNamespace(quote="only line")])]
    for cid in ("L9", "Lx", "3", ""):
        site = TagSiteProposal(
            site_type="internal", insert_after_residue=101, residue_before="G",
            residue_after="S", tag_type="ALFA",
            evidence_type="published tag insertion at this exact site",
            position_evidence="validated", evidence_detail="d",
            functional_or_expression_impact_measured="NOT MEASURED",
            supporting_clip_id=cid, supporting_quote="kept", rationale="r", confidence="high",
        )
        result = TagSiteResult(sites=[site])
        fill_quotes_from_ledger(result, evidence=ledger)
        assert result.sites[0].supporting_quote == "kept", f"id {cid!r} should be ignored"


def test_the_ledger_renders_citable_ids() -> None:
    from accessible_surfaceome.agents.tag_site.runner import format_evidence_ledger

    ev = [
        types.SimpleNamespace(
            claim="a claim",
            spans=[types.SimpleNamespace(
                quote="q", source=types.SimpleNamespace(source_id="PMID:123"))],
        )
    ] * 2
    text = format_evidence_ledger(ev)
    assert "[L1]" in text and "[L2]" in text
    assert "supporting_clip_id" in text
