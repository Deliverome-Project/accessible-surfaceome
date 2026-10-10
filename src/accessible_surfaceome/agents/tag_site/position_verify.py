"""Blind second opinion on whether a quote names an insertion position.

`residue_mentions` is a literal matcher, and a literal matcher has now rejected
a CORRECT citation three times in one day: a 448-character verbatim quote that
differed by one curly apostrophe, a "residues 484-516" span that names the
junction precisely, and five further spellings found in a single sitting. Each
was patched by adding a pattern. The enumeration does not close — "the 484th
residue", a superscript, an OCR artifact and a non-English methods section are
all still out there.

So the matcher stays as a fast path and this is the long tail: when it finds
nothing, ask a model what position the sentence states.

WHY THIS IS NOT CIRCULAR. `enforce_position_claims` exists because the model
OVERCLAIMS — it is the guard that catches a site asserting "validated" when its
own quote names no position. Asking the same model "did your quote support your
claim?" would be worthless; it already thinks so, which is why it claimed it.

The verifier is therefore BLIND: it is shown the sentence and nothing else. It
never sees the claimed residue, the gene, or that a claim is under review, so it
cannot rubber-stamp a position it does not know is wanted. The caller compares
its answer to the claim afterwards.

It can only ever UPGRADE. A verifier that could also downgrade would be a second
way to lose a correct site, and the deterministic path already decides that.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

#: Deliberately free of gene names, tag names and any mention of review, so the
#: answer cannot be steered toward a position the caller is hoping for.
_SYSTEM = (
    "You read one sentence from a methods section and report the residue "
    "position it states for an insertion, replacement or deletion in a protein.\n\n"
    "Answer with a single integer, or NONE.\n\n"
    "Report a position ONLY when the sentence states where in the protein "
    "sequence something was inserted, replaced or deleted. A span names its "
    "FIRST residue: 'residues 484-516 were replaced' is 484.\n\n"
    "Answer NONE when the number is anything else — a duration, a temperature, "
    "a concentration, a figure or table number, a cell line, a catalogue number, "
    "a year, a quantity of cells, or a reference marker. A sentence can contain "
    "numbers and still state no position; NONE is the common answer and the "
    "one to give whenever you are unsure."
)

_INT = re.compile(r"-?\d{1,6}")


def verify_position_blind(
    quote: str | None, *, client: Any, max_residue: int | None = None
) -> int | None:
    """The residue position ``quote`` states, or None.

    Any failure — no client, an API error, an unparseable reply — returns None,
    which leaves the caller's deterministic verdict exactly as it was.
    """
    if not quote or client is None or len(quote.strip()) < 12:
        return None
    try:
        resp = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=8,
            system=_SYSTEM,
            messages=[{"role": "user", "content": quote.strip()}],
        )
        text = "".join(
            getattr(b, "text", "") for b in getattr(resp, "content", []) or []
        ).strip()
    except Exception as exc:  # noqa: BLE001 - a verifier must never fail a run
        logger.warning("blind position verify failed: %s", exc)
        return None

    if not text or text.upper().startswith("NONE"):
        return None
    m = _INT.search(text)
    if not m:
        return None
    n = int(m.group(0))
    if n <= 0 or (max_residue is not None and n > max_residue):
        return None
    return n
