"""Stage 1 of a literature refresh: find papers new since a record ($0, no LLM).

Runs the same deterministic kickoff searches a full annotate runs (both A1 and
A2 focuses, through the runner's own ``_build_gene_context`` →
``build_kickoff`` → ``_execute_plan``), so a refresh sees exactly the paper
universe a fresh annotate would. Three filters then narrow that universe to
papers worth screening:

* **date** — first published after the record's generation date. Search
  responses are cached for 30 days, so the HTTP client passed in must bypass
  the cache for the search endpoints (:func:`open_refresh_client`); otherwise
  the refresh would replay a pre-cutoff listing and find nothing.
* **not already cited** — the record's evidence ledger source ids.
* **names the gene** — the approved symbol, an alias, a previous symbol or the
  approved name appears in the title or abstract. The broad topic queries
  return recent papers about other genes; this free check keeps them away from
  the paid abstract screen. Papers that arrived as body clips from a targeted
  evidence search are kept regardless — those searches are already anchored
  on the gene.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import paper_source_id
from accessible_surfaceome.tools._shared.cache import Cache
from accessible_surfaceome.tools._shared.http import CachedHTTP, default_cache_path
from accessible_surfaceome.tools._shared.models import IdentifierBundle, Paper
from accessible_surfaceome.tools._shared.ratelimit import default_limiter

from .dates import resolve_publication_dates

# Cache labels of the search/listing endpoints the kickoff plan hits. Full-text
# fetches use separate labels (europepmc_fulltext, pmc_xml, ncbi_pmc_efetch,
# unpaywall_pdf) and keep their long-lived cache.
SEARCH_SOURCES: frozenset[str] = frozenset(
    {"europepmc", "ncbi", "ncbi_pubmed_esearch", "pubtator"}
)

Exclusion = Literal["before_cutoff", "already_cited", "no_gene_mention", "undated"]


def open_refresh_client() -> CachedHTTP:
    """A ``CachedHTTP`` that always re-queries the search endpoints."""
    return CachedHTTP(
        Cache(default_cache_path()), default_limiter(), fresh_sources=SEARCH_SOURCES
    )


@dataclass
class NewCandidate:
    source_id: str
    title: str
    published: date | None
    focuses: list[str]
    has_body_clips: bool
    has_abstract: bool


@dataclass
class DiscoveryDiff:
    """Per-gene result of stage 1. Serializable to a flat report row."""

    gene: str
    hgnc_id: str
    cutoff: date
    n_discovered: int
    candidates: list[NewCandidate] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    # Not serialized: the Paper objects the screen stage re-uses so it does not
    # have to search again.
    papers: dict[str, Paper] = field(default_factory=dict, repr=False)

    @property
    def n_candidates(self) -> int:
        return len(self.candidates)

    def to_row(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "hgnc_id": self.hgnc_id,
            "cutoff": self.cutoff.isoformat(),
            "n_discovered": self.n_discovered,
            "n_new_candidates": self.n_candidates,
            **{f"n_excluded_{k}": v for k, v in sorted(self.excluded.items())},
            "new_source_ids": ";".join(c.source_id for c in self.candidates),
        }


# Aliases shorter than this are not trusted on their own: short alias symbols
# collide with unrelated abbreviations (KLK15's "ACO" matches ACC oxidase and
# trial acronyms; IL24's "ST16" matches a bacterial sequence type).
MIN_ALIAS_LEN = 5


def _symbol_regex(symbol: str) -> str:
    """Whole-token regex tolerating a hyphen/space at letter↔digit boundaries.

    ``IL24`` matches "IL24", "IL-24" and "IL 24"; ``HSP90AB1`` matches
    "HSP90AB1" and "HSP-90AB1".
    """
    parts = re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", symbol)
    body = r"[-\s]?".join(re.escape(p) for p in parts)
    return rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])"


def gene_name_patterns(bundle: IdentifierBundle) -> list[re.Pattern[str]]:
    """Patterns that count as the paper naming this gene.

    The approved symbol and previous symbols match case-sensitively as whole
    tokens (hyphen/space tolerant); aliases only when at least
    :data:`MIN_ALIAS_LEN` characters long; the approved name case-insensitively
    with any run of spaces/hyphens between its words.
    """
    symbols = {bundle.hgnc_symbol, *bundle.previous_symbols}
    symbols |= {a for a in bundle.aliases if a and len(a) >= MIN_ALIAS_LEN}
    pats = [re.compile(_symbol_regex(s)) for s in sorted(symbols) if s and len(s) >= 3]
    if bundle.approved_name:
        words = [re.escape(w) for w in re.split(r"[\s-]+", bundle.approved_name.strip()) if w]
        pats.append(re.compile(r"[\s-]+".join(words), re.IGNORECASE))
    return pats


def mentions_gene(paper: Paper, patterns: list[re.Pattern[str]]) -> bool:
    text = f"{paper.title or ''}\n{paper.abstract or ''}"
    return any(p.search(text) for p in patterns)


def filter_new(
    papers: dict[str, Paper | None],
    *,
    published: dict[str, date],
    cutoff: date,
    cited_ids: set[str],
    body_clip_ids: set[str],
    patterns: list[re.Pattern[str]],
) -> tuple[list[str], dict[str, int]]:
    """Apply the three stage-1 filters. Returns (kept source ids, exclusion counts).

    Pure function (no I/O) so the rules are unit-testable. An undated paper is
    kept when its ``year`` is on or after the cutoff year — dropping it would
    silently hide PMC-only preprints that EuropePMC has not dated yet.
    """
    kept: list[str] = []
    excluded: dict[str, int] = {}

    def _drop(reason: Exclusion) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    for sid, paper in papers.items():
        if sid in cited_ids:
            _drop("already_cited")
            continue
        when = published.get(sid)
        if when is None:
            year = paper.year if paper is not None else None
            if year is None or year < cutoff.year:
                _drop("undated")
                continue
        elif when <= cutoff:
            _drop("before_cutoff")
            continue
        if sid not in body_clip_ids and (paper is None or not mentions_gene(paper, patterns)):
            _drop("no_gene_mention")
            continue
        kept.append(sid)
    return kept, excluded


def discover_new(
    hgnc_id: str,
    *,
    cutoff: date,
    cited_ids: set[str],
    http: CachedHTTP,
    retraction_index: Any,
) -> DiscoveryDiff:
    """Run both kickoff searches for one gene and return what is new since ``cutoff``."""
    # Lazy imports keep ``--help`` fast and avoid the heavy agent import until
    # a gene is actually processed.
    from accessible_surfaceome.agents._support.timing import TimingRecorder
    from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
        build_kickoff,
    )
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        _build_gene_context,
        _execute_plan,
    )

    context = _build_gene_context(hgnc_id, http=http, retraction_index=retraction_index)
    papers: dict[str, Paper | None] = {}
    focuses: dict[str, set[str]] = {}
    body_clip_ids: set[str] = set()
    for focus in ("a1", "a2"):
        plan = build_kickoff(focus, context.n_tmh, context.ecd_aa)
        _pool, _log, by_source, discovered = _execute_plan(
            plan,
            context=context,
            http=http,
            retraction_index=retraction_index,
            timing=TimingRecorder(),
            timing_phase="literature_refresh_discover",
        )
        for paper in discovered.values():
            sid = paper_source_id(paper)
            papers[sid] = papers.get(sid) or paper
            focuses.setdefault(sid, set()).add(focus)
        for sid in by_source:
            papers.setdefault(sid, None)
            focuses.setdefault(sid, set()).add(focus)
            body_clip_ids.add(sid)

    published = resolve_publication_dates(papers, http)
    kept, excluded = filter_new(
        papers,
        published=published,
        cutoff=cutoff,
        cited_ids=cited_ids,
        body_clip_ids=body_clip_ids,
        patterns=gene_name_patterns(context.bundle),
    )
    diff = DiscoveryDiff(
        gene=context.bundle.hgnc_symbol,
        hgnc_id=hgnc_id,
        cutoff=cutoff,
        n_discovered=len(papers),
        excluded=excluded,
    )
    for sid in kept:
        paper = papers[sid]
        diff.candidates.append(
            NewCandidate(
                source_id=sid,
                title=(paper.title if paper is not None else ""),
                published=published.get(sid),
                focuses=sorted(focuses.get(sid, set())),
                has_body_clips=sid in body_clip_ids,
                has_abstract=bool(paper is not None and (paper.abstract or "").strip()),
            )
        )
        if paper is not None:
            diff.papers[sid] = paper
    return diff
