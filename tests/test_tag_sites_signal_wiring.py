"""A signal `compute_signals` accepts but nothing supplies is inert, and every
unit test of the lane that consumes it still passes.

`propeptide` was exactly this. The refusal was implemented in `terminal.py`,
tested eight ways, committed — and `run_gene` had no such parameter, so
`compute_signals` never received one and the gate never fired on a single
published gene. The lane's own tests could not see it: they call
`terminal_candidates(signals)` with a hand-built dict.

Both consumers fall back SILENTLY, which is what makes this class invisible.
`disorder.py` uses `signals.get("disorder") or {}` and drops to pLDDT; the
terminal lane treats a missing propeptide as "not annotated". Neither logs, and
neither can distinguish "no data for this gene" from "nobody wired it up".

So the wiring is pinned here rather than left to be rediscovered. The map below
is the deliberate-edit surface: a new optional signal is either threaded through
`run_gene` or recorded as a known gap with its cost, and a gap cannot be closed
or opened without this file changing.
"""

from __future__ import annotations

import inspect

from accessible_surfaceome.tag_sites import run as R

#: Optional `compute_signals` signals that `run_gene` does NOT supply, with what
#: it costs to leave them unwired. Removing an entry requires threading it.
KNOWN_UNWIRED: dict[str, str] = {
    "disorder_tracks": (
        "The disorder lane falls back to the pLDDT proxy. Measured against "
        "Tedman's 112 screen-validated junctions, the published-predictor "
        "consensus puts the top extracellular site a median 3 aa from the "
        "junction and the pLDDT<70 run 40 aa away (disorder.py:36). "
        "12,584 deterministic disorder-lane sites across 2,111 genes in "
        "tag_site_public were placed by the proxy, while disorder_public holds "
        "97,351 rows across 24,029 accessions, already built and unused. "
        "Wiring it moves over half the internal catalogue, so it is a "
        "deliberate re-derive and not a patch."
    ),
}


def optional_signals() -> set[str]:
    return {
        name
        for name, p in inspect.signature(R.compute_signals).parameters.items()
        if p.default is not inspect.Parameter.empty
    }


def test_every_optional_signal_is_either_wired_or_a_recorded_gap() -> None:
    """The guard. A new optional signal added to `compute_signals` and not
    threaded through `run_gene` fails here instead of silently never firing."""
    src = inspect.getsource(R.run_gene)
    params = set(inspect.signature(R.run_gene).parameters)
    for name in sorted(optional_signals()):
        wired = name in params and f"{name}={name}" in src
        if name in KNOWN_UNWIRED:
            assert not wired, (
                f"{name!r} is now wired through run_gene but still listed in "
                f"KNOWN_UNWIRED — remove the entry in the same commit"
            )
            continue
        assert wired, (
            f"{name!r} is an optional signal that run_gene never passes, so "
            f"compute_signals cannot receive it and whatever consumes it falls "
            f"back silently. Thread it through run_gene, or add it to "
            f"KNOWN_UNWIRED with what the fallback costs."
        )


def test_the_recorded_gaps_are_real_signals() -> None:
    """A stale entry would silently excuse a signal that no longer exists,
    which is how an allowlist stops guarding anything."""
    unknown = set(KNOWN_UNWIRED) - optional_signals()
    assert not unknown, f"KNOWN_UNWIRED names non-signals: {sorted(unknown)}"


def test_each_gap_records_what_it_costs() -> None:
    """"Known gap" without a measured cost is indistinguishable from "we forgot",
    which is the state this test exists to end."""
    for name, why in KNOWN_UNWIRED.items():
        assert len(why) > 80, f"{name}: the gap needs its cost stated, not a label"


def test_propeptide_is_wired_and_stays_wired() -> None:
    """Named explicitly, because it is the one that was inert: the generic test
    above would also pass if someone moved it into KNOWN_UNWIRED."""
    assert "propeptide" not in KNOWN_UNWIRED
    assert "propeptide" in inspect.signature(R.run_gene).parameters
    assert "propeptide=propeptide" in inspect.getsource(R.run_gene)
