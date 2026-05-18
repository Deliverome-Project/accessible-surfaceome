"""Tiny gazetteer mapping common cell-line tokens → species.

Used by the v2 orchestrator's deterministic species post-pass: when an
``ExpressionObservation`` / ``TissueContext`` / ``CellTypeContextV1`` /
``AccessibilityModulationObservation`` row has ``species="unspecified"``
but its free-text fields mention a cell line whose species is encoded
in the line name itself (MC3T3-E1 is unambiguously mouse), we can fill
the field deterministically without a model call.

Intentionally tiny — ~40 entries covering the most-cited lines across
the methodology categories the pipeline pulls from. Not a Cellosaurus
replacement; the agent prompt is still the primary path. False
positives are worse than misses here, so include only lines whose
name leaves no ambiguity.

Lookup is token-based with word-boundary regex so "MCF7" matches but
"MCF7-derived line PMCF7XX" doesn't double-match anything spurious.

To extend: add to ``_CELL_LINES`` keyed by the canonical line name
(spaces / hyphens / case normalized at lookup). One line per row.
"""

from __future__ import annotations

import re
from typing import Final

from .models import Species


# Cell-line → species. Keys are normalized (uppercase, no spaces/hyphens)
# for matching; original tokens with separators are reconstructed at
# match time via the regex below.
#
# Coverage rationale (groups):
# * Glioma / glioblastoma (Delaveris 2026 used these): U251, U87, T98G,
#   LN229 — all human.
# * Mouse osteoblast (SRC sample's RANKL paper): MC3T3-E1, MLO-Y4.
# * Rat thyroid (SRC sample's NIS papers): FRTL-5, PCCL3.
# * Hematopoietic / immune (CD81 / WT1 samples): THP-1, K562, Jurkat,
#   RAMOS, RAJI, MOLM-13, U937, HL-60 — all human.
# * Breast cancer (ATP5F1B / HSPA5 samples): MCF7, MDA-MB-231, T47D,
#   SK-BR-3, BT474 — all human.
# * Lung (CLDN18, EGFR): A549, H1299, H460, NCI-H1975, BEAS-2B — human.
# * Liver: HepG2, Hep3B, Huh7 — human.
# * Cervical / kidney workhorses: HeLa, HEK293 (+ HEK293T), Caco-2,
#   MDCK — HeLa/HEK293/Caco-2 human, MDCK dog.
# * Mouse workhorses: NIH-3T3, RAW 264.7, 4T1, B16, EL4, J774.
# * Rat workhorses: PC12, Rat-1, RBL-2H3, INS-1.
# * Hamster: CHO, BHK-21.
# * Monkey kidney: COS-1, COS-7, Vero (Vero is African green monkey ≠
#   macaque, but ``Species`` enum collapses to "macaque" or "other";
#   tagged "other" to avoid misroute).
_CELL_LINES: Final[dict[str, Species]] = {
    # --- human ---
    "U251": "human",
    "U251MG": "human",
    "U87": "human",
    "U87MG": "human",
    "T98G": "human",
    "LN229": "human",
    "THP1": "human",
    "K562": "human",
    "JURKAT": "human",
    "RAMOS": "human",
    "RAJI": "human",
    "MOLM13": "human",
    "U937": "human",
    "HL60": "human",
    "MCF7": "human",
    "MDAMB231": "human",
    "T47D": "human",
    "SKBR3": "human",
    "BT474": "human",
    "A549": "human",
    "H1299": "human",
    "H460": "human",
    "NCIH1975": "human",
    "BEAS2B": "human",
    "HEPG2": "human",
    "HEP3B": "human",
    "HUH7": "human",
    "HELA": "human",
    "HEK293": "human",
    "HEK293T": "human",
    "CACO2": "human",
    "HCT116": "human",
    "SW480": "human",
    "HUVEC": "human",
    "PANC1": "human",
    "MIAPACA2": "human",
    # --- mouse ---
    "MC3T3E1": "mouse",
    "MLOY4": "mouse",
    "NIH3T3": "mouse",
    "3T3": "mouse",
    "RAW264.7": "mouse",
    "RAW2647": "mouse",
    "4T1": "mouse",
    "B16": "mouse",
    "B16F10": "mouse",
    "EL4": "mouse",
    "J774": "mouse",
    "C2C12": "mouse",
    "L929": "mouse",
    "P815": "mouse",
    # --- rat ---
    "FRTL5": "rat",
    "PCCL3": "rat",
    "PC12": "rat",
    "RAT1": "rat",
    "RBL2H3": "rat",
    "INS1": "rat",
    # --- hamster ---
    "CHO": "other",   # Chinese hamster — Species enum lacks hamster; tag "other"
    "BHK21": "other",
    # --- monkey (Vero = African green monkey, COS = SV40-transformed CV-1) ---
    "COS1": "other",
    "COS7": "other",
    "VERO": "other",
    # --- dog ---
    "MDCK": "dog",
}


# Regex pattern from the keys: build once, match many. Word boundaries
# (\b) + non-greedy alphanumeric/hyphen separator handling lets us
# match "MC3T3-E1" and "MC3T3 E1" and "MC3T3E1" against the same key
# "MC3T3E1". Inserting an optional [-\s]? between every adjacent pair
# of characters in the key would generate a giant regex; instead we
# normalize the input text by stripping [-\s_.] before matching.
_LINE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    # Min 2 chars so short cell-line suffixes like "E1" in "MC3T3 E1"
    # survive tokenization and get joined via the adjacent-pair pass.
    r"\b[A-Za-z0-9][A-Za-z0-9._\-]{1,30}\b"
)


def _normalize_token(tok: str) -> str:
    """Strip separators + uppercase so 'MC3T3-E1' → 'MC3T3E1'."""
    return re.sub(r"[-\s_.]+", "", tok).upper()


def infer_species_from_text(text: str) -> Species | None:
    """Scan ``text`` for any known cell-line token and return its species.

    Matches against single tokens and adjacent token pairs (so "MC3T3 E1"
    and "RAW 264.7" resolve to the same keys as "MC3T3-E1" / "RAW264.7").

    Returns ``None`` if no token matched OR if two tokens matched with
    conflicting species (e.g. one human + one mouse cell line both
    mentioned in the same row → ambiguous, don't guess). This is the
    "false positives are worse than misses" policy.
    """
    if not text:
        return None
    tokens = _LINE_TOKEN_RE.findall(text)
    matched: set[Species] = set()
    for tok in tokens:
        species = _CELL_LINES.get(_normalize_token(tok))
        if species is not None:
            matched.add(species)
    # Also try adjacent token pairs to catch space-separated lines
    # like "MC3T3 E1" or "RAW 264.7" without polluting the single-token
    # path.
    for a, b in zip(tokens, tokens[1:], strict=False):
        species = _CELL_LINES.get(_normalize_token(a + b))
        if species is not None:
            matched.add(species)
    if len(matched) == 1:
        return next(iter(matched))
    return None  # zero matches OR multi-species conflict


__all__ = ["infer_species_from_text"]
