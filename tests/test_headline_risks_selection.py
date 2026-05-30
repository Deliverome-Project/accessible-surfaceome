"""Tripwire tests for the synthesizer's headline_risks selection
discipline.

History: the original tripwires (PR #38 follow-up) enforced the 11-value
enum + the three orphan-class signals. The post-design-review slim
dropped the enum to 5 values and moved orphan-class signals out of
``headline_risks`` entirely:

* ``low_endogenous_expression`` → derived ``filters.low_endogenous_expression``
* ``antibody_validation_weak`` → ``surface_evidence.evidence_grade``
* ``ligand_unknown`` → ``filters_llm.has_known_ligand``
* ``ecd_too_small`` → ``filters.ecd_accessibility_class``
* ``restricted_subdomain`` → ``accessibility_risks.restricted_subdomain.present``
* ``other`` → forbidden (raise in ``one_paragraph`` instead)

The new tripwires assert the prompt carries the slim discipline.
"""

from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    SYSTEM_PROMPT_PATH as SYNTH_SYSTEM_PROMPT_PATH,
)


def test_synthesizer_prompt_has_headline_risks_section() -> None:
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    # Must have a dedicated section so the discipline is locatable,
    # not buried in a sub-bullet inside "The judgment that matters".
    assert "## Headline-risks selection discipline" in body


def test_synthesizer_prompt_names_only_the_five_enum_values() -> None:
    """The slimmed enum has 5 values; the prompt must enumerate them
    and call out the count explicitly so the model can't reach for a
    historical value."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    # The "**five** values" phrasing anchors readers (and the model)
    # to the slim — drift either direction (back to 11, sideways to
    # 4 or 6) trips this.
    assert "**five** values" in body
    for value in (
        "shed_form",
        "secreted_form",
        "co_receptor",
        "epitope_masked",
        "isoform_decoy",
    ):
        assert value in body, (
            f"prompt must list {value!r} as one of the remaining "
            "headline_risk enum values"
        )


def test_synthesizer_prompt_documents_removed_values_and_redirects() -> None:
    """Each removed value gets a line telling the model where its
    signal lives now. Drops verifying this catch the case where someone
    re-adds a value to the prompt without restoring the enum.
    """
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    for removed in (
        "ecd_too_small",
        "restricted_subdomain",
        "antibody_validation_weak",
        "low_endogenous_expression",
        "ligand_unknown",
        "other",
    ):
        assert removed in body, (
            f"prompt must reference removed value {removed!r} so the "
            "model knows NOT to use it"
        )


def test_synthesizer_prompt_forbids_other_explicitly() -> None:
    """``other`` was the escape hatch the audit found in 3/6 samples.
    Prompt must explicitly forbid it (not just omit from the enum) so
    the model can't try to reach for it from memory."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    # "forbidden" is the load-bearing word; "raise it in one_paragraph"
    # is the redirect.
    assert "`other` → forbidden" in SYNTH_SYSTEM_PROMPT_PATH.read_text()
    assert "raise it in" in body or "raise the risk in" in body


def test_synthesizer_prompt_describes_ligand_unknown_relocation() -> None:
    """``ligand_unknown`` moved from headline_risks to
    ``filters_llm.has_known_ligand``. The prompt must document this
    so the model sets the bool correctly for orphan receptors."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    assert "has_known_ligand" in body
    # The has-known-ligand section should explain orphan-class
    # examples so the model picks False for the right genes.
    assert "Orphan GPCRs" in body or "orphan GPCRs" in body


def test_synthesizer_prompt_describes_surface_accessibility_no_value() -> None:
    """The new ``surface_accessibility="no"`` value needs prompt
    guidance so the model uses it (instead of stretching ``low`` or
    ``uncertain`` to cover confidently-not-surface cases)."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text()
    assert "## Surface accessibility" in body
    assert '`"no"`' in body or '"no" verdict' in body.lower()
