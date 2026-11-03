"""Lift the agent metadata back out of `rationale`, where it was concatenated.

``to_viewer_sites`` used to fold the agent-only fields into the rationale as a
trailing bracket:

    ... [validation: function_only; position: inferred; source: paper;
         cited_tag_residue: 594; entailment_verified: True]

so the viewer contract would not have to change. The cost landed on the reader:
raw field names, a Python ``True``, and an internal gate's verdict rendered as
prose in the middle of a scientific argument — with nothing the UI could turn
into structure, sort on, or filter by.

They are columns now. This recovers them for records already written, by
parsing the bracket the old code emitted and stripping it from the prose. Pure
string work on committed records; no re-run, no model calls.

    uv run python scripts/backfill_site_metadata_fields.py            # dry run
    uv run python scripts/backfill_site_metadata_fields.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "viewer/public/tag-sites"
log = logging.getLogger("backfill_fields")

#: The trailing block the old emitter appended, with nothing after it.
_BLOCK = re.compile(r"\s*\[(validation:[^\]]*)\]\s*$")
_BOOL = {"true": True, "false": False}


def split_rationale(text: str) -> tuple[str, dict]:
    """``(prose, fields)``. Unparseable text comes back unchanged with no fields."""
    m = _BLOCK.search(text or "")
    if not m:
        return text, {}
    fields: dict = {}
    for part in m.group(1).split(";"):
        if ":" not in part:
            continue
        key, _, val = part.partition(":")
        key, val = key.strip(), val.strip()
        if not val:
            continue
        if key == "validation":
            fields["validation_level"] = val
        elif key == "position":
            fields["position_evidence"] = val
        elif key == "source":
            fields["source_tier"] = val
        elif key == "cited_tag_residue":
            try:
                fields["cited_tag_residue"] = int(val)
            except ValueError:
                pass
        elif key in {"entailment_verified", "position_repaired"}:
            fields[key] = _BOOL.get(val.lower(), False)
        elif key == "quote_describes_no_insertion":
            # Stated only when the quote was NOT probative, so the field it maps
            # to is the inverse; absence means probative, which is the default.
            fields["quote_probative"] = not _BOOL.get(val.lower(), False)
    return _BLOCK.sub("", text).strip(), fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    files = touched = sites = 0
    for path in sorted(VIEWER_DIR.glob("*.json")):
        rec = json.loads(path.read_text())
        changed = False
        for s in rec.get("sites") or []:
            prose, fields = split_rationale(s.get("rationale") or "")
            if not fields:
                continue
            s["rationale"] = prose
            s.update(fields)
            s.setdefault("quote_probative", True)
            sites += 1
            changed = True
        files += 1
        if changed:
            touched += 1
            if args.execute:
                path.write_text(json.dumps(rec, indent=2, default=str))
    log.info(
        "records scanned %d, records changed %d, sites lifted %d", files, touched, sites
    )
    if not args.execute:
        log.info("dry run — nothing written (pass --execute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
