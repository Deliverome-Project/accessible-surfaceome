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

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        interval_s = self._intervals_ms.get(host, 0.0) / 1000.0
        if interval_s <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last_call.get(host, 0.0)
            wait_for = interval_s - (now - last)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_call[host] = time.monotonic()


def default_limiter() -> RateLimiter:
    """Default per-host caps for the upstreams gene_lookup uses today.

    NCBI's 10 qps with API key is the only documented hard cap; everything else
    is a courteous self-throttle.
    """

    return RateLimiter(
        {
            "eutils.ncbi.nlm.nih.gov": 110,  # ~9 qps, leaves headroom under 10 qps cap
            "rest.uniprot.org": 200,
            "rest.genenames.org": 200,
            "api.platform.opentargets.org": 250,
            "www.ebi.ac.uk": 130,  # Europe PMC; ~7-8 qps courtesy ceiling
        }
    )
