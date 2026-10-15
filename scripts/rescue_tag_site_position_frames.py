"""Re-adjudicate published tag sites whose cited position was read in a FOREIGN
proteoform frame, and upgrade the ones a frame genuinely proves.

A literature site whose quote does not NAME its junction is downgraded to
``position_evidence='inferred'`` by ``enforce_position_claims``. That check
reads the canonical sequence only, so a paper numbering in the mature protein or
an isoform fails it — and ``residue_mentions``' own docstring says as much,
deferring the recovery to the synthesis REPL. 198 published sites sit at
``inferred`` today. This script asks, for each of them, whether an alternate
frame lets the quote name the junction after all, under the guards in
:mod:`accessible_surfaceome.agents.tag_site.frames`.

It NEVER MOVES A POSITION. The junction, the flanking residues and the
extracellular call are all left exactly as published; the only thing that
changes is the strength of the claim attached to them, plus the new
``position_frame`` column recording which frame proved it. A site whose stored
flanks no longer agree with the sequence is skipped rather than upgraded — that
record is internally inconsistent and upgrading it would launder the
inconsistency into a stronger claim.

Dry run by default. ``--execute`` writes, verifies each row by reading it back,
and purges the affected ``/v1/tag-sites/{SYMBOL}`` cache surfaces — a D1 write
whose cache is not purged is the drift this repo keeps re-learning.

    uv run python scripts/rescue_tag_site_position_frames.py
    uv run python scripts/rescue_tag_site_position_frames.py --genes GABRA4,GABRP
    uv run python scripts/rescue_tag_site_position_frames.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from typing import Any

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.frames import (  # noqa: E402
    Frame,
    resolve,
)
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.cloud.surface_annotation import purge_paths  # noqa: E402

log = logging.getLogger("rescue_frames")

#: D1 caps bound parameters per query at 100.
_CHUNK = 60


def _chunks(items: list[Any], size: int = _CHUNK):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_sites(d1: D1Client, *, genes: list[str] | None) -> list[dict[str, Any]]:
    """Published literature sites with a junction and an unproven position."""
    sql = (
        "SELECT gene_symbol, uniprot_acc, site_id, site_kind, insert_after_residue, "
        "residue_before, residue_after, extracellular, position_evidence, sources_json "
        "FROM tag_site_public WHERE provenance = 'literature_retrieved' "
        "AND insert_after_residue IS NOT NULL "
        "AND (position_evidence = 'inferred' OR position_evidence IS NULL)"
    )
    if not genes:
        return d1.query(sql + ";", [])
    out: list[dict[str, Any]] = []
    for chunk in _chunks(genes):
        marks = ", ".join(["?"] * len(chunk))
        out += d1.query(f"{sql} AND gene_symbol IN ({marks});", chunk)
    return out


def build_frames(d1: D1Client, accs: list[str]) -> dict[str, list[Frame]]:
    """Per accession: the canonical sequence as the REFERENCE frame, plus the
    mature frame (when UniProt annotates a signal peptide) and every isoform.

    The ortholog frame is deliberately absent, and not by choice: public D1's
    ``compara_ortholog.ortholog_uniprot_acc`` is NULL in all 21,549 rows, so
    there is no join key from a human accession to the 12,222 mouse / 14,118
    cyno sequences that DO sit in ``topology_public``. A citation numbering in a
    rat or mouse frame therefore cannot be resolved at all today — which the
    guards handle correctly by refusing to promote some other frame in its
    place, and which is worth fixing on its own.
    """
    frames: dict[str, list[Frame]] = defaultdict(list)
    for chunk in _chunks(accs):
        marks = ", ".join(["?"] * len(chunk))
        rows = d1.query(
            f"SELECT uniprot_acc, uniprot_acc_full, is_canonical, sequence, "
            f"signal_peptide_length FROM topology_public "
            f"WHERE uniprot_acc IN ({marks}) "
            f"AND cohort IN ('human_canonical', 'human_isoforms');",
            chunk,
        )
        for row in rows:
            acc, seq = row["uniprot_acc"], row["sequence"]
            if not seq:
                continue
            if row["is_canonical"]:
                frames[acc].append(Frame(label="reference", sequence=seq, offset=0))
                sp = row["signal_peptide_length"] or 0
                if sp:
                    frames[acc].append(
                        Frame(label="mature", sequence=seq[sp:], offset=sp)
                    )
            else:
                frames[acc].append(
                    Frame(
                        label=f"isoform:{row['uniprot_acc_full']}",
                        sequence=seq,
                        offset=None,
                    )
                )
    return frames


def first_quote(sources_json: str | None) -> str:
    for src in json.loads(sources_json or "[]"):
        if isinstance(src, dict) and src.get("claim"):
            return str(src["claim"])
    return ""


def flanks_still_agree(site: dict[str, Any], reference: str) -> bool:
    """The stored ``residue_before`` / ``residue_after`` match the reference at
    the stored junction.

    This is ``geometry.check_residues``' invariant, re-asserted at write time.
    A record that fails it disagrees with its own sequence, so the honest move
    is to leave it alone and report it, not to hand it a stronger claim.
    """
    n = site["insert_after_residue"]
    if not 1 <= n <= len(reference):
        return False
    before, after = site.get("residue_before"), site.get("residue_after")
    if before and reference[n - 1].upper() != before.upper():
        return False
    if after and n < len(reference) and reference[n].upper() != after.upper():
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--genes", default="", help="comma-separated scope")
    ap.add_argument("--execute", action="store_true", help="write to public D1")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    genes = [g.strip().upper() for g in args.genes.split(",") if g.strip()]
    with D1Client.public() as d1:
        sites = load_sites(d1, genes=genes)
        log.info("%d published literature site(s) with an unproven position", len(sites))
        if not sites:
            return 0
        accs = sorted({s["uniprot_acc"] for s in sites if s.get("uniprot_acc")})
        frames = build_frames(d1, accs)
        log.info(
            "frames built for %d/%d accessions (mature available for %d, isoforms for %d)",
            len(frames), len(accs),
            sum(1 for v in frames.values() if any(f.label == "mature" for f in v)),
            sum(1 for v in frames.values() if any(f.family == "isoform" for f in v)),
        )

        upgrades: list[tuple[dict[str, Any], Any]] = []
        skipped_inconsistent: list[dict[str, Any]] = []
        blocked: list[tuple[dict[str, Any], Any]] = []

        for site in sites:
            frame_list = frames.get(site["uniprot_acc"]) or []
            reference = next(
                (f.sequence for f in frame_list if f.label == "reference"), None
            )
            if not reference:
                continue
            quote = first_quote(site["sources_json"])
            if not quote:
                continue
            res = resolve(
                quote,
                frames=frame_list,
                reference_label="reference",
                target=site["insert_after_residue"],
            )
            # Only worth reporting when a frame actually FIT and was refused —
            # "the paper names a frame we lack, and here is the frame we
            # declined to promote in its place". A site where nothing matched
            # at all is not a blocked rescue, it is simply uncited, and listing
            # it as blocked implies we found something.
            refused_alternate = [
                h
                for h in res.hits
                if h.frame_label != "reference" and not h.confers_validation
            ]
            if res.blocked_by_unavailable_frame and refused_alternate:
                blocked.append((site, res))
                continue
            hit = res.validating_hit
            if hit is None or hit.frame_label == "reference":
                continue
            if not flanks_still_agree(site, reference):
                skipped_inconsistent.append(site)
                continue
            upgrades.append((site, hit))

        print("\n" + "=" * 78)
        print("FRAME RESCUE" + ("" if args.execute else "  [DRY RUN — nothing written]"))
        print("=" * 78)
        for site, hit in upgrades:
            print(
                f"  UPGRADE  {site['gene_symbol']:9s} {site['site_id']:36s} "
                f"junction {site['insert_after_residue']:5d}  "
                f"frame={hit.frame_label} (frame pos {hit.frame_position}, "
                f"named={hit.frame_named}, letter_tokens={hit.letter_confirmed_tokens})"
            )
        for site, res in blocked:
            print(
                f"  BLOCKED  {site['gene_symbol']:9s} {site['site_id']:36s} "
                f"cites frame {sorted(res.named_families)} which we do not hold; "
                f"cited positions {sorted(res.cited_positions)} — left at 'inferred'"
            )
        for site in skipped_inconsistent:
            print(
                f"  SKIPPED  {site['gene_symbol']:9s} {site['site_id']:36s} "
                f"stored flanks disagree with the sequence at its own junction"
            )
        print(
            f"\n  {len(upgrades)} upgradeable, {len(blocked)} blocked by an "
            f"unavailable frame, {len(skipped_inconsistent)} internally inconsistent"
        )

        if not args.execute or not upgrades:
            if upgrades:
                print("\n  re-run with --execute to write these.")
            return 0

        # Additive column; harmless when it already exists.
        cols = {c["name"] for c in d1.query("PRAGMA table_info(tag_site_public);", [])}
        if "position_frame" not in cols:
            d1.query("ALTER TABLE tag_site_public ADD COLUMN position_frame TEXT;", [])
            log.info("added tag_site_public.position_frame")

        written = 0
        for site, hit in upgrades:
            d1.query(
                "UPDATE tag_site_public SET position_evidence = 'validated', "
                "position_frame = ? WHERE uniprot_acc = ? AND site_id = ?;",
                [hit.frame_label, site["uniprot_acc"], site["site_id"]],
            )
            back = d1.query(
                "SELECT position_evidence, position_frame, insert_after_residue "
                "FROM tag_site_public WHERE uniprot_acc = ? AND site_id = ?;",
                [site["uniprot_acc"], site["site_id"]],
            )
            if not back:
                log.error("  %s: row vanished after update", site["site_id"])
                continue
            row = back[0]
            if (
                row["position_evidence"] != "validated"
                or row["position_frame"] != hit.frame_label
                or row["insert_after_residue"] != site["insert_after_residue"]
            ):
                log.error("  %s: read-back mismatch %r", site["site_id"], row)
                continue
            written += 1
        log.info("verified %d/%d row(s) written", written, len(upgrades))

        # A D1 write whose cache is not purged keeps serving the old shape for
        # up to the route's TTL, on an arbitrary subset of POPs.
        paths = sorted({f"/v1/tag-sites/{s['gene_symbol']}" for s, _ in upgrades})
        purge_paths(paths)
        log.info("purged %d tag-site cache surface(s)", len(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
