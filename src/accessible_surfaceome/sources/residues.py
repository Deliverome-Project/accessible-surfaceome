"""Mapping non-standard residue letters onto the 20 standard amino acids.

Every sequence-based predictor used here -- metapredict, NetSurfP-3.0, SignalP -- rejects
non-standard letters outright rather than skipping them, so an unsanitised sequence does
not degrade a prediction, it aborts the shard or drops the protein.

That is not a rare edge case. The 24 human proteins containing U (selenocysteine) are the
selenoproteome, and GPX3 and GPX6 are signal-peptide positive, so they sit squarely in the
population these predictors exist to annotate. A first metapredict sweep silently lost all
27 affected proteoforms.

``modal/disorder_app.py`` carries a copy of this logic, because the Modal images for those
predictors do not install this package. ``tests/test_residues.py`` asserts the two agree.
"""

from __future__ import annotations

STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")

# U -> C is the standard substitution and biophysically sound: selenocysteine is a
# cysteine analogue with selenium for sulfur. O (pyrrolysine) -> K likewise. B, Z and J are
# ambiguity codes; each maps to one of the two residues it stands for. X (unknown) -> A,
# the least structurally opinionated residue.
SUBSTITUTIONS = {"U": "C", "O": "K", "B": "N", "Z": "Q", "J": "L", "X": "A"}


def sanitise(seq: str) -> tuple[str, bool]:
    """Return ``(standard-alphabet sequence, whether anything was substituted)``.

    The flag matters downstream: a prediction made on a substituted sequence is not quite a
    prediction about the real protein, and a reader should be able to tell.
    """
    if all(c in STANDARD_AA for c in seq):
        return seq, False
    return (
        "".join(SUBSTITUTIONS.get(c, "A") if c not in STANDARD_AA else c for c in seq),
        True,
    )
