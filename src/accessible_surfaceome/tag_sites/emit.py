"""Merge-writer for the viewer's per-gene tag-sites JSON.

Single writer that both the deterministic pipeline and (later) the literature
agent call, so their sites coexist in one ``viewer/public/tag-sites/{SYMBOL}.json``
without clobbering each other. Sites are keyed by ``site_id`` — a re-run updates
its own rows and leaves the others intact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def emit_tag_sites_json(
    gene_symbol: str,
    uniprot_acc: str,
    sites: list[dict[str, Any]],
    *,
    out_dir: str | Path,
    isoform_pins: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge ``sites`` (by ``site_id``, new wins) into ``{out_dir}/{SYMBOL}.json``
    and write it back. ``isoform_pins`` (per-isoform deterministic pins, see
    ``tag_sites.isoform``) are merged the same way by their own ``site_id`` and
    stored under ``isoform_pins``. Returns the written ``TaggedSitesFile`` dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{gene_symbol}.json"

    by_id: dict[str, dict[str, Any]] = {}
    pins_by_id: dict[str, dict[str, Any]] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            for s in existing.get("sites", []):
                if isinstance(s, dict) and "site_id" in s:
                    by_id[s["site_id"]] = s
            for pin in existing.get("isoform_pins", []):
                if isinstance(pin, dict) and "site_id" in pin:
                    pins_by_id[pin["site_id"]] = pin
        except (json.JSONDecodeError, OSError):
            pass  # corrupt/unreadable existing file → start fresh

    for s in sites:
        by_id[s["site_id"]] = s
    for pin in isoform_pins or []:
        pins_by_id[pin["site_id"]] = pin

    merged = sorted(by_id.values(), key=lambda s: s["site_id"])
    merged_pins = sorted(pins_by_id.values(), key=lambda p: p["site_id"])
    payload = {
        "has_data": len(merged) > 0,
        "gene_symbol": gene_symbol,
        "uniprot_acc": uniprot_acc,
        "sites": merged,
        "isoform_pins": merged_pins,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
