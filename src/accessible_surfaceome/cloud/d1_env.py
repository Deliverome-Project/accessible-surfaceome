"""D1 credential pre-flight + tiered enforcement.

Centralizes the "are CLOUDFLARE_* env vars set up correctly?" check that
:func:`accessible_surfaceome.cloud.surface_annotation._publish_dict` and
:func:`accessible_surfaceome.agents.surfaceome_v1.orchestrator._load_triage_record_from_d1`
previously duplicated inline.

The check has three failure modes:

* **All three vars missing** (``CLOUDFLARE_ACCOUNT_ID``,
  ``CLOUDFLARE_API_TOKEN``, ``CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID``) —
  legitimate fresh-checkout / CI / offline-dev. Returns ``None`` with a
  single startup line, no warning per call.
* **Partial creds set** (some vars populated, others empty) — this is a
  misconfig: e.g. the worktree's ``.env`` symlink dangled, or a stray
  shell ``export CLOUDFLARE_API_TOKEN=`` left an empty token. Returns
  ``None`` with a *loud* warning naming the missing var(s), so the
  operator notices BEFORE annotate burns $3-5 on a gene whose
  ``triage_signal`` then silently lands as ``unknown``. This was the
  June-2026 bug — partial creds in the youthful-cannon worktree shipped
  6 records with ``triage_signal=unknown`` despite the triage rows
  existing in D1.
* **Hard-fail mode** (``ACCESSIBLE_SURFACEOME_REQUIRE_D1=1``) — promotes
  any miss-or-partial state to a raised :class:`D1AuthError`. Production
  sweeps set this so a credential drop on a 19k-gene sweep can't silently
  accumulate ``unknown`` triages.

The flag is read fresh from the environment on every call (no module-level
caching) so tests that ``monkeypatch.setenv`` see the change.
"""

from __future__ import annotations

import logging
import os

from accessible_surfaceome.cloud.d1_client import D1Config
from accessible_surfaceome.env import load_env

logger = logging.getLogger(__name__)

REQUIRE_D1_ENV_VAR = "ACCESSIBLE_SURFACEOME_REQUIRE_D1"

_D1_ENV_VARS: tuple[str, str, str] = (
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID",
)


class D1AuthError(RuntimeError):
    """Raised when D1 creds are missing/partial AND ``REQUIRE_D1`` is set.

    Distinct from generic ``RuntimeError`` so callers (or test assertions)
    can tell a credential failure apart from a transport / D1-query
    failure. Tracks the missing var names on ``.missing`` for log messages.
    """

    def __init__(self, *, operation: str, missing: list[str], symbol: str | None = None):
        self.operation = operation
        self.missing = list(missing)
        self.symbol = symbol
        target = f" for {symbol}" if symbol else ""
        super().__init__(
            f"{REQUIRE_D1_ENV_VAR}=1 but D1 creds are missing for {operation}{target}: "
            f"{', '.join(missing)}"
        )


def _require_d1() -> bool:
    """``True`` when ``ACCESSIBLE_SURFACEOME_REQUIRE_D1`` is set to a truthy value.

    Treats ``1``, ``true``, ``yes``, ``on`` (case-insensitive) as truthy.
    Anything else — including unset, empty string, and ``0`` — is falsy.
    """
    raw = os.environ.get(REQUIRE_D1_ENV_VAR, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def public_d1_config_or_warn(
    *, operation: str, symbol: str | None = None
) -> D1Config | None:
    """Build a public-DB :class:`D1Config` from env, or return ``None``.

    The single canonical "do we have D1 creds?" entry point. Use at every
    call site that's about to hit public D1 — :func:`publish_record`,
    :func:`_load_triage_record_from_d1`, future Worker-mirror tools.

    Behaviour:

    * All three vars populated → returns a configured :class:`D1Config`.
    * All three vars empty (legitimate skip) → returns ``None``, logs an
      info-level line so the run trace shows D1 was skipped intentionally.
    * Partial state (1-2 of 3 set) → returns ``None``, logs a *warning*
      naming every missing var, AND records the gap as a misconfig in the
      run log.
    * Any miss-or-partial state under ``REQUIRE_D1=1`` → raises
      :class:`D1AuthError`.

    Args:
        operation: Human-readable name for the operation that needed D1.
            Goes into log messages and the exception (``"publish_record"``,
            ``"triage D1 fallback"``, etc).
        symbol: Optional gene symbol to include in the log message. Helps
            when sweeping — "missing for SLC7A5" beats a context-free warn.

    Returns:
        :class:`D1Config` when env is healthy, else ``None``.

    Raises:
        D1AuthError: When ``REQUIRE_D1=1`` and env is missing/partial.
    """
    load_env()
    values = {var: os.environ.get(var, "").strip() for var in _D1_ENV_VARS}
    missing = [var for var, val in values.items() if not val]

    if not missing:
        return D1Config(
            account_id=values["CLOUDFLARE_ACCOUNT_ID"],
            database_id=values["CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID"],
            api_token=values["CLOUDFLARE_API_TOKEN"],
        )

    if _require_d1():
        raise D1AuthError(operation=operation, missing=missing, symbol=symbol)

    target = f" for {symbol}" if symbol else ""
    if len(missing) == len(_D1_ENV_VARS):
        # All three missing — fresh-checkout / CI / offline. Legitimate.
        logger.info(
            "no D1 public credentials in env; skipping %s%s",
            operation,
            target,
        )
    else:
        # Partial state — misconfig. This is the June-2026 bug shape.
        logger.warning(
            "D1 misconfig: partial credentials set, skipping %s%s. "
            "Missing: %s. Either set all of %s, or unset them all to "
            "explicitly skip D1. To turn this warning into a hard fail "
            "(prod-sweep mode), set %s=1.",
            operation,
            target,
            ", ".join(missing),
            ", ".join(_D1_ENV_VARS),
            REQUIRE_D1_ENV_VAR,
        )
    return None
