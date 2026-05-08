"""Triage-specific tool wiring.

The triage agent uses the same three custom tools as the deep dive
(``gene_lookup``, ``patent_lookup``, ``gene_literature``), but its view of
the M1 panel is narrower: ``db_panel`` returns are filtered to exclude the
``patent_handle`` and ``deeptmhmm`` sources before reaching the agent.
Rationale:

* ``patent_handle`` is an internal curated lane, not a public dataset.
  Whether a protein appears in our patent set should not bias the
  cheap accessibility-only triage call. The deep dive still sees it.
* ``deeptmhmm`` is a TM-prediction whose signal is already covered by
  UniProt's structured topology features (``signal_peptide`` /
  ``transmembrane`` / ``intramembrane`` / ``gpi_anchor``). Removing it
  forces the triage agent to reason from authoritative annotations
  rather than averaging in a redundant ML prediction.

Everything else is delegated to the deep-dive's ``tool_registry``.
"""

from __future__ import annotations

from typing import Any, Callable

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import DBVotePanel, SourceVote
from accessible_surfaceome.tools._shared.source_text import SourceTextStore

from accessible_surfaceome.agents.surface_annotator.tool_registry import (
    custom_tool_definitions as _deepdive_custom_tool_definitions,
)
from accessible_surfaceome.agents.surface_annotator.tool_registry import (
    build_handlers as _deepdive_build_handlers,
)


_TRIAGE_HIDDEN_SOURCES: frozenset[str] = frozenset({"patent_handle", "deeptmhmm"})


def _filter_db_panel(panel: DBVotePanel) -> DBVotePanel:
    """Return a copy of ``panel`` with hidden sources removed.

    Recomputes ``n_sources_voting_surface`` / ``in_db_union`` against the
    filtered set, and zeroes ``in_patent_handles`` (the triage agent should
    not condition its call on patent membership).
    """

    visible: list[SourceVote] = [
        s for s in panel.sources if s.source not in _TRIAGE_HIDDEN_SOURCES
    ]
    return DBVotePanel(
        hgnc_symbol=panel.hgnc_symbol,
        uniprot_acc=panel.uniprot_acc,
        sources=visible,
        n_sources_voting_surface=sum(1 for s in visible if s.vote),
        in_db_union=any(s.vote for s in visible),
        in_patent_handles=False,
    )


def _wrap_gene_lookup(
    handler: Callable[[dict[str, Any]], Any],
) -> Callable[[dict[str, Any]], Any]:
    def _call(payload: dict[str, Any]) -> Any:
        result = handler(payload)
        if isinstance(result, DBVotePanel):
            return _filter_db_panel(result)
        return result

    return _call


def custom_tool_definitions() -> list[dict[str, Any]]:
    """Tool definitions the triage agent registers with its remote agent.

    Same set as the deep dive (``gene_lookup``, ``patent_lookup``,
    ``gene_literature``) — the *behaviour* of ``gene_lookup`` differs
    (db_panel filtered) but the JSON schema the agent calls is identical.
    """

    return _deepdive_custom_tool_definitions()


def build_handlers(
    http: CachedHTTP, *, source_store: SourceTextStore | None = None
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    handlers = _deepdive_build_handlers(http, source_store=source_store)
    if "gene_lookup" in handlers:
        handlers["gene_lookup"] = _wrap_gene_lookup(handlers["gene_lookup"])
    return handlers
