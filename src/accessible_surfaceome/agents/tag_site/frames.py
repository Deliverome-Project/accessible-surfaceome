"""Reading a tag position out of a FOREIGN proteoform frame, safely.

``residue_mentions`` confirms a cited residue against ONE sequence, and says so
in its own docstring: "a paper numbering in a different frame (mature protein,
another isoform) will therefore not match and is dropped here ... recovering
such a frame is the synthesis stage's work, with the REPL." This module does it
deterministically instead, because the loss is not rare and it is not only about
papers.

Two separate causes, one mechanism:

* **The paper's frame.** A methods section numbers its insertion in whatever
  frame it used. Of the published literature sites carrying a junction, 198 sit
  at ``position_evidence='inferred'``; a hand audit of the frame-recoverable
  ones found a single sentence that places a tag in three different genes
  "between amino acids 4 and 5 of the mature ... subunit" — three sites whose
  junction the agent had already computed correctly and could not prove.
* **Our own frame.** A designed ORF is an Ensembl-transcript product, and for a
  substantial minority that is a UniProt *isoform* record rather than the
  canonical one. In the L1 internal-site set, 71 of 566 members are numbered on
  something other than the human canonical sequence. A canonical-framed
  position for one of those is a position in a different protein.

So the reference frame is whatever sequence the construct is actually built
from, and canonical / mature / isoform / ortholog are alternates a citation may
be speaking in.

GUARDS
------
Generosity without a guard is a coincidence generator: with k frames, a random
letter-and-number token confirms somewhere with probability ~1-(19/20)^k. Two
rules, both derived from hand-adjudicating the real sentences (see
``tests/test_tag_sites_frames.py``):

1. **A non-reference frame validates only if it is LICENSED** — either the text
   names it ("of the mature ... subunit", "of the rat KCC2b"), or at least two
   LETTER-CONFIRMED tokens resolve in that same frame ("Asn-549 and Asp-550",
   each agreeing with the frame's sequence). Bare positional forms
   ("positions 383 and 384") name no residue identity, confirm in every frame
   trivially, and so license nothing.
2. **A named frame wins or nothing does.** If the text names a frame we do not
   hold — a rat sequence, say — then a frame that merely happens to fit is not
   promoted in its place. Publishing a human coordinate derived from a rat
   position with arithmetic behind it is worse than declining.

A hit that is not licensed is still RECORDED. "The citation numbers this in a
rat frame at 383" is a fact worth carrying on the record; it just is not a
validated human position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .literature_discovery import (
    LETTER_CONFIRMED_FORMS,
    SPELLED_AA_FORMS,
    residue_mentions_detailed,
)

#: Frame families. ``reference`` is the sequence the construct is built from —
#: the member's own translated ORF — and is the frame every accepted position is
#: finally expressed in.
REFERENCE = "reference"
MATURE = "mature"
ISOFORM = "isoform"
ORTHOLOG = "ortholog"

#: Species whose numbering a paper might be using. Human is deliberately ABSENT:
#: nearly every paper in the corpus says "human" somewhere, so reading it as a
#: frame name would fire the named-frame rule on almost everything and defeat
#: guard 2 entirely.
_SPECIES = (
    "rat|mouse|murine|rodent|bovine|porcine|ovine|canine|feline|rabbit|chicken|"
    "chick|quail|zebrafish|xenopus|frog|monkey|macaque|cynomolgus|marmoset|"
    "hamster|guinea pig|drosophila|yeast|c\\. ?elegans"
)

# A species word only names a FRAME when it is attached to the thing being
# numbered. "mouse monoclonal antibody" and "rat anti-HA" are ubiquitous in
# methods text and say nothing about coordinates, so a bare species mention is
# not enough — it has to read as "of the rat KCC2b" or "rat numbering".
_RE_SPECIES_OF = re.compile(rf"\bof\s+(?:the\s+)?({_SPECIES})\b", re.I)
_RE_SPECIES_NUMBERING = re.compile(
    rf"\b({_SPECIES})\s+(?:numbering|sequence|coordinates|orthologu?e)\b", re.I
)
# Likewise "mature": "mature mRNA", "mature dendritic cells" are not frames.
_RE_MATURE = re.compile(
    r"\b(?:of|in)\s+the\s+mature\b"
    r"|\bmature\s+(?:protein|peptide|polypeptide|form|subunit|receptor|chain)\b"
    r"|\bmature[- ]protein\s+numbering\b",
    re.I,
)
_RE_PRECURSOR = re.compile(r"\b(?:precursor|pro-?protein|pre-?pro-?protein)\b", re.I)
_RE_ISOFORM = re.compile(
    r"\bisoform\s+(?:\d+|[A-Za-z]\b)|\bsplice\s+variant\s+(?:\d+|[A-Za-z]\b)", re.I
)

#: How far a cited position may sit from the junction and still be read as
#: naming it. Papers differ on whether the label is the residue before or after
#: the insertion point, which ``residue_mentions`` documents.
DEFAULT_TOLERANCE = 1

#: Half-width of the sequence neighbourhood used to map a frame position back to
#: the reference when there is no constant offset.
_WINDOW = 9
#: A window shorter than this cannot identify a coordinate uniquely enough to
#: be worth trusting.
_MIN_WINDOW = 8


@dataclass(frozen=True)
class Frame:
    """One proteoform the cited position might be numbered in.

    ``offset`` is the constant to add to a position in this frame to reach the
    reference coordinate — known exactly for a mature frame (the signal-peptide
    length) and for any frame differing from the reference by a single terminal
    truncation. ``None`` means the relationship is not a constant shift (an
    internal indel, an ortholog) and the coordinate must be recovered from the
    sequence itself.
    """

    label: str
    sequence: str
    offset: int | None = None
    #: Whether a publication would be expected to number in THIS frame.
    #:
    #: Guard 1 asks "is this paper numbering somewhere unusual?", and that
    #: question is only meaningful relative to where papers normally number:
    #: canonical UniProt. When the reference frame is a construct WE designed —
    #: a library member whose ordered form is an isoform or a designed ORF —
    #: canonical is not a suspicious alternate, it is almost certainly the frame
    #: the paper used, and the member frame is one no publication has seen. KCNN2
    #: is the worked case: "between aa 246 and 247" names no frame and spells no
    #: residue, so Guard 1 refuses canonical, yet canonical is exactly right and
    #: maps uniquely into the 791-aa construct.
    #:
    #: An expected frame is licensed by the strength of its MAPPING instead —
    #: a unique sequence window or an exact offset, agreeing on residue identity
    #: where the citation gives one. That is structural evidence rather than the
    #: near-chance letter-and-number coincidence the spelled-residue rule exists
    #: to suppress.
    expected: bool = False

    @property
    def family(self) -> str:
        """The frame FAMILY, which is what the text can name.

        Derived from the label so a caller cannot label a frame one thing and
        have it licensed as another: ``isoform:P54289-2`` is an ``isoform``,
        ``ortholog:rat:P12345`` is an ``ortholog``.
        """
        head = self.label.split(":", 1)[0]
        if head in (MATURE, ISOFORM, ORTHOLOG):
            return head
        return REFERENCE


@dataclass(frozen=True)
class FrameHit:
    """A cited position that resolves to ``reference_position`` in one frame."""

    frame_label: str
    frame_family: str
    frame_position: int
    reference_position: int
    #: Letter-bearing tokens anywhere in the text that this frame's sequence
    #: agrees with.
    letter_confirmed_tokens: int
    #: Of those, how many SPELL the residue ("Asn-549") rather than using the
    #: bare code form ("D2"). At least one is required before two tokens may
    #: license a frame — nomenclature yields codes, never spellings.
    spelled_tokens: int
    #: Whether the text NAMES this frame's family.
    frame_named: bool
    #: Whether this is a frame a publication would be expected to use.
    frame_expected: bool
    confers_validation: bool


@dataclass(frozen=True)
class FrameResolution:
    """Everything the text says about its own numbering, and what it licenses."""

    hits: tuple[FrameHit, ...] = ()
    validating_hit: FrameHit | None = None
    named_families: frozenset[str] = field(default_factory=frozenset)
    #: The text named a frame family we do not hold, so guard 2 refuses to
    #: promote any other frame in its place.
    blocked_by_unavailable_frame: bool = False
    #: Every position the text names, in the frames' own coordinates. Recorded
    #: even when nothing validates, so a record can say where the citation
    #: thinks the tag goes.
    cited_positions: frozenset[int] = field(default_factory=frozenset)


def named_frame_families(text: str | None) -> set[str]:
    """The frame families ``text`` explicitly names.

    ``precursor`` maps to the REFERENCE family, not to ``mature``: the UniProt
    canonical sequence IS the precursor, so a paper saying it numbers on the
    precursor is naming the unprocessed full-length form — the opposite of the
    mature frame, and usually the reference we already hold.
    """
    if not text:
        return set()
    out: set[str] = set()
    if _RE_MATURE.search(text):
        out.add(MATURE)
    if _RE_PRECURSOR.search(text):
        out.add(REFERENCE)
    if _RE_ISOFORM.search(text):
        out.add(ISOFORM)
    if _RE_SPECIES_OF.search(text) or _RE_SPECIES_NUMBERING.search(text):
        out.add(ORTHOLOG)
    return out


def letter_confirmed_positions(text: str | None, sequence: str | None) -> set[int]:
    """Positions named by a form that carries a residue IDENTITY and that
    ``sequence`` agrees with.

    These are the only tokens that can tell one frame from another: a bare
    number confirms everywhere, so it is no evidence for any particular frame.
    """
    detail = residue_mentions_detailed(text, sequence=sequence)
    return {n for n, forms in detail.items() if forms & LETTER_CONFIRMED_FORMS}


def map_to_reference(frame: Frame, position: int, *, reference: str) -> int | None:
    """``position`` in ``frame``, expressed in ``reference`` coordinates.

    Uses the frame's constant offset when it has one. Otherwise locates the
    residue's own neighbourhood in the reference and refuses when that
    neighbourhood is absent or occurs more than once — a guessed coordinate is
    how a cassette lands a hundred residues from where the paper put it.
    """
    if not frame.sequence or not reference:
        return None
    if not 1 <= position <= len(frame.sequence):
        return None
    if frame.offset is not None:
        mapped = position + frame.offset
        return mapped if 1 <= mapped <= len(reference) else None

    lo = max(0, position - 1 - _WINDOW)
    hi = min(len(frame.sequence), position + _WINDOW)
    window = frame.sequence[lo:hi]
    if len(window) < _MIN_WINDOW:
        return None
    first = reference.find(window)
    if first < 0 or reference.find(window, first + 1) != -1:
        return None  # absent, or ambiguous
    return first + (position - 1 - lo) + 1


def resolve(
    text: str | None,
    *,
    frames: list[Frame],
    reference_label: str,
    target: int,
    tolerance: int = DEFAULT_TOLERANCE,
) -> FrameResolution:
    """Which frames let ``text`` NAME the junction ``target``, and which of
    those are licensed to validate it.

    ``target`` is in reference coordinates. ``frames`` must include the
    reference frame itself (the one labelled ``reference_label``).
    """
    reference = next(
        (f.sequence for f in frames if f.label == reference_label), None
    )
    if not text or not frames or not reference:
        return FrameResolution()

    named = named_frame_families(text)
    named_alternates = named - {REFERENCE}
    available = {f.family for f in frames}
    blocked = bool(named_alternates) and not (named_alternates & available)

    window = {target + d for d in range(-tolerance, tolerance + 1)}
    hits: list[FrameHit] = []
    cited: set[int] = set()

    for frame in frames:
        detail = residue_mentions_detailed(text, sequence=frame.sequence)
        if not detail:
            continue
        cited |= set(detail)
        letter_forms = {
            n: forms for n, forms in detail.items() if forms & LETTER_CONFIRMED_FORMS
        }
        n_letter = len(letter_forms)
        n_spelled = sum(1 for f in letter_forms.values() if f & SPELLED_AA_FORMS)
        is_reference = frame.label == reference_label
        frame_named = frame.family in named_alternates
        for position in sorted(detail):
            mapped = map_to_reference(frame, position, reference=reference)
            if mapped is None or mapped not in window:
                continue
            if is_reference:
                # Unchanged behaviour: a quote naming the residue in the
                # protein's own frame is a validated position, and needs no
                # frame language to say so.
                #
                # Deliberately NOT subject to ``blocked``. Guard 2 exists to
                # stop an alternate frame being promoted in place of a named
                # frame we lack — it must never suppress the protein's own
                # frame, for two reasons: that is today's behaviour and this
                # module must not regress it, and the frame-name patterns can
                # false-positive on ordinary methods prose ("of the rat
                # anti-HA antibody"), which would otherwise silently downgrade
                # a correctly-cited site.
                licensed = True
            elif blocked:
                licensed = False
            elif named_alternates:
                # Guard 2: the text named an alternate family, so only that
                # family may speak for it. This outranks expectedness — if the
                # paper says it numbers in rat, canonical being the usual frame
                # is beside the point, because the paper has told us otherwise.
                licensed = frame_named
            elif frame.expected:
                # The frame a publication would be expected to use. Licensed by
                # the mapping, which has already succeeded to get here: either
                # an exact offset or a sequence window found exactly once. The
                # identity check below is redundant for a window mapping (the
                # window contains the position, so the letters agree by
                # construction) and is the real check for an offset one, where a
                # caller could supply a wrong offset.
                licensed = (
                    position not in letter_forms
                    or (
                        1 <= mapped <= len(reference)
                        and reference[mapped - 1].upper()
                        == frame.sequence[position - 1].upper()
                    )
                )
            else:
                # Guard 1: no frame named, so the frame has to earn it with two
                # letter-confirmed tokens, at least one of them SPELLING the
                # residue. Two bare codes are not independent evidence — a
                # receptor-nomenclature sentence produces three of them.
                licensed = n_letter >= 2 and n_spelled >= 1
            hits.append(
                FrameHit(
                    frame_label=frame.label,
                    frame_family=frame.family,
                    frame_position=position,
                    reference_position=mapped,
                    letter_confirmed_tokens=n_letter,
                    spelled_tokens=n_spelled,
                    frame_named=frame_named,
                    frame_expected=frame.expected,
                    confers_validation=licensed,
                )
            )
            break  # one hit per frame is enough to speak for it

    # Prefer the reference frame, then a frame the text actually named, then one
    # that earned it on tokens — so a record cites the strongest basis it has.
    def _rank(hit: FrameHit) -> tuple[int, int]:
        """Reference first — a position in the construct's own numbering needs
        no mapping. Then a frame the text NAMED, then the frame a publication
        would be expected to use, then one that earned it on tokens."""
        if hit.frame_label == reference_label:
            return (0, 0)
        if hit.frame_named:
            return (1, -hit.letter_confirmed_tokens)
        if hit.frame_expected:
            return (2, -hit.letter_confirmed_tokens)
        return (3, -hit.letter_confirmed_tokens)

    validating = sorted(
        (h for h in hits if h.confers_validation), key=_rank
    )
    return FrameResolution(
        hits=tuple(hits),
        validating_hit=validating[0] if validating else None,
        named_families=frozenset(named),
        blocked_by_unavailable_frame=blocked,
        cited_positions=frozenset(cited),
    )
