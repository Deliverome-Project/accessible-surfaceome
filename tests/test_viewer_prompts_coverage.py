"""Bidirectional drift guard for the viewer's agent-prompts page.

Failure mode this guards against
================================

``viewer/app/prompts/page.tsx`` reads every prompt file in its
``PROMPT_GROUPS`` array with ``fs.readFileSync`` at SSG build time. Two
drift directions silently break the page:

1. **Stale ``rel:`` entry** — the page array references a prompt path
   that no longer exists (e.g. ``plan_trim_select/prompts/trim_system.md``
   after the A1/A2 split retired the joint prompt). ``loadPrompt``
   swallows the ``ENOENT`` and the card silently disappears; the reader
   has no signal that the intended prompt is missing.

2. **Orphan prompt file** — a new prompt is added under
   ``src/accessible_surfaceome/agents/**/prompts/*.md`` but never wired
   into ``PROMPT_GROUPS`` (e.g. ``risks_builder_system.md``,
   ``biological_context_grade_builder_system.md``). The agent runs with
   it, but the docs page hides it — readers think the catalog they see
   is exhaustive when it isn't.

Why match the markdown drift tests' shape
=========================================

``tests/test_d1_records_schema_drift.py`` enforces the
``viewer/public/data/surfaceome/*.json`` ↔ ``*.md`` mapping with an
explicit ``KNOWN_NO_MARKDOWN_EXPORT`` allowlist and a check that
allowlist entries don't go stale. This file uses the same pattern for
``agents/**/prompts/*.md`` ↔ ``PROMPT_GROUPS[*].rel``: every on-disk
prompt must be wired into the page or live in ``ALLOWED_NO_VIEWER_DISPLAY``
with a tracking note.

Why parse ``page.tsx`` with a regex
===================================

The viewer is a Next.js TypeScript project — pytest cannot import its
modules. The page is a flat constant array of object literals, and the
only thing the test cares about is the set of ``rel:`` string values.
A single regex over the file text is the right size for the job and
mirrors how the markdown-drift guard reads ``viewer/scripts/...mjs``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repo root is two levels up from ``tests/`` — same heuristic as
# ``test_d1_records_schema_drift.py`` and ``scripts/audit/check_viewer_types_sync.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_AGENTS_DIR = _REPO_ROOT / "src" / "accessible_surfaceome" / "agents"
_PAGE_TSX = _REPO_ROOT / "viewer" / "app" / "prompts" / "page.tsx"

# Allowlist for prompt files that intentionally aren't displayed on
# ``/prompts``. Empty today — every prompt under
# ``agents/**/prompts/*.md`` is currently part of the live pipeline and
# belongs on the page. If a prompt is added that genuinely shouldn't
# be surfaced (e.g. a deprecated variant kept around for reproducibility),
# add its repo-rooted path here with a tracking note explaining why.
ALLOWED_NO_VIEWER_DISPLAY: frozenset[str] = frozenset()

# Match each `rel: "src/accessible_surfaceome/..."` literal in page.tsx.
# Captures the quoted path. Tolerates leading whitespace and either
# single or double quotes (page.tsx uses doubles today, but a future
# Prettier config could flip them).
_REL_RE = re.compile(
    r"""rel:\s*(["'])(src/accessible_surfaceome/agents/[^"']+\.md)\1""",
)


def _on_disk_prompt_paths() -> set[str]:
    """Return the set of repo-rooted (POSIX) paths of every
    ``agents/**/prompts/*.md`` file currently committed to the tree."""
    paths: set[str] = set()
    for md in _AGENTS_DIR.glob("**/prompts/*.md"):
        rel = md.relative_to(_REPO_ROOT).as_posix()
        paths.add(rel)
    return paths


def _rel_entries_in_page_tsx() -> set[str]:
    """Return the set of ``rel:`` values declared in ``PROMPT_GROUPS``."""
    if not _PAGE_TSX.is_file():
        pytest.skip(
            f"viewer prompts page not found at {_PAGE_TSX} — the viewer "
            "directory may have moved. Update _PAGE_TSX in this test."
        )
    text = _PAGE_TSX.read_text(encoding="utf-8")
    return {m.group(2) for m in _REL_RE.finditer(text)}


def test_every_on_disk_prompt_is_wired_into_viewer_page() -> None:
    """Every ``agents/**/prompts/*.md`` file must have a ``rel:`` entry
    in ``viewer/app/prompts/page.tsx``'s ``PROMPT_GROUPS`` array, or
    live in ``ALLOWED_NO_VIEWER_DISPLAY`` with a tracking note.

    Catches the orphan-prompt direction of the drift (new prompt added,
    docs page never updated).
    """
    on_disk = _on_disk_prompt_paths()
    if not on_disk:
        pytest.skip(
            f"No prompt files under {_AGENTS_DIR} — agents directory may "
            "have moved. Update _AGENTS_DIR in this test."
        )
    wired = _rel_entries_in_page_tsx()
    unwired = on_disk - wired - ALLOWED_NO_VIEWER_DISPLAY

    if unwired:
        lines = [
            f"{len(unwired)} prompt file(s) exist on disk but are NOT wired "
            "into viewer/app/prompts/page.tsx's PROMPT_GROUPS array — the "
            "/prompts page will silently omit them:",
            "",
        ]
        for rel in sorted(unwired):
            lines.append(f"  - {rel}")
        lines.append("")
        lines.append(
            "Either add a {id, label, rel, blurb} entry to the appropriate "
            "group in viewer/app/prompts/page.tsx, OR add the path to "
            "ALLOWED_NO_VIEWER_DISPLAY in this test with a tracking note "
            "explaining why the prompt is intentionally hidden."
        )
        pytest.fail("\n".join(lines))


def test_every_viewer_rel_entry_points_at_real_file() -> None:
    """Every ``rel:`` value in ``PROMPT_GROUPS`` must resolve to an
    on-disk prompt file.

    Catches the broken-reference direction of the drift (prompt retired
    or renamed, page.tsx never updated).
    """
    on_disk = _on_disk_prompt_paths()
    wired = _rel_entries_in_page_tsx()
    broken = wired - on_disk

    if broken:
        lines = [
            f"{len(broken)} rel: entry/entries in viewer/app/prompts/page.tsx "
            "point at file(s) that don't exist on disk — the /prompts page's "
            "loadPrompt swallows ENOENT and silently drops the card:",
            "",
        ]
        for rel in sorted(broken):
            lines.append(f"  - {rel}")
        lines.append("")
        lines.append(
            "Either restore the file, OR update viewer/app/prompts/page.tsx "
            "to remove / repoint the entry (and the cross-references in the "
            "group description + the index-suppression comment)."
        )
        pytest.fail("\n".join(lines))


def test_allowed_no_viewer_display_entries_are_real_paths() -> None:
    """Guard against ``ALLOWED_NO_VIEWER_DISPLAY`` going stale: every
    allowlist entry must still resolve to an on-disk prompt file.

    If a prompt is retired, the allowlist entry has to go too (otherwise
    the allowlist quietly rots and starts protecting nothing)."""
    if not ALLOWED_NO_VIEWER_DISPLAY:
        return  # Nothing to check.
    on_disk = _on_disk_prompt_paths()
    stale = ALLOWED_NO_VIEWER_DISPLAY - on_disk
    if stale:
        lines = [
            "ALLOWED_NO_VIEWER_DISPLAY has entries that no longer exist on "
            "disk (the prompt was retired but the allowlist wasn't pruned):",
            "",
        ]
        for rel in sorted(stale):
            lines.append(f"  - {rel}")
        lines.append("")
        lines.append("Remove these entries from ALLOWED_NO_VIEWER_DISPLAY.")
        pytest.fail("\n".join(lines))
