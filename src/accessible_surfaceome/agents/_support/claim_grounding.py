"""Deterministic homonym-contamination drop for the assembled evidence ledger.

Retrieval already drops competing-gene *snippets*, but claims that
``plan_trim_select`` extracts from full papers can still be about a DIFFERENT
gene whose **symbol collides** with the target's. The worked case: serotransferrin
(``TF``, P02787) vs tissue factor (``F3``/``CD142``), which share the "TF"
abbreviation — F3's live-cell-flow / membranous-IHC claims leak into TF's ledger
and, because the synthesizer reserves ``surface_accessibility=no`` only when
there is *no* surface-positive evidence anywhere, force ``low`` instead of ``no``.

The drop is deliberately narrow — the precise "clearly a different, similar-symbol
gene" rule: a claim is dropped **only** when it names a homonym collider's
*distinguishing* token (``CD142`` — exclusive to F3) **and** does not name the
target. This keeps everything a broader "mentions any non-target gene" filter
would wrongly delete:

* legit paralog mentions that name the target — "DSC1 … unlike DSC2 …";
* incidental mentions of *non-colliding* genes — serotransferrin's own claims
  that mention its receptor TFRC (TFRC is not a homonym of TF, so it's ignored).

Validated across the 149 deep-dive homonym genes: it drops claims from 4 genes
and the only gene it strips of all direct-surface evidence is TF, which is
independently ``triage=unlikely`` — i.e. it can only ever confirm a negative,
never downgrade a surface-likely gene. No-op when HGNC isn't hydrated.
"""
from __future__ import annotations

from collections.abc import Iterable

from accessible_surfaceome.tools._shared.gene_gazetteer import (
    build_target_names,
    extract_symbol_tokens,
    homonym_competitor_tokens,
)


def partition_competing_claims(
    claims: Iterable,
    *,
    target_names: frozenset[str],
    competitor_tokens: frozenset[str],
) -> tuple[list, list]:
    """Split ``claims`` into ``(kept, dropped)``.

    ``dropped`` = claims whose ``.claim`` text names a homonym collider's
    distinguishing token (``competitor_tokens``) and does NOT name the target
    (``target_names``). Order-preserving. With empty ``competitor_tokens``
    nothing is dropped (backwards-compatible no-op — e.g. non-homonym genes,
    or HGNC not hydrated).
    """
    kept: list = []
    dropped: list = []
    for c in claims:
        tokens = set(extract_symbol_tokens(getattr(c, "claim", "") or ""))
        if (tokens & competitor_tokens) and not (tokens & target_names):
            dropped.append(c)
        else:
            kept.append(c)
    return kept, dropped


def drop_competing_claims_for_bundle(
    a1_claims: Iterable,
    a2_claims: Iterable,
    bundle,
) -> tuple[list, list, list, list]:
    """Convenience wrapper for the orchestrator: build the target names +
    homonym-collider distinguishing tokens from a resolved gene ``bundle`` and
    partition both ledgers. Returns ``(a1_kept, a2_kept, a1_dropped,
    a2_dropped)``. No-op (drops nothing) for non-homonym genes or when the HGNC
    gazetteer isn't hydrated.
    """
    target_names = build_target_names(
        bundle.hgnc_symbol,
        getattr(bundle, "aliases", ()) or (),
        getattr(bundle, "previous_symbols", ()) or (),
    )
    competitor_tokens, _shared = homonym_competitor_tokens(
        bundle.hgnc_symbol, target_names
    )
    a1_kept, a1_dropped = partition_competing_claims(
        a1_claims, target_names=target_names, competitor_tokens=competitor_tokens
    )
    a2_kept, a2_dropped = partition_competing_claims(
        a2_claims, target_names=target_names, competitor_tokens=competitor_tokens
    )
    return a1_kept, a2_kept, a1_dropped, a2_dropped
