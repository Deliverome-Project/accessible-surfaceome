"""A site may claim `validated` only if its quote names the position.

Every site the agent produced on the held-out control genes cited a quote that
never named its own residue:

    ERBB2 S22  "To test whether an activating mutation influences HER2
                internalization rate..."
    LDLR  T21  "The cellular localization of these plasmids in cells stably
                expressing WT (HepG2 WT+)..."

Those positions are plausibly right -- they are the canonical signal-peptide
cleavage sites -- but they were derived from topology, not from the citation,
and were reported as `position_evidence: validated`. The schema already draws
this distinction; nothing enforced it.
"""

from accessible_surfaceome.agents.tag_site.runner import enforce_position_claims
from accessible_surfaceome.agents.tag_site.schema import TagSiteProposal, TagSiteResult

SEQ = "M" + "A" * 99 + "K" + "G" + "A" * 150          # K101, G102


def _site(res=101, quote=None, position_evidence="validated"):
    return TagSiteProposal(
        rank=1, site_type="internal", insert_after_residue=res,
        residue_before="K", residue_after="G", topology_state="extracellular",
        tag_type="ALFA", evidence_type="published tag insertion at this exact site",
        position_evidence=position_evidence, evidence_detail="d",
        functional_or_expression_impact_measured="x",
        supporting_quote=quote, rationale="r", confidence="high",
    )


def _run(sites):
    r = TagSiteResult(gene_symbol="X", uniprot_accession="Q0",
                      sequence_length=len(SEQ), sites=sites)
    return enforce_position_claims(r, sequence=SEQ)


def test_a_quote_naming_the_residue_keeps_its_validated_claim():
    s = _site(quote="an ALFA tag was inserted after K101 of the ectodomain")
    assert _run([s]).sites[0].position_evidence == "validated"


def test_a_spelled_out_residue_in_the_quote_also_counts():
    """The form that rescued the one site this pipeline got right."""
    s = _site(quote="we added the tag following the signal peptide (Lysine 101)")
    assert _run([s]).sites[0].position_evidence == "validated"


def test_the_adjacent_residue_counts_because_papers_differ_on_the_convention():
    """A label may name the residue before OR after the junction."""
    s = _site(quote="the tag sits at G102 of the mature protein")
    assert _run([s]).sites[0].position_evidence == "validated"


def test_a_quote_that_never_names_the_position_is_downgraded():
    """The ERBB2 S22 / LDLR T21 class."""
    s = _site(quote="To test whether an activating mutation influences "
                    "internalization rate, we tagged the receptor")
    out = _run([s]).sites[0]
    assert out.position_evidence == "inferred"
    assert out.insert_after_residue == 101        # the site is kept, not dropped


def test_a_missing_quote_cannot_support_a_validated_claim():
    assert _run([_site(quote=None)]).sites[0].position_evidence == "inferred"


def test_a_site_already_marked_inferred_is_left_alone():
    s = _site(quote=None, position_evidence="inferred")
    assert _run([s]).sites[0].position_evidence == "inferred"


def test_a_number_from_an_unrelated_sentence_does_not_validate_the_site():
    """Noise the sequence check rejects must not launder a position claim."""
    s = _site(quote="cells were cultured in A549 medium for 101 hours")
    # 101 appears, but as a duration, and A549 is a cell line the sequence
    # rejects — the bare integer must not count as naming the residue.
    assert _run([s]).sites[0].position_evidence == "inferred"
