"""The prompt must hand the model PRE-COMPUTED coordinates.

Regression for the observed failure mode: given a bare run-length topology
string, the synthesis stage mis-counted a 26-residue signal peptide as 18 and
shifted every downstream boundary with it. Code counts; the model should not
have to.
"""
from accessible_surfaceome.agents.tag_site.normalize import topology_runs
from accessible_surfaceome.agents.tag_site.prompt import (
    build_user_prompt,
    format_topology_landmarks,
    numbered_sequence,
)

SEQ = "MLLLLLLLLLA" + "HSEAKKGSKFDT" + "PPPPPPPP" + "V" * 22 + "CCCCCCCC"
TOPO = "S" * 11 + "O" * 20 + "M" * 22 + "I" * 8


def test_topology_runs_returns_contiguous_labelled_spans():
    assert topology_runs(TOPO) == [
        ("S", 1, 11), ("O", 12, 31), ("M", 32, 53), ("I", 54, 61),
    ]


def test_topology_runs_handles_a_protein_with_no_signal_peptide():
    assert topology_runs("I" * 3 + "M" * 4 + "O" * 5) == [
        ("I", 1, 3), ("M", 4, 7), ("O", 8, 12),
    ]


def test_landmarks_name_every_span_with_explicit_bounds():
    out = format_topology_landmarks(TOPO)
    assert "SIGNAL PEPTIDE: 1-11" in out
    assert "EXTRACELLULAR: 12-31" in out
    assert "TRANSMEMBRANE: 32-53" in out
    assert "INTRACELLULAR: 54-61" in out


def test_landmarks_report_an_authoritative_sp_end_that_differs():
    """DeepTMHMM and UniProt disagree on the cleavage site often enough that the
    model must be told which one is authoritative rather than inferring it."""
    out = format_topology_landmarks(TOPO, sp_end=8)
    assert "SIGNAL PEPTIDE: 1-8" in out
    assert "MATURE N-TERMINUS: 9" in out


def test_numbered_sequence_labels_each_line_with_its_start_position():
    out = numbered_sequence(SEQ, width=10)
    assert out.splitlines()[0].startswith("   1  MLLLLLLLLL")
    assert out.splitlines()[1].startswith("  11  AHSEAKKGSK")


def test_production_prompt_carries_landmarks_and_a_numbered_sequence():
    p = build_user_prompt("TMEM123", "Porimin", mode="production",
                          sequence=SEQ, topology=TOPO, sp_end=11)
    assert "SIGNAL PEPTIDE: 1-11" in p
    assert "TRANSMEMBRANE: 32-53" in p
    assert "   1  " in p
    assert "do NOT re-count" in p


def test_landmarks_state_an_authoritative_sp_the_prediction_missed():
    """UniProt annotates a signal peptide DeepTMHMM did not predict. The
    authoritative span must still be stated, and the spans after it clipped."""
    out = format_topology_landmarks("O" * 40, sp_end=17)
    assert "SIGNAL PEPTIDE: 1-17" in out
    assert "EXTRACELLULAR: 18-40" in out
    assert "MATURE N-TERMINUS: 18" in out


def test_landmarks_clip_a_predicted_sp_run_to_the_authoritative_end():
    out = format_topology_landmarks("S" * 24 + "O" * 16, sp_end=21)
    assert "SIGNAL PEPTIDE: 1-21" in out
    assert "EXTRACELLULAR: 22-40" in out


def test_prompt_explains_how_papers_spell_residue_positions():
    """A paper may write the position as a word, a three-letter code, or a bare
    code buried in a primer table — and may name the residue before OR after the
    junction, inconsistently within one paper. The model has to be told."""
    from accessible_surfaceome.agents.tag_site.prompt import SYSTEM_PROMPT
    low = SYSTEM_PROMPT.lower()
    for cue in ("spelled", "three-letter", "primer", "before or after"):
        assert cue in low, cue
