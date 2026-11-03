"""The enrichment pass has to record that it searched, or its resume is a lie.

``publish_tag_sites`` writes one row per SITE, so a member the pass ran and
found nothing in leaves no trace — and ~80% of these members have no published
loop insertion, so that is the majority outcome. Without a per-member row in
``tag_site_gene_public`` the sweep's skip set is permanently empty: every resume
re-runs the whole cohort at roughly $1 a member and never converges.

The first pass gets its rows from ``scripts/publish_tag_site_genes.py``, a
separate maintenance pass over the committed viewer snapshots. That cannot work
here — only three snapshots are committed, and these records live in D1 — so the
enrichment stamps its own row at run time, which is also what the repo's
prompt-provenance rule asks for.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "enrich_tag_site_lit", ROOT / "scripts/enrich_tag_site_lit.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


enrich = _load()

SERIES = "literature_enriched_v1"
SHA = "c" * 64


class _Result:
    """The fields ``searched_row`` reads off a ``TagSiteResult``."""

    def __init__(self, *, prompt_sha: str = SHA, others: list | None = None) -> None:
        self.prompt_sha = prompt_sha
        self.prompt_version = "2.0.0"
        self.model = "claude-opus-5"
        self.schema_version = "1.1.0"
        self.generated_at = "2026-10-18T00:00:00Z"
        self.notes = "two loops, one published insertion"
        self.other_positions = others or []


class _Member:
    gene_symbol = "KCNN2"
    candidate_id = "l1-p1037"


def row(*, n_sites: int = 1, result: _Result | None = None, n_papers: int = 312):
    sites = [{"provenance": enrich.ENRICHED_PROVENANCE, "position": 458 + i}
             for i in range(n_sites)]
    return enrich.searched_row(
        _Member(), result or _Result(), sites,
        base_acc="P70604", run_series=SERIES, n_papers=n_papers,
    )


def test_the_row_counts_the_members_enriched_sites() -> None:
    r = row(n_sites=2)
    assert r is not None
    assert r["n_sites"] == 2


def test_a_member_that_found_nothing_is_recorded_as_a_dated_zero() -> None:
    """The row this whole mechanism exists for. Re-running it buys the same
    empty answer for the same money."""
    r = row(n_sites=0)
    assert r is not None
    assert r["n_sites"] == 0
    assert r["prompt_sha"] == SHA
    assert r["searched_at"] == "2026-10-18T00:00:00Z"


def test_the_row_names_the_member_and_the_series_not_just_the_gene() -> None:
    """Keyed on ``(gene_symbol, candidate_id, run_series)``. A gene-keyed row
    here would overwrite the first pass's and destroy its dated zero."""
    r = row()
    assert r is not None
    assert r["gene_symbol"] == "KCNN2"
    assert r["candidate_id"] == "l1-p1037"
    assert r["run_series"] == SERIES
    assert r["uniprot_acc"] == "P70604"


def test_the_discovery_count_is_carried() -> None:
    r = row(n_papers=312)
    assert r is not None
    assert r["n_papers"] == 312


def test_a_run_that_never_reached_the_model_claims_no_search() -> None:
    """No ``prompt_sha`` means no LLM pass happened — a paused run, say. Writing
    a row for it would date a search that was never made, and the next resume
    would skip the member forever."""
    assert row(result=_Result(prompt_sha="")) is None


def test_other_positions_ride_along() -> None:
    """Cytoplasm-facing and function-abrogating insertions are per-gene facts
    that live on this row; they have nowhere else to go."""
    r = row(result=_Result(others=[{"position": 12, "why": "intracellular"}]))
    assert r is not None
    assert r["n_other_positions"] == 1
