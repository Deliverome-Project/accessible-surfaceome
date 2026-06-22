"""Load environment variables from the repo's ``.env`` at CLI entry.

Why this exists: the CLI and the orchestrator both need access to secrets
(``ANTHROPIC_API_KEY``, optional ``NCBI_API_KEYS`` / ``NCBI_API_KEY``)
without baking them into the shell profile. We load ``.env`` from the repo root once, at the top of
``main()`` — never at module import time, per the project's coding-style rule
("Imports at the top; no side effects on import").

Precedence rules:

* Shell-set variables with a real value are not overridden. CI,
  ``export ANTHROPIC_API_KEY=...``, and ``direnv`` always win over ``.env``.
* Shell-set variables with an *empty* value are treated as unset and filled
  in from ``.env``. Empty values almost always come from credential scrubbers
  (Claude Code subshells, sandbox harnesses) rather than intentional user
  overrides; respecting them blocks ``.env`` from doing its job.
* The .env path resolves in this order: explicit ``path=`` argument, then
  ``REPO_ROOT/.env`` (which itself may be a symlink — see
  ``scripts/bootstrap-worktree.sh`` and the ``ACCESSIBLE_SURFACEOME_ENV_SOURCE``
  convention).
* A missing .env is not an error — many invocations don't need secrets.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

from .paths import REPO_ROOT


def load_env(path: Path | None = None) -> Path | None:
    """Load .env into ``os.environ`` if present. Returns the path that was loaded, or None."""

    target = path or (REPO_ROOT / ".env")
    if not target.exists():
        return None
    # Hand-rolled merge instead of dotenv.load_dotenv so we can treat empty
    # shell-env values as unset. python-dotenv has no built-in for that.
    for key, value in dotenv_values(target).items():
        if value is None:
            continue
        existing = os.environ.get(key)
        if existing:  # non-empty shell value wins
            continue
        os.environ[key] = value
    return target
