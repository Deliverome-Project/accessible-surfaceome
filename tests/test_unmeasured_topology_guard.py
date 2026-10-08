"""The deep dive must refuse to run on fabricated topology.

A placeholder / stub ``IsoformTopology`` reports ``tm_helix_count=0``,
``signal_peptide_length=0`` and ``ecd_length_residues=0`` — numerically
identical to a real measurement of a soluble protein. Because the
deterministic block is interpolated into the agent's prompt, the model reads
those zeros as fact and writes them into its executive summary.

This is not hypothetical. Two records published in the
``intracellular_rescue_v1_sonnet_2026_09`` cohort assert the fabricated
topology verbatim:

* ``BLCAP`` — "a small intracellular protein with zero annotated
  transmembrane helices, no extracellular domain, and no signal peptide"
* ``C1orf115`` — "a cytoplasmic peripheral membrane protein with no
  transmembrane helix, signal peptide, or extracellular domain"

Both carry a UniProt transmembrane annotation, so both verdicts rest on a
false premise the pipeline supplied. Hence a hard failure rather than the
previous silent placeholder.
"""

from __future__ import annotations

import argparse
import inspect
from datetime import UTC, datetime

import pytest

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    PLACEHOLDER_TOPOLOGY_TOOL_VERSION,
    STUB_TOPOLOGY_TOOL_VERSION,
    UNMEASURED_TOPOLOGY_TOOL_VERSIONS,
    topology_is_measured,
)
from accessible_surfaceome.tools._shared.models import IsoformTopology


def _topology(tool_version: str) -> IsoformTopology:
    return IsoformTopology(
        isoform_id="P00000-1",
        uniprot_acc="P00000",
        tm_helix_count=0,
        n_terminal_orientation="cytoplasmic",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=0,
        ecd_length_residues=0,
        icd_length_residues=0,
        per_residue_topology="",
        tool_version=tool_version,
        retrieved_at=datetime.now(UTC),
        ecd_pct_similarity_to_canonical=None,
    )


@pytest.mark.parametrize(
    "tool_version", sorted(UNMEASURED_TOPOLOGY_TOOL_VERSIONS)
)
def test_unmeasured_markers_are_not_measured(tool_version: str) -> None:
    assert topology_is_measured(_topology(tool_version)) is False


def test_real_deeptmhmm_version_is_measured() -> None:
    assert topology_is_measured(_topology("deeptmhmm-1.0.24")) is True


def test_both_fabrication_markers_are_covered() -> None:
    """Guard against a new placeholder marker slipping past the check.

    The two markers are minted in different modules — ``d1_deterministic``
    (gene outside the sweep cohort) and the v1 orchestrator's stub (D1
    unreachable) — so a third could easily be added without updating the set.
    """
    assert UNMEASURED_TOPOLOGY_TOOL_VERSIONS == {
        PLACEHOLDER_TOPOLOGY_TOOL_VERSION,
        STUB_TOPOLOGY_TOOL_VERSION,
    }


def test_v1_stub_uses_the_shared_constant() -> None:
    """The stub must stay recognisable to ``topology_is_measured``.

    It previously hardcoded its own literal, so the two could drift.
    """
    from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
        _stub_deterministic_features,
    )

    stub = _stub_deterministic_features("P00000")
    assert stub.canonical_topology.tool_version == STUB_TOPOLOGY_TOOL_VERSION
    assert topology_is_measured(stub.canonical_topology) is False


def test_annotate_requires_measured_topology_by_default() -> None:
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import annotate

    param = inspect.signature(annotate).parameters["require_measured_topology"]
    assert param.default is True, "the guard must be opt-OUT, never opt-in"


@pytest.mark.parametrize(
    "module_path", ["scripts.annotate_gene", "scripts.run_deep_dive_sweep"]
)
def test_runners_expose_the_optout_and_default_to_guarding(module_path: str) -> None:
    """Both entry points need the escape hatch, defaulting to guarded."""
    import importlib.util
    import sys
    from pathlib import Path

    name = module_path.rsplit(".", 1)[-1]
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_t_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    parser_src = path.read_text()
    assert "--allow-unmeasured-topology" in parser_src
    # store_true => absent means False => require_measured_topology stays True.
    assert 'action="store_true"' in parser_src
    assert "require_measured_topology=not args.allow_unmeasured_topology" in parser_src


def test_error_message_tells_the_operator_what_to_run() -> None:
    """A bare 'no topology' error would just get --allow-'d past.

    The message has to name the sweep commands, or the escape hatch becomes
    the path of least resistance.
    """
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
        UnmeasuredTopologyError,
    )

    assert issubclass(UnmeasuredTopologyError, RuntimeError)
    src = inspect.getsource(
        __import__(
            "accessible_surfaceome.agents.surfaceome_v2.orchestrator",
            fromlist=["_annotate"],
        )._annotate
    )
    assert "build_topology_candidate_set.py" in src
    assert "run_topology_sweep.py" in src


def test_argparse_flag_is_a_true_optout() -> None:
    """Sanity-check the flag semantics rather than trusting the string match."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-unmeasured-topology", action="store_true")
    assert ap.parse_args([]).allow_unmeasured_topology is False
    assert ap.parse_args(["--allow-unmeasured-topology"]).allow_unmeasured_topology is True
