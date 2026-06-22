"""Per-host minimum-interval throttle.

The agent calls custom tools synchronously and sequentially, but a single
``resolve`` fans out to four upstreams concurrently from a thread pool. We need
to ensure that bursts within one fan-out (and across consecutive gene calls in a
batch) respect upstream qps caps — particularly NCBI's 10 qps with API key.
"""

from __future__ import annotations

import time
from threading import Lock
from urllib.parse import urlparse


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
        state_key = f"{host}\0{bucket}" if bucket else host
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(state_key, 0.0)
            wait_for = interval_s - (now - last)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call[state_key] = time.monotonic()


def default_limiter() -> RateLimiter:
    """Default per-host caps for the upstreams gene_lookup uses today.

    NCBI's 10 qps with API key is the only documented hard cap; everything else
    is a courteous self-throttle.
    """

    return RateLimiter(
        {
            "eutils.ncbi.nlm.nih.gov": 350,  # no key: <3 qps; keyed calls override to 110ms/key
            "www.ncbi.nlm.nih.gov": 350,  # PubTator3 asks clients to stay under 3 qps
            "rest.uniprot.org": 200,
            "rest.genenames.org": 200,
            "api.platform.opentargets.org": 250,
            "www.ebi.ac.uk": 130,  # Europe PMC; ~7-8 qps courtesy ceiling
        }
    )
