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
        "MEASURED, and leaving it unwired is the right call — this entry records "
        "a deliberate decision, not a debt. The disorder lane falls back to a "
        "contiguous extracellular run of plddt < 70. Scoping it over 2,470 genes "
        "(97.6% of published disorder sites) against the 25-site internal corpus: "
        "all three arms place at a median 2 aa from the validated junction and a "
        "paired sign test on nearest-site distance gives p = 0.508, so there is "
        "no placement accuracy to recover on internal sites. What wiring it would "
        "do is mislabel its own output: DISORDER_PCT_MIN = 60 is a within-protein "
        "rank with no absolute floor, so it admits the top 40% of every protein "
        "whether or not the protein has any disorder, and 33% of the predictor "
        "arm's post-NMS sites carry their own pLDDT >= 70 while shipping "
        "disorder.py's fixed rationale 'within a low-pLDDT disordered "
        "extracellular run' — false for them, and inside surface_loop's territory "
        "(PLDDT_MIN = 70), where derive_deterministic_sites gives disorder "
        "priority on a collision and relabels them. The pLDDT-run fallback does "
        "that 0 times out of 15,561. Post-NMS totals would go 15,561 -> 23,281 "
        "(+50%) with a median Jaccard of 0.000 against what is published, i.e. "
        "for over half of genes it shares zero residues with the current output. "
        "The one real win is ordering, not coverage: distance to the TOP-RANKED "
        "site improves from a median 79 aa to 11 aa (p = 0.006, n = 15), which is "
        "worth capturing as a tie-break INSIDE the existing plddt < 70 run rather "
        "than as the run's threshold. Numbers: docs/"
        "handoff-2026-10-18-disorder-tracks-scoping.md."
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
