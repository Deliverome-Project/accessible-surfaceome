"""Per-host minimum-interval throttle.

The agent calls custom tools synchronously and sequentially, but a single
``resolve`` fans out to four upstreams concurrently from a thread pool. We need
to ensure that bursts within one fan-out (and across consecutive gene calls in a
batch) respect upstream qps caps — particularly NCBI's 10 qps with API key.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from threading import Lock
from urllib.parse import urlparse

# A gate computes the courtesy wait for one (state_key, interval_s) request and
# RETURNS the number of seconds the *caller* should sleep — it must NOT sleep
# itself. This keeps the (single-container) Modal gate doing only microsecond
# bookkeeping so one slow host/key never blocks another (no head-of-line
# blocking) and the gate is never a throughput chokepoint. See
# ``modal/deep_dive_app.py::rate_limit_gate``.
ExternalRateLimitGate = Callable[[str, float], float]

_EXTERNAL_GATE: ExternalRateLimitGate | None = None
_EXTERNAL_GATE_LOCK = Lock()


def set_external_rate_limit_gate(gate: ExternalRateLimitGate | None) -> None:
    """Install a process-local hook for cross-process rate limiting.

    ``RateLimiter`` is intentionally in-process by default. Modal fan-out needs
    one additional coordination layer so 100+ containers do not each obey a
    polite local limit while collectively overwhelming PubTator / Europe PMC /
    NCBI. The Modal app installs a hook that calls a single-container gate
    function; local scripts leave this unset.

    The ``state_key`` passed to the hook never contains raw API keys. Bucket
    labels such as ``api_key:<secret>`` are hashed before they leave the
    process.
    """

    global _EXTERNAL_GATE
    with _EXTERNAL_GATE_LOCK:
        _EXTERNAL_GATE = gate


def _external_state_key(host: str, bucket: str | None) -> str:
    if not bucket:
        return host
    digest = hashlib.sha256(bucket.encode("utf-8")).hexdigest()[:24]
    return f"{host}\0bucket:{digest}"


def reserve_slot(
    table: dict[str, float],
    state_key: str,
    interval_s: float,
    *,
    now: float,
    max_wait_s: float | None = None,
) -> float:
    """Reserve the next courtesy slot for ``state_key``; return seconds to wait.

    Pure given ``(table, now)`` — it only reads/writes ``table[state_key]``, so
    it is directly unit-testable and is shared by both the in-process
    :class:`RateLimiter` and the cross-process Modal gate
    (``modal/deep_dive_app.py``) so the two paths can't diverge.

    Each key is an independent schedule line: the first call for a key waits 0,
    and N back-to-back calls get waits ``0, interval, 2·interval, …``. Different
    keys never interact. **The caller sleeps the returned duration itself** —
    never hold a lock across that sleep (that is the head-of-line-blocking bug
    this design removes).

    ``max_wait_s`` bounds both the returned wait and how far ahead the slot is
    reserved, so pathological contention — hundreds of queued reservations on a
    ~1 qps host, compounded by phantom slots left by crashed/retried workers —
    degrades to a brief over-rate instead of an unbounded queue that could blow
    a gene's wall-clock timeout. Non-positive intervals return 0 immediately.
    """
    if interval_s <= 0:
        return 0.0
    # First call for a key (prev defaults to now-interval) ⇒ no wait.
    prev = table.get(state_key, now - interval_s)
    scheduled = max(now, prev + interval_s)
    wait_for = scheduled - now
    if max_wait_s is not None and wait_for > max_wait_s:
        # Cap the reservation horizon, not just the returned wait — otherwise
        # the slot stays booked far in the future and every later caller piles
        # on behind it. Capping both degrades gracefully to a slight over-rate.
        scheduled = now + max_wait_s
        wait_for = max_wait_s
    table[state_key] = scheduled
    return wait_for


class RateLimiter:
    """Thread-safe per-host minimum-interval limiter.

    ``intervals_ms`` keys are bare hostnames (e.g. ``"eutils.ncbi.nlm.nih.gov"``).
    Hosts not in the table pass through with no delay.
    """

    def __init__(self, intervals_ms: dict[str, float]):
        self._intervals_ms = dict(intervals_ms)
        self._last_call: dict[str, float] = {}
        self._lock = Lock()

    def wait(
        self,
        url: str,
        min_interval_ms: float = 0.0,
        *,
        bucket: str | None = None,
        interval_ms: float | None = None,
    ) -> None:
        """Block until ``min_interval_ms`` (or the per-host cap, whichever is
        larger) has elapsed since the last call to this host.

        ``min_interval_ms`` lets a caller impose a courtesy floor on hosts not
        in the table — used by the PDF-download path to avoid hammering
        publisher servers that have no configured per-host cap.

        ``bucket`` splits the throttle state within a host. NCBI E-utilities
        rate-limits keyed requests per API key rather than per IP, so the HTTP
        client uses one bucket per ``api_key``. ``interval_ms`` lets that
        caller override the unauthenticated host interval with the keyed limit.
        """
        host = urlparse(url).netloc
        base_interval_ms = (
            self._intervals_ms.get(host, 0.0) if interval_ms is None else interval_ms
        )
        interval_s = max(base_interval_ms, min_interval_ms) / 1000.0
        if interval_s <= 0:
            return
        with _EXTERNAL_GATE_LOCK:
            gate = _EXTERNAL_GATE
        if gate is not None:
            # The gate reserves the next slot and returns how long to wait; we
            # sleep here in the worker process, not inside the gate container.
            wait_for = gate(_external_state_key(host, bucket), interval_s)
            if wait_for and wait_for > 0:
                time.sleep(wait_for)
            return
        state_key = f"{host}\0{bucket}" if bucket else host
        # Reserve the slot under the lock, then sleep *outside* it: holding the
        # lock across the sleep would serialize unrelated hosts/buckets in this
        # process (head-of-line blocking) — the same flaw the Modal gate fixes.
        with self._lock:
            wait_for = reserve_slot(
                self._last_call, state_key, interval_s, now=time.monotonic()
            )
        if wait_for > 0:
            time.sleep(wait_for)


def default_limiter() -> RateLimiter:
    """Default per-host caps for the upstreams gene_lookup uses today.

    NCBI's 10 qps with API key is the only documented hard cap; everything else
    is a courteous self-throttle. The OA-recovery hosts (Unpaywall, DataCite,
    Crossref Labs) were previously absent from this table, so under Modal
    fan-out they were hit at full concurrency (``interval=0``). They ask for
    polite, identifiable clients rather than publishing a hard qps, so we keep
    them at a conservative ~1-2 qps; a brief OA lookup per paper is not the
    sweep's bottleneck.
    """

    return RateLimiter(
        {
            "eutils.ncbi.nlm.nih.gov": 350,  # no key: <3 qps; keyed calls override to 110ms/key
            "www.ncbi.nlm.nih.gov": 350,  # PubTator3 asks clients to stay under 3 qps
            "rest.uniprot.org": 200,
            "rest.genenames.org": 200,
            "api.platform.opentargets.org": 250,
            "www.ebi.ac.uk": 130,  # Europe PMC; ~7-8 qps courtesy ceiling
            "api.unpaywall.org": 600,  # polite; daily-cap service, no hard qps published
            "api.datacite.org": 1000,  # public REST API — keep to ~1 qps to be courteous
            "api.labs.crossref.org": 1000,  # Retraction Watch feed host (Crossref Labs)
        }
    )
