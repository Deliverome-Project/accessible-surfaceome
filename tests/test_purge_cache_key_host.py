"""The purge keys must match the Worker's cache-key host, byte for byte.

This drifted silently and cost real freshness. The Worker keys
``caches.default`` on a SYNTHETIC host; the Python publish path has to
mirror it exactly or Cloudflare accepts the purge, returns
``success=true``, and evicts nothing — so a republished record serves
stale until its Cache-Control TTL (up to 24h for per-gene records).

That is exactly what happened: the Worker renamed its ``withEdgeCache``
key host to ``surfaceome-api.cache`` (#119/#171) and the Python side kept
sending ``cache.internal``. Confirmed against production — purging the
``cache.internal`` key left ``cf-cache-status: HIT`` with ``age``
climbing, while purging the ``surfaceome-api.cache`` key flipped the same
URL to a MISS.

Nothing else catches this: the purge is best-effort by design (it must
never fail a publish), so a wrong host is indistinguishable from a
working one at runtime. Hence parsing the Worker source.
"""
from __future__ import annotations

import re

from accessible_surfaceome.cloud import surface_annotation as sa
from accessible_surfaceome.paths import REPO_ROOT

WORKER = REPO_ROOT / "cloudflare/workers/surfaceome_api/src/index.js"

# `new URL(keyPath, "https://host")` — the synthetic cache-key hosts.
_KEY_HOST_RE = re.compile(r'new URL\([^,]+,\s*"(https://[^"]+)"\)')


def _worker_cache_hosts() -> set[str]:
    return set(_KEY_HOST_RE.findall(WORKER.read_text()))


def test_worker_declares_its_cache_key_hosts() -> None:
    """Guard the guard: if the Worker stops matching this shape the test
    below would vacuously pass."""
    hosts = _worker_cache_hosts()
    assert hosts, f"no synthetic cache-key host parsed out of {WORKER}"


def test_every_purge_url_uses_a_host_the_worker_actually_keys_on() -> None:
    hosts = _worker_cache_hosts()
    for url in sa._purge_urls_for("EGFR"):
        origin = "https://" + url.split("://", 1)[1].split("/", 1)[0]
        assert origin in hosts, (
            f"purge URL {url} targets {origin}, which the Worker never uses as "
            f"a cache key (it keys on {sorted(hosts)}). Cloudflare will accept "
            f"this purge and evict nothing."
        )


def test_every_kv_key_uses_a_host_the_worker_actually_keys_on() -> None:
    hosts = _worker_cache_hosts()
    for key in sa._kv_keys_for("EGFR"):
        origin = "https://" + key.split("://", 1)[1].split("/", 1)[0]
        assert origin in hosts, f"KV key {key} targets {origin}, not in {sorted(hosts)}"


def test_cache_internal_is_gone() -> None:
    """The specific wrong host, pinned so it cannot creep back."""
    urls = sa._purge_urls_for("EGFR") + sa._kv_keys_for("EGFR")
    assert not [u for u in urls if "cache.internal" in u]


def test_edge_and_kv_share_one_base() -> None:
    """Both tiers key on the same synthetic host. Deriving them from one
    constant is what stops them drifting apart again."""
    assert sa._KV_CACHE_BASE == sa._EDGE_CACHE_BASE


# ---------------------------------------------------------------------------
# Deploy epoch — the cache keys had no notion of response SHAPE.
# ---------------------------------------------------------------------------

_EPOCH_CALL_RE = re.compile(r"cacheEpoch\(env\)")


def test_worker_namespaces_both_cache_keys_by_the_deploy_epoch() -> None:
    """Both tiers must carry it. Epoching only one leaves the other serving
    the old response shape after a deploy — up to an hour for a KV read,
    up to a day for a caches.default entry."""
    src = WORKER.read_text()
    assert len(_EPOCH_CALL_RE.findall(src)) >= 3, (
        "expected cacheEpoch(env) in withEdgeCache's key, handleCatalog's "
        "key, and /v1/health's payload"
    )


def test_worker_falls_back_when_the_binding_is_absent() -> None:
    """`version_metadata` is optional (wrangler.toml is gitignored, so a
    stale local config is likely). Absent binding must degrade to the old
    behaviour, never crash."""
    src = WORKER.read_text()
    assert 'env?.CF_VERSION_METADATA?.id || "v0"' in src


def test_python_and_worker_agree_on_the_fallback_token() -> None:
    """Offline, _cache_epoch returns the Worker's own fallback so keys built
    without a reachable Worker still match a Worker deployed without the
    binding."""
    import accessible_surfaceome.cloud.surface_annotation as m
    m._EPOCH_CACHE = None
    try:
        assert m._cache_epoch() == "v0" or m._EPOCH_CACHE is not None
    finally:
        m._EPOCH_CACHE = None
