"""HGNC gene-symbol gazetteer for snippet subject-grounding.

``evidence_retrieval`` pulls candidate sentences out of full text by
hallmark regex. On papers that discuss several surface targets — which
is the norm in immunotherapy literature — a regex match can land on a
*sibling* protein's sentence: a CALR query pulling a CD47 sentence, a
GPRC5D query pulling a BCMA sentence. That is not noise; it is a wrong
anchored claim.

This module provides the two dictionaries the snippet extractor needs to
tell "about the target" from "about a competing gene":

* :func:`load_gazetteer` — the normalized set of all approved HGNC
  symbols + aliases + previous symbols, for *competing-gene* detection.
  Read once from the local ``data/external/hgnc/hgnc_complete_set.tsv``
  and cached. Degrades to an empty set when that (LFS-tracked) TSV is
  not hydrated — the competing-gene check simply goes dark while the
  target-mention check still works.
* :func:`build_target_names` — the *target's* own safe name set (symbol
  + non-ambiguous, symbol-shaped aliases) for the positive check.

:func:`extract_symbol_tokens` is the shared tokenizer so the extractor
and the gazetteer agree on what counts as a symbol mention. It is
case-sensitive: gene symbols in running biomedical text are written
uppercase, and requiring uppercase is what keeps English words ("was",
"set", "rest") from colliding with the genes that share their spelling.
"""

from __future__ import annotations

import csv
import logging
import re
from functools import lru_cache
from pathlib import Path

from accessible_surfaceome.paths import DATA_EXTERNAL_DIR

logger = logging.getLogger(__name__)


_DEFAULT_HGNC_TSV = DATA_EXTERNAL_DIR / "hgnc" / "hgnc_complete_set.tsv"

# Minimum normalized length for a token to count. Two-char symbols
# ("AR", "RO", "MS") are exactly the ambiguous ones; dropping them costs
# a little recall on the competing-gene check and buys a lot of
# precision.
_MIN_SYMBOL_LEN = 3

# All-caps tokens that appear constantly in biomedical text but are lab
# methods / reagents / fluorophores / stats — not gene mentions. Some
# coincide with real HGNC symbols (e.g. APC is also allophycocyanin in
# a flow-cytometry context); in this corpus the non-gene reading
# dominates, so we drop them from both the gazetteer and the target set.
_AMBIGUOUS_TOKENS: frozenset[str] = frozenset({
    "DNA", "RNA", "MRNA", "CDNA", "SIRNA", "SHRNA", "MIRNA", "NCRNA", "LNCRNA",
    "PCR", "QPCR", "RTPCR", "ELISA", "FACS", "IHC", "WB", "COIP", "CHIP",
    "NMR", "TEM", "SEM", "SDS", "PAGE", "TBS", "PBS", "BSA", "FBS", "EDTA",
    "DMSO", "HEPES", "DTT", "PFA", "ATP", "ADP", "AMP", "GTP", "GDP", "GMP",
    "NAD", "NADH", "FAD", "ROS", "HRP", "DAPI", "GFP", "RFP", "YFP", "CFP",
    "FITC", "APC", "RRID", "DOI", "PMID", "ORCID", "ELN", "FDR", "ANOVA",
})

# Token = uppercase-leading run of upper-alnum, with optional hyphenated
# continuations ("HER-2", "CD47", "GPRC5D", "TNFRSF17"). Case-sensitive
# on purpose — see the module docstring.
_SYMBOL_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b")

# A "clean" symbol-shaped string: only A-Z, digits, hyphens — no slashes,
# parentheses, or spaces. Exotic aliases like "HER-2/neu" or
# "p185(erbB2)" are deliberately rejected; the canonical symbol plus the
# clean aliases (HER2, CD340) carry the positive check.
_CLEAN_SYMBOL_RE = re.compile(r"[A-Z0-9-]+")


def normalize_symbol(raw: str) -> str:
    """Normalize a symbol-shaped string for comparison, or return ``""``.

    Upper-cases, then drops hyphens so "HER-2" and "HER2" compare equal.
    Returns ``""`` when ``raw`` is not symbol-shaped (contains slashes,
    parentheses, spaces, or lowercase-only content) — those are phrase
    aliases we don't try to match.
    """
    s = (raw or "").strip().upper()
    if not s or not _CLEAN_SYMBOL_RE.fullmatch(s):
        return ""
    return s.replace("-", "")


def extract_symbol_tokens(text: str) -> list[str]:
    """Return the normalized symbol-shaped tokens written uppercase in ``text``.

    Used on a single sentence by the snippet extractor. Tokens shorter
    than :data:`_MIN_SYMBOL_LEN` after normalization are dropped.
    """
    out: list[str] = []
    for match in _SYMBOL_TOKEN_RE.finditer(text):
        norm = match.group(0).replace("-", "")
        if len(norm) >= _MIN_SYMBOL_LEN:
            out.append(norm)
    return out


def build_target_names(
    symbol: str,
    aliases: tuple[str, ...] | list[str] = (),
    previous_symbols: tuple[str, ...] | list[str] = (),
) -> frozenset[str]:
    """Build the *target's* safe name set for the positive (in-sentence) check.

    Includes the canonical symbol plus any aliases / previous symbols
    that are symbol-shaped, long enough, and not in the ambiguous-token
    denylist. Phrase aliases ("HER-2/neu") and short/ambiguous ones
    ("RO", "NEU") are dropped — the canonical symbol and the clean
    aliases (HER2, CD340) are reliable enough.
    """
    names: set[str] = set()
    for raw in (symbol, *aliases, *previous_symbols):
        norm = normalize_symbol(raw)
        if norm and len(norm) >= _MIN_SYMBOL_LEN and norm not in _AMBIGUOUS_TOKENS:
            names.add(norm)
    return frozenset(names)


@lru_cache(maxsize=4)
def load_gazetteer(path: str | None = None) -> frozenset[str]:
    """Load the normalized HGNC symbol/alias gazetteer for competing-gene checks.

    Reads ``symbol``, ``alias_symbol``, and ``prev_symbol`` from every
    ``Approved`` row of the HGNC complete-set TSV. Alias/prev columns are
    pipe-separated. Result is cached (the file is large and static).

    Degrades gracefully: if the TSV is not present (LFS not hydrated in
    this worktree), logs a warning and returns an empty set — callers
    treat an empty gazetteer as "competing-gene check disabled".
    """
    tsv = Path(path) if path else _DEFAULT_HGNC_TSV
    if not tsv.exists():
        logger.warning(
            "HGNC gazetteer not hydrated at %s — competing-gene snippet "
            "filter disabled. Hydrate with: "
            'bash scripts/bootstrap-worktree.sh "data/external/hgnc/**"',
            tsv,
        )
        return frozenset()

    symbols: set[str] = set()
    with tsv.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if (row.get("status") or "").strip() != "Approved":
                continue
            for col in ("symbol", "alias_symbol", "prev_symbol"):
                raw = (row.get(col) or "").replace('"', "")
                for piece in raw.split("|"):
                    norm = normalize_symbol(piece)
                    if (
                        norm
                        and len(norm) >= _MIN_SYMBOL_LEN
                        and norm not in _AMBIGUOUS_TOKENS
                    ):
                        symbols.add(norm)
    logger.info("loaded HGNC gazetteer: %d normalized symbols from %s", len(symbols), tsv)
    return frozenset(symbols)


def sentence_subject(
    sentence: str,
    *,
    target_names: frozenset[str],
    gazetteer: frozenset[str],
) -> str:
    """Classify a sentence as ``"target"``, ``"competing"``, or ``"neither"``.

    * ``"target"`` — a target symbol/alias token is present. The check
      short-circuits here, so a sentence mentioning *both* the target
      and a sibling gene ("Unlike CD47, CALR is exposed...") is kept.
    * ``"competing"`` — no target token, but a different HGNC symbol is
      present. This is the sibling-target misfire; the caller drops it.
    * ``"neither"`` — no symbol-shaped gene token at all (the sentence
      may refer to the protein anaphorically); the caller keeps it at
      base score.

    With both sets empty the result is always ``"neither"`` — i.e. the
    filter is a no-op, which is the backwards-compatible default.
    """
    if not target_names and not gazetteer:
        return "neither"
    tokens = extract_symbol_tokens(sentence)
    if any(tok in target_names for tok in tokens):
        return "target"
    if gazetteer and any(
        tok in gazetteer and tok not in target_names for tok in tokens
    ):
        return "competing"
    return "neither"


__all__ = [
    "build_target_names",
    "extract_symbol_tokens",
    "load_gazetteer",
    "normalize_symbol",
    "sentence_subject",
]
