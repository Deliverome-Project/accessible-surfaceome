"""Version-bump guardrail for schemas and prompts.

Pins a content fingerprint of each versioned artifact to its declared
version. The committed golden lives at ``tests/version_fingerprints.json``;
``tests/test_version_fingerprints.py`` asserts the current artifacts still
match it, and ``scripts/update_version_fingerprints.py`` regenerates it but
*refuses to record a new fingerprint under an unchanged version* — which is
what forces the bump.

Tracked artifacts:
  * ``SurfaceomeRecord`` / ``TriageRecord`` — the shipped record schemas,
    fingerprinted via ``model_json_schema()`` and pinned to their
    ``schema_version``.
  * ``prompt_corpus`` — every ``agents/*/prompts/*.md`` prompt, pinned to
    :data:`PROMPT_CORPUS_VERSION` (one global version per the chosen
    granularity).

Why this exists: ``SurfaceomeRecord`` was reworked repeatedly while
``schema_version`` stayed at ``1.1.0``, so records (and the viewer's
freshness check) silently believed they were current. The guardrail makes
that class of drift a failing test instead.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from accessible_surfaceome.tools._shared.models import (
    SurfaceomeRecord,
    TriageRecord,
)

# Bump this whenever any agents/*/prompts/*.md file changes, then run
# scripts/update_version_fingerprints.py. One global version covers the whole
# prompt corpus (the chosen granularity).
PROMPT_CORPUS_VERSION = "2.24.0"


def _repo_root() -> Path:
    # src/accessible_surfaceome/_version_guard.py → parents[2] == repo root.
    return Path(__file__).resolve().parents[2]


GOLDEN_PATH = _repo_root() / "tests" / "version_fingerprints.json"


def schema_fingerprint(model: type[BaseModel]) -> str:
    """sha256 of a model's JSON schema, serialized canonically so the hash is
    stable across runs (key order independent)."""
    canonical = json.dumps(
        model.model_json_schema(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prompt_files() -> list[Path]:
    """Every agent prompt markdown file, sorted by repo-relative path for a
    deterministic corpus order."""
    root = _repo_root()
    agents = root / "src" / "accessible_surfaceome" / "agents"
    return sorted(
        agents.glob("*/prompts/*.md"), key=lambda p: str(p.relative_to(root))
    )


def prompt_corpus_fingerprint() -> str:
    """sha256 over the (relative-path, bytes) of every prompt file. Renames
    and content edits both change the hash."""
    root = _repo_root()
    h = hashlib.sha256()
    for path in prompt_files():
        h.update(str(path.relative_to(root)).encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def current_fingerprints() -> dict[str, dict[str, str]]:
    """The live ``{artifact: {version, fingerprint}}`` map computed from the
    code + prompts as they currently are."""

    def _ver(model: type[BaseModel]) -> str:
        return str(model.model_fields["schema_version"].default)

    return {
        "SurfaceomeRecord": {
            "version": _ver(SurfaceomeRecord),
            "fingerprint": schema_fingerprint(SurfaceomeRecord),
        },
        "TriageRecord": {
            "version": _ver(TriageRecord),
            "fingerprint": schema_fingerprint(TriageRecord),
        },
        "prompt_corpus": {
            "version": PROMPT_CORPUS_VERSION,
            "fingerprint": prompt_corpus_fingerprint(),
        },
    }


def load_golden() -> dict[str, dict[str, str]]:
    """The committed golden, or ``{}`` if it doesn't exist yet."""
    if not GOLDEN_PATH.exists():
        return {}
    return json.loads(GOLDEN_PATH.read_text())


def reconcile(
    golden: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Compute the golden that *should* be committed given ``current``,
    plus any errors that block recording.

    Rules per artifact:
      * absent from golden → add it (new artifact, no error).
      * fingerprint changed AND version unchanged → ERROR, leave entry as-is
        (this is the bump-forcing rule).
      * fingerprint changed AND version changed → record the new pair.
      * fingerprint unchanged, version changed → record the new version
        (a deliberate re-version with identical content; allowed).
      * fully unchanged → keep.
    """
    new_golden: dict[str, dict[str, str]] = {k: dict(v) for k, v in golden.items()}
    errors: list[str] = []
    for name, cur in current.items():
        prev = golden.get(name)
        if prev is None:
            new_golden[name] = dict(cur)
            continue
        fp_changed = prev.get("fingerprint") != cur["fingerprint"]
        ver_changed = prev.get("version") != cur["version"]
        if fp_changed and not ver_changed:
            errors.append(
                f"{name} changed but its version is still {cur['version']!r}. "
                f"Bump {name}'s version, then rerun "
                f"scripts/update_version_fingerprints.py."
            )
            # leave new_golden[name] as the old (refused) entry
            continue
        if fp_changed or ver_changed:
            new_golden[name] = dict(cur)
    return new_golden, errors


def write_golden(golden: dict[str, dict[str, str]]) -> None:
    GOLDEN_PATH.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")


__all__ = [
    "PROMPT_CORPUS_VERSION",
    "GOLDEN_PATH",
    "schema_fingerprint",
    "prompt_files",
    "prompt_corpus_fingerprint",
    "current_fingerprints",
    "load_golden",
    "reconcile",
    "write_golden",
]
