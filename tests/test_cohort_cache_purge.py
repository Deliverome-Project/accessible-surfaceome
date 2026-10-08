"""Couple the cohort cache-purge map to the two things it can drift from.

``scripts/cloud/sync_public_d1.py`` is the second writer into public D1
(``publish_record`` is the first). It rewrites whole tables that back
cohort-level Worker endpoints, and for a long time it purged nothing — so
a triage sweep landed in D1 while ``/v1/triage/export.tsv`` kept serving
the previous day's bytes, on an arbitrary subset of POPs.

The purge map that fixes it (``_COHORT_SURFACES_BY_TABLE``) is hand-written
against two external facts, both of which move without touching it:

1. which table groups ``sync_public_d1.py`` knows how to sync, and
2. which Worker routes are cached long enough to be worth purging.

These tests pin both.
"""

from __future__ import annotations

import re

import pytest

from accessible_surfaceome.cloud.surface_annotation import (
    _COHORT_SURFACES_BY_TABLE,
    cohort_purge_paths,
)
from accessible_surfaceome.paths import REPO_ROOT

_SYNC_SCRIPT = REPO_ROOT / "scripts" / "cloud" / "sync_public_d1.py"
_WORKER = (
    REPO_ROOT / "cloudflare" / "workers" / "surfaceome_api" / "src" / "index.js"
)

# Table groups that legitimately have no cohort surface to purge. Keeping
# them here (rather than as empty tuples in the map) means a NEW group
# added to the sync script fails the test below instead of silently
# defaulting to "purge nothing" — the exact failure mode this guards.
_NO_COHORT_SURFACE = {
    # /v1/orthologs/{SYMBOL} is per-gene: not a fixed list, needs a
    # gene-scoped sweep like purge_gene_cache.py.
    "compara",
    # Backs no cached cohort endpoint of its own.
    "gene_identifier",
}


def _sync_table_groups() -> set[str]:
    src = _SYNC_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"^_ALL_TABLES\s*=\s*\[(.*?)\]", src, re.MULTILINE | re.DOTALL)
    assert m, "could not find _ALL_TABLES in sync_public_d1.py"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_every_sync_group_is_classified() -> None:
    """A new ``--only`` group must be given a purge list or an exemption.

    Without this, adding a table group to the sync script silently inherits
    "no purge" — which is how the gap existed in the first place.
    """
    groups = _sync_table_groups()
    classified = set(_COHORT_SURFACES_BY_TABLE) | _NO_COHORT_SURFACE
    unclassified = groups - classified
    assert not unclassified, (
        f"sync_public_d1.py syncs {sorted(unclassified)} but neither "
        "_COHORT_SURFACES_BY_TABLE nor this test's _NO_COHORT_SURFACE "
        "says what that invalidates. Add the cohort endpoints it stales, "
        "or exempt it here with a reason."
    )


def test_no_stale_entries_in_purge_map() -> None:
    """Every key in the map is still a real sync group."""
    orphans = set(_COHORT_SURFACES_BY_TABLE) - _sync_table_groups()
    assert not orphans, (
        f"_COHORT_SURFACES_BY_TABLE has entries for {sorted(orphans)}, "
        "which sync_public_d1.py no longer syncs."
    )


def _long_cached_routes() -> set[str]:
    """Worker paths returned with ``CACHE_TTL_LONG`` from a cohort handler.

    Parsed rather than hardcoded so a handler dropped to ``CACHE_TTL_SHORT``
    (or promoted to long) shows up here.
    """
    src = _WORKER.read_text(encoding="utf-8")
    # Map handler name -> whether it returns ttl: CACHE_TTL_LONG.
    long_handlers = {
        name
        for name, body in re.findall(
            r"^async function (\w+)\(env[^)]*\)\s*\{(.*?)^\}",
            src,
            re.MULTILINE | re.DOTALL,
        )
        if "CACHE_TTL_LONG" in body
    }
    # Map route path -> handler, for the cohort (non-parameterized) routes.
    routes: set[str] = set()
    for path, handler in re.findall(
        r'path === "(/v1/[^"]+)"\)\s*return withEdgeCache\([^)]*?\(\)\s*=>\s*(\w+)\(',
        src,
    ):
        if handler in long_handlers:
            routes.add(path)
    return routes


@pytest.mark.skipif(not _WORKER.exists(), reason="Worker source not present")
def test_purge_map_covers_every_long_cached_cohort_route() -> None:
    """Every 1-day-TTL cohort route is purged by some sync group.

    The 60s routes (``/v1/catalog``, ``/v1/genes``, ``/v1/triage/{SYMBOL}``)
    are deliberately absent from the map — they self-heal — so this only
    asserts the long ones are covered, never that the short ones aren't.
    """
    long_routes = _long_cached_routes()
    assert long_routes, "parsed zero long-cached routes — the regex has rotted"
    covered = {p.split("?", 1)[0] for p in cohort_purge_paths(_sync_table_groups())}
    missing = long_routes - covered
    assert not missing, (
        f"Worker serves {sorted(missing)} with CACHE_TTL_LONG (1 day) but no "
        "sync group purges it — a sync would leave readers on stale bytes "
        "for up to a day. Add it to _COHORT_SURFACES_BY_TABLE."
    )


def test_query_variants_are_purged_for_the_one_include_query_route() -> None:
    """``/v1/triage/export.tsv`` keys per query string, so variants need listing.

    It is the only route wrapped with ``includeQuery: true``; the bare path
    does not cover ``?run_id=...``. If another route gains that flag, this
    test's premise needs revisiting.
    """
    src = _WORKER.read_text(encoding="utf-8")
    include_query_routes = re.findall(
        r'path === "(/v1/[^"]+)"\)\s*return withEdgeCache\([^;]*?includeQuery:\s*true',
        src,
    )
    assert include_query_routes == ["/v1/triage/export.tsv"], (
        "the set of includeQuery routes changed — each one caches per query "
        f"string and needs its public variants enumerated. Got: {include_query_routes}"
    )
    paths = cohort_purge_paths(["triage_run"])
    assert any("?" in p for p in paths), (
        "/v1/triage/export.tsv caches per query string but the purge list "
        "carries only the bare path"
    )


def test_unknown_groups_contribute_nothing() -> None:
    assert cohort_purge_paths(["not_a_table"]) == []
    assert cohort_purge_paths([]) == []


def test_paths_are_deduplicated() -> None:
    once = cohort_purge_paths(["triage_run"])
    twice = cohort_purge_paths(["triage_run", "triage_run"])
    assert once == twice
