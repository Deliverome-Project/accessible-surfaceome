"""Signal-peptide-proximal tag placement, following Tedman's published method.

His approach, from the Deep Receptor Scanning methods (doi:10.1101/2025.09.19.677468):
detect the signal peptide, call its cleavage site with SignalP 6.0, find where the
structured N-terminal domain *begins* with NetSurfP, and insert the tag at positions
**between** those two points -- then re-predict cleavage and disorder on each tagged
design and keep the one that perturbs neither.

The important shape is that this defines an **interval**, not a point. The biological
constraint is "past the cleavage site, before the fold starts", and every position in
between is admissible. Measured against his 111 signal-peptide-bearing receptors, his
actual insertions fall inside that interval **106 times (95.5%)**, and the interval is a
median **7 aa** wide -- which is why picking the single most-disordered residue is a
stronger claim than the biology supports, and why a fixed 20-residue window would place
a tag inside the folded domain for most receptors.

He used NetSurfP-2.0 alone. We have three disorder predictors, and they agree about where
structure begins: pairwise median difference 2-3 aa, 86-88% within 10 aa, median onset
residue 31-32. So a consensus onset generalises his method rather than changing it.
"""

from __future__ import annotations

from typing import NamedTuple

STRUCTURE_THRESHOLD = 0.5
"""Disorder score below which a residue counts as structured."""

STRUCTURE_RUN = 5
"""Consecutive residues below the threshold needed to call the fold started.

A single ordered residue inside a flexible linker is noise; a sustained run is the domain
boundary. Five is short enough to catch a compact domain and long enough to ignore one
confident residue.
"""


class TagInterval(NamedTuple):
    """Admissible insertion positions, in the "after N" convention.

    ``lo`` is the first residue the tag may follow (the cleavage site itself) and ``hi``
    the last (the residue before the fold begins). ``onsets`` records what each predictor
    said, so a narrow or contradictory interval can be inspected rather than trusted.
    """

    lo: int
    hi: int
    onsets: dict[str, int | None]
    cleavage_site: int

    @property
    def width(self) -> int:
        return max(0, self.hi - self.lo)

    @property
    def positions(self) -> list[int]:
        return list(range(self.lo, self.hi + 1)) if self.hi >= self.lo else []

    def describe(self) -> str:
        spread = [v for v in self.onsets.values() if v is not None]
        agree = f"{min(spread)}-{max(spread)}" if spread else "none"
        return (
            f"insert after residues {self.lo}..{self.hi} ({self.width} aa wide); "
            f"cleavage {self.cleavage_site}, structure onset {agree}"
        )


def structure_onset(
    track: list[float],
    start: int,
    *,
    threshold: float = STRUCTURE_THRESHOLD,
    run: int = STRUCTURE_RUN,
) -> int | None:
    """First residue after ``start`` where disorder stays below ``threshold`` for ``run``.

    Returns a 1-indexed residue, or None when the track never settles -- an ectodomain
    that is disordered throughout has no fold boundary to respect, and the caller should
    fall back rather than invent one.
    """
    if start < 0 or not track:
        return None
    for i in range(start, len(track) - run + 1):
        if all(track[j] < threshold for j in range(i, i + run)):
            return i + 1
    return None


def tag_interval(
    cleavage_site: int,
    tracks: dict[str, list[float]],
    *,
    threshold: float = STRUCTURE_THRESHOLD,
    run: int = STRUCTURE_RUN,
    fallback_width: int = 7,
) -> TagInterval:
    """The admissible span between the cleavage site and the start of the fold.

    The onset is the **median** of the predictors that return one, not the earliest or the
    latest. Earliest would let one over-eager predictor collapse the interval to nothing;
    latest would let one under-calling predictor push the tag into the domain. With
    pairwise agreement already at 2-3 aa the choice rarely matters, and when it does the
    disagreement is itself the signal, which is why every onset is kept on the result.

    ``fallback_width`` applies only when no predictor finds a boundary; it is the measured
    median interval width, so an all-disordered ectodomain gets a typical span rather than
    an unbounded one.
    """
    onsets = {name: structure_onset(t, cleavage_site, threshold=threshold, run=run)
              for name, t in tracks.items()}
    found = sorted(v for v in onsets.values() if v is not None)
    if found:
        onset = found[len(found) // 2]
    else:
        onset = cleavage_site + fallback_width + 1
    return TagInterval(lo=cleavage_site, hi=max(cleavage_site, onset - 1),
                       onsets=onsets, cleavage_site=cleavage_site)


def tagged_sequence(sequence: str, after_residue: int, cassette: str) -> str:
    """The protein with ``cassette`` spliced in after ``after_residue`` (1-indexed)."""
    if not 0 <= after_residue <= len(sequence):
        raise ValueError(f"cannot insert after residue {after_residue} of {len(sequence)}")
    return sequence[:after_residue] + cassette + sequence[after_residue:]


def candidate_designs(
    sequence: str, interval: TagInterval, cassette: str
) -> list[tuple[int, str]]:
    """``(after_residue, tagged sequence)`` for every admissible position.

    Tedman built a series across the interval and chose between them by re-prediction
    rather than picking one up front; these are the designs that re-prediction scores.
    """
    return [(p, tagged_sequence(sequence, p, cassette)) for p in interval.positions]


class PositionScore(NamedTuple):
    """Every tool's reading at one candidate position, unreduced.

    Deliberately not averaged. The three predictors disagree about absolute disorder by a
    wide margin at the same residues -- NetSurfP-3.0 reads 0.93 where metapredict reads
    0.61 -- and which of them deserves weight is an open question that the data here
    cannot settle: NetSurfP is the tool Tedman used and the closest to his junctions on
    its own, but pLDDT alone is nearly as close. Storing each tool separately keeps that
    decision reversible instead of baking a weighting into the record.
    """

    after_residue: int
    scores: dict[str, float | None]
    percentiles: dict[str, float | None]

    def consensus(self, weights: dict[str, float] | None = None) -> float | None:
        """Weighted mean of the per-tool percentiles, computed on demand, never stored."""
        pairs: list[tuple[float, float]] = []
        if weights:
            for key, w in weights.items():
                v = self.percentiles.get(key)
                if v is not None:
                    pairs.append((w, v))
        else:
            pairs = [(1.0, v) for v in self.percentiles.values() if v is not None]
        if not pairs:
            return None
        return sum(w * v for w, v in pairs) / sum(w for w, _ in pairs)


def score_positions(
    interval: TagInterval,
    tracks: dict[str, list[float]],
    percentiles: dict[str, list[float]] | None = None,
) -> list[PositionScore]:
    """Each admissible position, with every tool's raw score and rank kept separate."""
    out = []
    for p in interval.positions:
        raw = {k: (t[p - 1] if 1 <= p <= len(t) else None) for k, t in tracks.items()}
        pct = {k: (v[p - 1] if percentiles and k in percentiles and 1 <= p <= len(v) else None)
               for k, v in (percentiles or {}).items()}
        out.append(PositionScore(after_residue=p, scores=raw, percentiles=pct))
    return out


class RepredictionResult(NamedTuple):
    """What re-running the predictors on a tagged design showed.

    Tedman re-predicted cleavage and disorder for every candidate and kept the design
    "most strongly predicted to preserve the correct cleavage site without altering
    disorder prediction". This is that check, and it is the only step in the pipeline with
    a feedback loop: everything else scores the native sequence and assumes insertion is
    neutral. That assumption is much weaker for us than for him -- our cassette is 51 aa
    against his 9 -- so this matters more here, not less.
    """

    after_residue: int
    cleavage_before: int
    cleavage_after: int | None
    cleavage_preserved: bool
    disorder_shift: dict[str, float | None]

    @property
    def ok(self) -> bool:
        return self.cleavage_preserved


def compare_reprediction(
    after_residue: int,
    cleavage_before: int,
    cleavage_after: int | None,
    disorder_before: dict[str, list[float]],
    disorder_after: dict[str, list[float]],
    *,
    cassette_len: int,
) -> RepredictionResult:
    """Score one tagged design against its untagged self.

    Disorder is compared only over the residues *upstream* of the insertion, where the two
    sequences still correspond position-for-position. Downstream the tag has shifted every
    index by ``cassette_len``, so comparing there would measure the offset rather than any
    change the tag caused.
    """
    shift: dict[str, float | None] = {}
    for name, before in disorder_before.items():
        after = disorder_after.get(name)
        if not after:
            shift[name] = None
            continue
        n = min(after_residue, len(before), len(after))
        shift[name] = (sum(abs(before[i] - after[i]) for i in range(n)) / n) if n else None
    return RepredictionResult(
        after_residue=after_residue,
        cleavage_before=cleavage_before,
        cleavage_after=cleavage_after,
        cleavage_preserved=cleavage_after == cleavage_before,
        disorder_shift=shift,
    )
