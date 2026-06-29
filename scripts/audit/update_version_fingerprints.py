"""Regenerate ``tests/version_fingerprints.json`` after an intentional schema
or prompt version bump.

Run this when ``tests/test_version_fingerprints.py`` fails because you changed
a record schema or a prompt on purpose:

    uv run python scripts/audit/update_version_fingerprints.py          # write
    uv run python scripts/audit/update_version_fingerprints.py --check  # verify only

It **refuses** to record a new fingerprint for any artifact whose content
changed while its version stayed the same — bump the version first
(``SurfaceomeRecord.schema_version`` / ``TriageRecord.schema_version`` /
``_version_guard.PROMPT_CORPUS_VERSION``). That refusal is what makes the
version bump non-skippable.
"""

from __future__ import annotations

import sys

from accessible_surfaceome import _version_guard as vg


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    current = vg.current_fingerprints()
    golden = vg.load_golden()
    new_golden, errors = vg.reconcile(golden, current)

    if errors:
        print("Refusing to update version fingerprints:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if new_golden == golden:
        print("version fingerprints already up to date.")
        return 0

    if check_only:
        print(
            "version fingerprints are STALE — run without --check to write.",
            file=sys.stderr,
        )
        return 1

    vg.write_golden(new_golden)
    print(f"wrote {vg.GOLDEN_PATH.relative_to(vg.GOLDEN_PATH.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
