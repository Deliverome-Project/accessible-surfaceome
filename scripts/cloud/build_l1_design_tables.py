#!/usr/bin/env python
"""Build the L1 design overlay (tag sites, folded models, contact sites) for public D1.

Requested by Becca Carlson, 2026-11-11 ("update the viewer with suggested tag sites as
well as with folded versions") and 2026-11-12 (the L1 review page: refreshed sites,
the rationale for each pick, and the contact sites the agents found).

Three steps, each re-runnable:

    # 1. normalize the pinned design tables (+ any tagged-refold manifests)
    uv run python scripts/cloud/build_l1_design_tables.py build \\
        --pins PINS.json --data-dir DIR --analysis-repo ~/git/deliverome-analysis [--refresh-pins]

    # 2. write the INSERT-only SQL for that load (content-addressed load_version)
    uv run python scripts/cloud/build_l1_design_tables.py sql --data-dir DIR --out load.sql \\
        [--redact-internal]

    # 3. apply: locally, or (after review) to production
    npx --yes wrangler d1 execute surfaceome_public --local  --file cloudflare/migrations/l1_design_v1.sql
    npx --yes wrangler d1 execute surfaceome_public --local  --file load.sql

The pins file and the built tables are NOT kept in this repository. They come from the
private design repository, and this repository is public. ``--pins`` names the file and
``--data-dir`` where the normalized TSVs and ``manifest.json`` go.

A pin is either ``{"commit", "path"}`` (read with ``git show`` from a local clone of
the design repository) or ``{"object": "processed://..."}`` (read from S3, read-only).
Every input's sha256 is recorded in the manifest. Nothing here talks to Cloudflare.

**Join key.** Member ids are still being renumbered, so no source is joined on member
id. Each row is resolved through its design id; when the source carries the ordered
protein's sha256 it must match the member's, or the row is dropped as stale and
counted in the manifest.

**Status** (the source's own value stays verbatim in ``decision`` / ``status_detail``):

* ``built``: the rung's builder emitted a tagged construct for this pick.
* ``decided_not_built``: the pick is decided (by Becca, or by a session she delegated
  to on 2026-11-12) but no construct is built yet.
* ``no_tag``: the member gets no tag on this rung (the reason says why, e.g. routed
  to another rung).
* ``pending``: the source table predates the 2026-11-12 delegation and still marks the
  pick as held or awaiting approval.
* ``alternative``: a ranked or proposed site that is not the current pick (ranker
  runners-up, agent-proposer picks), shown so a reviewer can compare.

``--redact-internal`` replaces the provenance columns (source PR / commit / path,
decided_by, implemented_by, reason, rejected_alternative, rationale) with a placeholder.
Whether to use it on the public API is a deploy-time decision.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import posixpath
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

IMPLEMENTED_BY = (
    "Claude Code session l1-viewer-tag-sites (scripts/cloud/build_l1_design_tables.py)"
)
#: What --redact-internal writes into the provenance columns.
REDACTED = "withheld: internal design record"
#: Nullable columns --redact-internal drops outright; NOT NULL ones get REDACTED.
REDACT_DROP = {
    "source_pr",
    "s3_uri",
    "rationale_json",
    "rejected_alternative",
    "reason",
}
REDACT_FILL = {"source_commit", "source_path", "decided_by", "implemented_by"}
#: Rows a source table leaves unattributed follow its rung's rule; say so rather than
#: inventing a decider.
RULE_DECIDER = "no individual decision: rung rule applied by the source builder"
#: D1 caps one SQL statement at 100 KB.
MAX_STATEMENT_BYTES = 60_000
#: R2 prefix for tagged refolds (ingest_library_structures_to_r2.py --prefix).
TAGGED_R2_PREFIX = "library-colabfold-tagged"

MEMBER_COLS = [
    "member_id", "design_id", "gene_symbol", "species", "candidate_set", "rung",
    "membrane_class", "n_tm", "ordered_length_aa", "sequence_sha256", "topology_version",
    "uniprot_acc", "proteoform_json",
]  # fmt: skip
SITE_COLS = [
    "site_id", "member_id", "design_id", "gene_symbol", "species", "candidate_set",
    "rung", "site_source", "is_primary", "insert_after_residue", "residue_before",
    "residue_after", "leader", "cassette", "cassette_aa", "rank", "status", "decision",
    "status_detail", "confidence", "rejected_alternative", "rationale_json",
    "tagged_protein_sha256", "source_pr", "source_pr_state", "source_commit",
    "source_path", "decided_by", "implemented_by", "reason",
]  # fmt: skip
STRUCT_COLS = [
    "structure_id", "member_id", "design_id", "gene_symbol", "kind", "site_id",
    "source", "release", "s3_uri", "r2_key", "model_url", "proteoform_match",
    "residue_offset", "ordered_length_aa", "model_length_aa", "is_chosen",
    "mean_plddt", "cassette_first_model_residue", "cassette_last_model_residue",
    "refold_verdict", "note", "decided_by", "implemented_by", "reason",
]  # fmt: skip
CONTACT_COLS = [
    "member_id", "design_id", "gene_symbol", "residue", "aa", "canonical_residue",
    "source", "evidence_types", "contact_classes", "confidence_tier", "ion_site",
    "additive_only", "in_extracellular", "topology_state", "ligands", "pmids",
]  # fmt: skip
TABLES = {
    "members": ("l1_member_public", MEMBER_COLS),
    "sites": ("l1_tag_site_design_public", SITE_COLS),
    "structures": ("l1_structure_design_public", STRUCT_COLS),
    "contacts": ("l1_contact_site_public", CONTACT_COLS),
}
INT_COLS = {
    "n_tm", "ordered_length_aa", "insert_after_residue", "cassette_aa", "rank",
    "source_pr", "residue_offset", "model_length_aa", "is_chosen", "is_primary",
    "cassette_first_model_residue", "cassette_last_model_residue", "residue",
    "canonical_residue", "ion_site", "additive_only", "in_extracellular",
}  # fmt: skip
STATUSES = {"built", "decided_not_built", "no_tag", "pending", "alternative"}


# --------------------------------------------------------------------------- inputs


def _rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode()), delimiter="\t"))


def _int(v) -> int | None:
    if v is None or str(v).strip() in ("", "nan", "None"):
        return None
    return int(float(v))


def _float(v) -> float | None:
    if v is None or str(v).strip() in ("", "nan", "None"):
        return None
    return float(v)


def _bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def _pr_state(src: dict) -> str:
    if src.get("ref") == "main":
        return "merged"
    return src.get("state", "open")


def _read(src: dict, repo: Path, base: str) -> tuple[bytes, dict]:
    """One pinned input, with the provenance the manifest records for it."""
    if "object" in src:
        uri = src["object"]
        if uri.startswith("file://"):  # a local copy (tests, or an offline rebuild)
            raw = Path(uri.removeprefix("file://")).read_bytes()
        else:
            s3 = uri.replace("processed://", "s3://deliverome-processed/")
            raw = subprocess.run(
                ["aws", "s3", "cp", "--only-show-errors", s3, "-"],
                check=True,
                capture_output=True,
            ).stdout
        where: dict = {"object": uri}
        if src.get("commit"):
            where["commit"] = src["commit"]
    else:
        path = posixpath.normpath(f"{src.get('base', base)}/{src['path']}")
        raw = subprocess.run(
            ["git", "-C", str(repo), "show", f"{src['commit']}:{path}"],
            check=True,
            capture_output=True,
        ).stdout
        where = {"commit": src["commit"], "path": path}
    got = hashlib.sha256(raw).hexdigest()
    if src.get("sha256") and src["sha256"] != got:
        raise SystemExit(f"{src}: content sha256 {got} != pinned {src['sha256']}")
    info = {
        "pending_note": src.get("pending_note"),
        "snorkel_pending_note": src.get("snorkel_pending_note"),
        "pr": src.get("pr"),
        "ref": src.get("ref"),
        "pr_state": _pr_state(src),
        "sha256": hashlib.sha256(raw).hexdigest(),
        **where,
    }
    return raw, info


def _refresh_pins(pins: dict, repo: Path) -> None:
    """Move every PR-backed git pin to that PR's current head (or its merge commit)."""
    subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin"], check=True)
    main = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    for name, src in pins["sources"].items():
        if src.get("ref") == "main":
            if "commit" in src:
                src["commit"] = main
            continue
        if src.get("pr") is None:
            continue
        info = json.loads(
            subprocess.run(
                ["gh", "pr", "view", str(src["pr"]), "--repo", pins["analysis_repo"],
                 "--json", "state,headRefOid,mergeCommit"],
                check=True, capture_output=True, text=True,
            ).stdout
        )  # fmt: skip
        merged = info["state"] == "MERGED" and info.get("mergeCommit")
        new = info["mergeCommit"]["oid"] if merged else info["headRefOid"]
        if "commit" in src and new != src["commit"]:
            print(f"  pin {name}: {src['commit'][:8]} -> {new[:8]} ({info['state']})")
        src["commit"] = new
        src["state"] = info["state"].lower()


# --------------------------------------------------------------------------- members


GPCR_PREFIXES = ("ADGR", "GPR", "OR", "TAS2R", "FZD", "CELSR")
TRANSPORTER_PREFIXES = ("SLC", "ABC", "ATP", "AQP", "MFSD", "SV2", "SPNS")
CHANNEL_PREFIXES = (
    "KCN", "SCN", "CACN", "TRP", "P2RX", "GABR", "GLR", "GRIA", "GRIN", "GRIK", "GRID",
    "CHRN", "ANO", "PIEZO", "CLCN", "HCN", "ASIC", "PKD", "ORAI", "TMC", "CNG", "HTR3",
    "ZACN", "PANX", "CALHM", "TTYH", "BEST", "LRRC8", "OTOP", "TMEM63", "TPCN", "HVCN",
    "NALCN", "ITPR", "RYR",
)  # fmt: skip


def _membrane_class(m: dict, gpcr: set[str]) -> str:
    """Rule-based class for browsing; NOT a curated annotation.

    GPCR comes from the multipass rung table's GPCR flag; transporter and ion channel
    from HGNC symbol families; the single-pass types from the tag-path rung and the
    DeepTMHMM v1 helix count of the ordered protein.
    """
    sym = m["gene_symbol"].upper()
    n_tm = m["n_tm"] if m["n_tm"] is not None else -1
    if m["design_id"] in gpcr:
        return "GPCR"
    if n_tm >= 2 and sym.startswith(CHANNEL_PREFIXES):
        return "ion channel"
    if n_tm >= 2 and sym.startswith(TRANSPORTER_PREFIXES):
        return "transporter"
    if n_tm >= 5 and sym.startswith(GPCR_PREFIXES):
        return "GPCR"
    rung = m["rung"]
    if n_tm == 1:
        if "type III" in rung:
            return "single-pass type III"
        if rung == "N after SP":
            return "single-pass type I"
        if rung == "C-terminal":
            return "single-pass type II"
        return "single-pass (other)"
    if n_tm == 0:
        return "GPI / no TM helix"
    if n_tm >= 2:
        return "multipass (other)"
    return "unclassified"


class Resolver:
    """design id (+ sequence sha256 when the source has one) -> member; never member id."""

    def __init__(self, members: dict[str, dict]):
        self.by_design = {m["design_id"]: m for m in members.values() if m["design_id"]}
        self.by_sha: dict[str, list[dict]] = {}
        for m in members.values():
            self.by_sha.setdefault(m["sequence_sha256"], []).append(m)
        self.dropped: dict[str, list[str]] = {}

    def get(
        self,
        source: str,
        design_id: str | None,
        sha: str | None = None,
        gene: str | None = None,
    ):
        m = self.by_design.get(design_id or "")
        why = None
        if m is None:
            why = f"{design_id}: not a member of the pinned universe"
        elif sha and m["sequence_sha256"] and sha != m["sequence_sha256"]:
            why = f"{design_id}: sequence changed since the source was built (stale)"
        elif gene and gene != m["gene_symbol"]:
            why = f"{design_id}: gene {gene} != member gene {m['gene_symbol']}"
        if why:
            self.dropped.setdefault(source, []).append(why)
            return None
        return m


# --------------------------------------------------------------------------- sites


def _site(src_info: dict, **kw) -> dict:
    row = {c: None for c in SITE_COLS}
    row.update(
        source_pr=src_info.get("pr"),
        source_pr_state=src_info.get("pr_state"),
        source_commit=src_info.get("commit") or src_info.get("sha256"),
        source_path=src_info.get("path") or src_info.get("object"),
        site_source="rung_builder",
        is_primary=1,
    )
    row.update(kw)
    # A source the coordinator marked as about to be replaced (e.g. "pending #284"):
    # keep its rows visible, but never as a settled pick.
    if src_info.get("pending_note") and row["status"] != "alternative":
        row["status_detail"] = (
            f"{src_info['pending_note']}; was {row['status']}: {row['status_detail'] or ''}".rstrip(
                ": "
            )
        )
        row["status"] = "pending"
    if not row["decided_by"]:
        row["decided_by"] = RULE_DECIDER
    if not row["implemented_by"]:
        row["implemented_by"] = f"source builder (design PR {src_info.get('pr')})"
    if isinstance(row["rationale_json"], dict):
        clean = {
            k: v
            for k, v in row["rationale_json"].items()
            if v not in (None, "", [], {})
        }
        row["rationale_json"] = json.dumps(clean, sort_keys=True) if clean else None
    assert row["status"] in STATUSES, row
    return row


def _diff(a, b) -> int | None:
    a_i, b_i = _int(a), _int(b)
    return None if a_i is None or b_i is None else a_i - b_i


SNORKEL_PLACEMENT = "snorkel"


def _cterm_decisions(rows) -> dict[str, dict]:
    """Per-member C-terminal decisions, keyed by the design id inside ``scope``
    ("l1-m0474 (l1-p0156) ATP1B1 human")."""
    out = {}
    for r in rows:
        m = re.search(r"\((l1-p\d+)\)", r.get("scope", ""))
        if m:
            out[m.group(1)] = r
    return out


def _cterm(rows, info, R, decisions=None):
    """C-terminal arms (incl. stalk and furin moves). Snorkel rows are skipped here:
    they are the internal member's pick and load through ``_internal``."""
    decisions = decisions or {}
    out = []
    for r in rows:
        if r["placement"].startswith(SNORKEL_PLACEMENT):
            continue
        m = R.get("cterm", r["design_id"], gene=r["gene_symbol"])
        if not m:
            continue
        res = _int(r["cassette_after_residue"])
        native = _int(r["native_aa"])
        d = decisions.get(m["design_id"], {})
        out.append(_site(
            info, site_id=f"{m['design_id']}-cterm-{res}", m=m,
            rung=m["rung"], insert_after_residue=res,
            cassette="p003 51-aa tandem (issued encoding)",
            cassette_aa=_diff(r["protein_aa"], r["native_aa"]),
            status="built", decision=d.get("decision") or r["placement"],
            status_detail=r["placement"] if res == native else f"{r['placement']}; native length {native}",
            rejected_alternative=d.get("rejected_alternatives") or None,
            tagged_protein_sha256=r["protein_sha256"] or None,
            rationale_json={
                "question": d.get("question"), "evidence": d.get("evidence"),
                "would_change_it": d.get("would_change_it"),
                "review_flags": r["review_flags"], "junction_edit": r["junction_edit"],
                "worst_partner_tract_nt": r["worst_partner_tract_nt"],
                "worst_partner": r["worst_partner"], "cassette_features": r["cassette_features"],
            },
            decided_by=d.get("decided_by") or r["decided_by"],
            implemented_by=d.get("implemented_by") or r["implemented_by"],
            reason=d.get("reason") or r["reason"] or r["review_flags"] or None,
        ))  # fmt: skip
    # A decision with no construct (e.g. "hold (not built)" after a failed refold) still
    # shows: the member has been decided, it just has no tag on this rung.
    built = {r["design_id"] for r in rows}
    for design_id, d in decisions.items():
        if design_id in built:
            continue
        m = R.get("cterm_decisions", design_id)
        if not m:
            continue
        out.append(_site(
            info, site_id=f"{m['design_id']}-cterm-held", m=m, rung=m["rung"],
            insert_after_residue=None, status="no_tag", decision=d.get("decision"),
            status_detail=d.get("question") or None,
            rejected_alternative=d.get("rejected_alternatives") or None,
            rationale_json={"evidence": d.get("evidence"), "would_change_it": d.get("would_change_it")},
            decided_by=d.get("decided_by"), implemented_by=d.get("implemented_by"), reason=d.get("reason") or None,
        ))  # fmt: skip
    return out


def _nterm_sp(rows, info, R):
    out = []
    for r in rows:
        m = R.get("nterm_sp", r["design_id"], gene=r["gene_symbol"])
        if not m:
            continue
        status = "built" if r["status"] == "ready" else "pending"
        res = _int(r["insert_after_residue"])
        out.append(_site(
            info, site_id=f"{m['design_id']}-nsp-{res if res is not None else 'none'}", m=m,
            rung="N after SP", insert_after_residue=res,
            residue_before=r["residue_before"] or None, residue_after=r["residue_after"] or None,
            cassette="p003 51-aa tandem" if status == "built" else None,
            status=status, decision=r["subgroup"],
            status_detail=f"{r['status']} ({r['subgroup']}); cleavage after {r['cleavage_site'] or '?'}",
            tagged_protein_sha256=r["tagged_protein_sha256"] or None,
            rationale_json={
                "cleavage_site": r["cleavage_site"], "offset_past_cleavage": r.get("offset_past_cleavage"),
                "inside_predicted_fold": r.get("inside_predicted_fold"),
                "native_cleavage_probability": r.get("native_cleavage_probability"),
                "tagged_cleavage_probability": r.get("tagged_cleavage_probability"),
                "softened_over_0_07": r.get("softened_over_0_07"),
            },
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["reason"] or None,
        ))  # fmt: skip
    return out


def _nterm_decisions(rows, info, R):
    """N-after-SP decisions (delegated 2026-11-12): one row per member, keyed by design id.

    ``arm`` is native_site / igk_swap (both built) or no_nterm_arm (no tag). The cassette
    follows ``native_after_residue`` in the member's own numbering; for an Igk swap the
    leader replaces the native signal peptide (``igk_replaces_residues``).
    """
    out = []
    for r in rows:
        m = R.get("nterm_decisions", r["design_id"], gene=r["gene_symbol"])
        if not m:
            continue
        arm = r["arm"]
        res = _int(r.get("native_after_residue") or r.get("insert_after_residue"))
        built = arm in ("native_site", "igk_swap")
        verdict = r.get("refold_verdict") or None
        out.append(_site(
            info, site_id=f"{m['design_id']}-nsp-{res if res is not None else arm}", m=m,
            rung="N after SP", insert_after_residue=res if built else None,
            leader="igk" if arm == "igk_swap" else None,
            cassette="p003 51-aa tandem" if built else None,
            status="built" if built else "no_tag", decision=arm,
            status_detail=f"{arm}; refold verdict {verdict or 'none'}",
            rejected_alternative=r.get("rejected_alternative") or None,
            tagged_protein_sha256=r.get("tagged_sha256") or None,
            rationale_json={
                "cleavage_site": r.get("cleavage_site"), "inside_predicted_fold": r.get("inside_predicted_fold"),
                "tagged_cleavage_probability": _float(r.get("tagged_cleavage_probability")),
                "igk_replaces_residues": r.get("igk_replaces_residues"), "evidence": r.get("evidence"),
                "refold_verdict": verdict,
            },
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r.get("reason") or None,
        ))  # fmt: skip
    return out


def _type3(rows, info, R):
    out = []
    for r in rows:
        m = R.get("type3", r["design_id"], gene=r["gene_symbol"])
        if not m:
            continue
        design = r["design"]
        built = design in ("tag_alone", "igk_tag")
        out.append(_site(
            # The cassette goes after Met1 (native[0] + cassette + native[1:]);
            # Igk + Asp is prepended for igk_tag.
            info, site_id=f"{m['design_id']}-type3-r1", m=m,
            rung="N at residue 1, single-pass (type III)",
            insert_after_residue=1 if built else None,
            leader="igk" if design == "igk_tag" else None, cassette=r["cassette"] or None,
            cassette_aa=_diff(r["mature_aa"], r["native_aa"]) if built else None,
            status="built" if built else "pending", decision=design,
            status_detail=f"{design} ({r['subgroup']})",
            tagged_protein_sha256=r["protein_sha256"] or None,
            rationale_json={"subgroup": r["subgroup"], "cassette_decided_by": r.get("cassette_decided_by"),
                            "reviewed_by": r.get("reviewed_by")},
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["reason"] or None,
        ))  # fmt: skip
    return out


def _multipass(rows, info, R, lane):
    out = []
    by_design: dict[str, list[dict]] = {}
    for r in rows:
        by_design.setdefault(r["design_id"], []).append(r)
    for design_id, rs in by_design.items():
        # One primary per member: a decided construct first, then Igk.
        rs.sort(key=lambda r: (r["status"] != "decided", r["design"] != "igk_tag"))
        chk = lane.get(design_id, {})
        for i, r in enumerate(rs):
            m = R.get(
                "multipass",
                design_id,
                sha=r.get("native_sha256"),
                gene=r["gene_symbol"],
            )
            if not m:
                continue
            built = r["design"] in ("igk_tag", "tag_alone")
            status = "built" if built and r["status"] == "decided" else "pending"
            if r["design"] == "moved" and r["status"] == "decided":
                status = "no_tag"  # moved to another rung; the reason names it
            out.append(_site(
                # nterm_res1_multipass.py: "The cassette goes after Met1".
                info, site_id=f"{design_id}-res1-{r['design']}", m=m,
                rung="N at residue 1, multipass", is_primary=1 if i == 0 else 0,
                insert_after_residue=1 if built else None,
                leader="igk" if r["design"] == "igk_tag" else None,
                cassette=r["cassette"] or None,
                cassette_aa=_diff(r["mature_aa"], r["native_aa"]) if built else None,
                status=status if i == 0 else "alternative", decision=r["design"],
                status_detail=f"{r['status']}; GPCR={r['gpcr']}",
                tagged_protein_sha256=r["protein_sha256"] or None,
                rejected_alternative=r.get("rejected_alternative") or None,
                rationale_json={
                    "sequence_change": r.get("sequence_change"),
                    "lane_check": {k: chk.get(k) for k in ("lane_ok", "recommended_lane", "confidence", "evidence")}
                    if chk else None,
                    "cassette_decided_by": r.get("cassette_decided_by"),
                    # The refold folds the mature protein (leader cleaved): its sha256.
                    "mature_sha256": r.get("mature_sha256"),
                },
                decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["reason"] or None,
            ))  # fmt: skip
    return out


INTERNAL_DECISION_STATUS = {
    "internal_loop": "decided_not_built",
    "internal_loop_transferred": "decided_not_built",
    "internal_loop_orientation_unconfirmed": "decided_not_built",
    "snorkel": "decided_not_built",
    "route_to_nterm_after_sp": "no_tag",
}
LOOP_KEEP = (
    "segment_index", "start", "end", "segment_rank", "segment_score", "best_residue",
    "glycan_n", "disulfide_cys", "functional_sites", "ligand_contacts",
    "ligand_contacts_transferred", "partner_interface", "antibody_epitopes",
    "screen_intolerant", "median_plddt", "buried_fraction", "hard_negative_fraction",
    "membrane_side_eligible", "published_sites",
)  # fmt: skip


def _loop_evidence(loops: list[dict], residue: int | None) -> dict | None:
    if residue is None:
        return None
    for seg in loops:
        start, end = _int(seg["start"]), _int(seg["end"])
        if start is not None and end is not None and start <= residue <= end:
            return {k: seg[k] for k in LOOP_KEEP if seg.get(k) not in (None, "")}
    return None


def _ranker_scores(r: dict) -> dict:
    return {
        "rank_score": _float(r["rank_score"]),
        "absolute_score": _float(r["absolute_score"]),
        "best_region_pct_of_published_regions": _float(
            r["best_region_pct_of_published_regions"]
        ),
        "this_region_length": _int(r["this_region_length"]),
        "snorkel_candidate": _bool(r["snorkel_candidate"]),
    }


def _internal(
    decisions,
    proposed,
    info_dec,
    info_prop,
    R,
    loops_by_design,
    snorkels=None,
    snorkel_built=None,
    loop_built=None,
):
    out = []
    chosen: dict[str, int | None] = {}
    # The decisions table carries no junction letters; the ranked table does, for the
    # same (design, residue).
    junction = {
        (r["design_id"], _int(r["insert_after_residue"])): r.get("junction") or ""
        for r in proposed
    }
    for r in decisions:
        m = R.get(
            "internal_decisions",
            r["design_id"],
            sha=r["sequence_sha256"],
            gene=r["gene"],
        )
        if not m:
            continue
        res = _int(r["insert_after_residue"])
        chosen[m["design_id"]] = res
        dec = r["decision"]
        # A snorkel construct appends a module (linker + an added TM helix + the
        # cassette) after the native C-terminus, which puts the tag outside the cell.
        snork = (snorkels or {}).get(m["design_id"]) if dec == "snorkel" else None
        if snork and snork.get("sequence_sha256") not in (
            None,
            "",
            m["sequence_sha256"],
        ):
            R.dropped.setdefault("snorkel_designs", []).append(
                f"{m['design_id']}: snorkel design is stale"
            )
            snork = None
        status = INTERNAL_DECISION_STATUS.get(dec, "pending")
        detail = f"{dec}; refold verdict {r.get('refold_verdict') or 'none'}"
        # A snorkel the C-terminal builder already built: the member's pick is that
        # construct (native C-terminus, then the TM module and the cassette).
        built_snork = (
            (snorkel_built or {}).get(m["design_id"]) if dec == "snorkel" else None
        )
        # An internal loop arm the builder already built at this residue: the pick is built.
        built_loop = (loop_built or {}).get(m["design_id"])
        if built_loop and _int(built_loop["cassette_after_residue"]) != res:
            built_loop = (
                None  # built at another site: the decision is not what was built
            )
        if built_loop:
            status = "built"
            verdict = (
                built_loop.get("refold_verdict") or r.get("refold_verdict") or "none"
            )
            detail = f"{dec}; built ({built_loop.get('built_by') or 'internal builder'}); refold verdict {verdict}"
        if built_snork:
            status = "built"
            detail = f"{dec}; built as {built_snork['placement']}; refold verdict {r.get('refold_verdict') or 'none'}"
        if dec == "snorkel" and info_dec.get("snorkel_pending_note"):
            status, detail = (
                "pending",
                f"{info_dec['snorkel_pending_note']}; was decided_not_built: {detail}",
            )
        out.append(_site(
            info_dec, site_id=f"{m['design_id']}-internal-{res if res is not None else dec}", m=m,
            rung=m["rung"], site_source="ranker",
            insert_after_residue=(
                # Member numbering: the module (and the cassette after it) follows the
                # native C-terminus. cassette_after_residue counts the added module.
                _int(built_snork["native_aa"]) if built_snork
                else _int(snork["native_length"]) if snork else res
            ),
            cassette=(
                "p003 51-aa tandem (internal loop arm)" if built_loop
                else "snorkel: added TM module, then the 51-aa cassette" if built_snork
                else f"snorkel module, {snork['module_length']} aa (added TM helix + linkers + 51-aa cassette)"
                if snork else None
            ),
            cassette_aa=(
                _diff(built_loop["protein_aa"], built_loop["native_aa"]) if built_loop
                else _diff(built_snork["protein_aa"], built_snork["native_aa"]) if built_snork
                else _int(snork["module_length"]) if snork else None
            ),
            tagged_protein_sha256=(
                built_snork["protein_sha256"] if built_snork
                else built_loop["protein_sha256"] if built_loop
                else (snork or {}).get("snorkel_protein_sha256")
            ) or None,
            residue_before=((built_loop or {}).get("junction") or junction.get((r["design_id"], res), "")).partition("|")[0][:1] or None,
            residue_after=((built_loop or {}).get("junction") or junction.get((r["design_id"], res), "")).partition("|")[2][:1] or None,
            rank=_int(r["pick_rank"]), status=status,
            decision=dec, status_detail=detail,
            confidence=r["confidence"] or None, rejected_alternative=r["rejected_alternative"] or None,
            rationale_json={
                **_ranker_scores(r), "refold_verdict": r.get("refold_verdict"),
                "decided_on": r.get("decided_on"),
                "snorkel_construct": {
                    "placement": built_snork["placement"],
                    "cassette_after_construct_residue": built_snork["cassette_after_residue"],
                    "native_aa": built_snork["native_aa"], "protein_aa": built_snork["protein_aa"],
                } if built_snork else None,
                "snorkel_design": {k: snork.get(k) for k in ("components", "status", "reason", "rejected_alternative",
                                                            "decided_by", "implemented_by")} if snork else None,
                "loop_evidence": _loop_evidence(loops_by_design.get(m["design_id"], []), res),
            },
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["reason"] or None,
        ))  # fmt: skip
    for r in proposed:
        m = R.get(
            "internal_proposed",
            r["design_id"],
            sha=r["sequence_sha256"],
            gene=r["gene"],
        )
        if not m:
            continue
        res = _int(r["insert_after_residue"])
        rank = _int(r["rank"])
        if rank is None or rank > 2 or res == chosen.get(m["design_id"]):
            continue  # ranks 1-2 only, and never the decided pick twice
        before, _, after = (r.get("junction") or "").partition("|")
        out.append(_site(
            info_prop, site_id=f"{m['design_id']}-v5-r{rank}", m=m, rung=m["rung"],
            site_source="ranker", is_primary=0, insert_after_residue=res, rank=rank,
            residue_before=before[:1] or None, residue_after=after[:1] or None,
            status="alternative", decision="ranked proposal",
            status_detail=f"ranker rank {rank}" + ("; snorkel candidate" if _bool(r["snorkel_candidate"]) else ""),
            rationale_json={
                **_ranker_scores(r), "refold_priority": r.get("refold_priority"),
                "loop_evidence": _loop_evidence(loops_by_design.get(m["design_id"], []), res),
            },
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["why"] or None,
        ))  # fmt: skip
    return out


def _built_loop_arms(rows, info, R):
    """The loop arms already built (membrane-side gate table, source built_loop_arm)."""
    out = []
    for r in rows:
        if r["source"] != "built_loop_arm" or r["shipped"] != "1":
            continue
        m = R.get("built_loop_arms", r["design_id"], gene=r["gene_symbol"])
        if not m:
            continue
        out.append(_site(
            info, site_id=r["site_id"], m=m, rung=m["rung"], is_primary=1,
            insert_after_residue=_int(r["insert_after_residue"]),
            residue_before=r["residue_before"] or None, residue_after=r["residue_after"] or None,
            status="built", decision="built_loop_arm",
            status_detail=f"membrane-side gate: {r['verdict']}",
            rationale_json={"height_A": _float(r["height_A"]), "plddt": _float(r["plddt"]),
                            "gate_verdict": r["verdict"]},
            decided_by=r["decided_by"], implemented_by=r["implemented_by"], reason=r["reason"] or None,
        ))  # fmt: skip
    return out


def _agent_picks(rows, info, members_by_design, canonical_sha):
    """Agent-proposer picks (arm 'full' only), numbered on the UniProt canonical.

    Loaded only for members whose ordered protein IS the canonical (sha256 equal), so
    canonical numbering is member numbering; every other member is skipped rather than
    mapped by position.
    """
    by_gene: dict[str, list[dict]] = {}
    for m in members_by_design.values():
        if (
            canonical_sha.get(m["design_id"]) == m["sequence_sha256"]
            and m["candidate_set"] != "ortholog"
        ):
            by_gene.setdefault(m["gene_symbol"], []).append(m)
    out, skipped = [], 0
    for r in rows:
        if r["arm"] != "full" or _bool(r.get("abstained")):
            continue
        ms = by_gene.get(r["gene"], [])
        if not ms:
            skipped += 1
            continue
        for m in ms:
            out.append(_site(
                info, site_id=f"{m['design_id']}-agent-r{r['rank']}", m=m, rung=m["rung"],
                site_source="agent_proposer", is_primary=0,
                insert_after_residue=_int(r["insert_after_residue"]),
                rank=_int(r["rank"]), residue_before=r["residue_before"] or None,
                residue_after=r["residue_after"] or None, status="alternative",
                decision="agent proposal (experimental)", confidence=r["confidence"] or None,
                status_detail="agentic tag-site proposer, full dossier; benchmark top-3 0.71 vs ranker 0.73",
                rationale_json={"loop_index": r.get("loop_index"), "fields_used": r.get("fields_used"),
                                "validation": r.get("validation"), "n_rejected_loops": r.get("n_rejected_loops")},
                decided_by="no decision taken: proposal only",
                implemented_by="agentic tag-site proposer", reason=r["reason"] or None,
            ))  # fmt: skip
    return out, skipped


# --------------------------------------------------------------------------- contacts


def _contacts(rows, R) -> list[dict]:
    out: dict[tuple, dict] = {}
    for r in rows:
        ms = [
            m
            for m in R.by_sha.get(r["sequence_sha256"], [])
            if m["gene_symbol"] == r["gene"]
        ]
        if not ms:
            R.dropped.setdefault("lit_contacts", []).append(
                f"{r['candidate_id']}: no member with that sequence"
            )
            continue
        ion, additive = _bool(r["ion_site"]), _bool(r["additive_only"])
        ev = r["evidence_types"] or ""
        if ion or additive:
            tier = "hidden"
        elif "structure" in ev or "mutagenesis" in ev:
            tier = "high"
        else:
            tier = "lower"
        source = (
            "literature_agent"
            if r["evidence_class"] == "predicted_literature"
            else "uniprot_binding"
        )
        for m in ms:
            key = (m["member_id"], _int(r["residue"]), source)
            out[key] = {
                "member_id": m["member_id"], "design_id": m["design_id"], "gene_symbol": m["gene_symbol"],
                "residue": _int(r["residue"]), "aa": r["aa"] or None,
                "canonical_residue": _int(r["canonical_residue"]), "source": source,
                "evidence_types": ev or None, "contact_classes": r["contact_classes"] or None,
                "confidence_tier": tier, "ion_site": int(ion), "additive_only": int(additive),
                "in_extracellular": int(_bool(r["in_extracellular"])),
                "topology_state": r["deeptmhmm_v1_state"] or None,
                "ligands": r["ligands"] or None, "pmids": r["pmids"] or None,
            }  # fmt: skip
    return list(out.values())


# --------------------------------------------------------------------------- structures


def _native_structures(rows, info, members_by_member_id):
    out = []
    for r in rows:
        m = members_by_member_id.get(r["candidate_id"])
        if m is None:
            continue  # pre-renumbering ids the duplicate guard removed
        if m["gene_symbol"] != r["gene_symbol"]:
            raise SystemExit(
                f"payload {r['candidate_id']}: gene {r['gene_symbol']} != {m['gene_symbol']}"
            )
        row = {c: None for c in STRUCT_COLS}
        key = r["r2_key"]
        row.update(
            structure_id=f"{m['design_id']}-native-{r['source']}-{r['release']}",
            member_id=m["member_id"], design_id=m["design_id"], gene_symbol=m["gene_symbol"],
            kind="native", source=r["source"], release=r["release"],
            r2_key=key or None, model_url=r["model_url"] or None,
            s3_uri=(
                "processed://sprint4/s4e9-orf-design-fg-panel/predicted-structures/colabfold/"
                + key.split("library-colabfold/", 1)[1]
                if key.startswith("library-colabfold/") else None
            ),
            proteoform_match=r["proteoform_match"], residue_offset=_int(r["residue_offset"]) or 0,
            ordered_length_aa=_int(r["ordered_length_aa"]), model_length_aa=_int(r["model_length_aa"]),
            is_chosen=_int(r["is_chosen"]) or 0, mean_plddt=_float(r["mean_plddt"]),
            note=r["note"] or None,
            decided_by="structure choice by the payload builder (rule)",
            implemented_by=f"{info.get('path')} @ {(info.get('commit') or '')[:8]}; loaded by {IMPLEMENTED_BY}",
            reason="native model the payload says this member should show",
        )  # fmt: skip
        out.append(row)
    return out


#: Columns a tagged-refold manifest must carry, with the aliases accepted for each.
TAGGED_REQUIRED = {
    "design_id": ("design_id",),
    "pdb": ("pdb", "pdb_file", "pdb_name", "filename", "file", "pdb_key"),
}
TAGGED_OPTIONAL = {
    "site_id": ("site_id",),
    "sequence_sha256": ("native_sha256", "sequence_sha256"),
    "insert_after_residue": ("insert_after_residue", "cassette_after_residue"),
    "mean_plddt": ("mean_plddt", "plddt"),
    "cassette_first": ("cassette_first_model_residue", "cassette_start", "tag_start"),
    "cassette_last": ("cassette_last_model_residue", "cassette_end", "tag_end"),
    "model_length_aa": ("model_length_aa", "length_aa", "protein_aa"),
    "verdict": ("verdict", "refold_verdict"),
    "note": ("note", "notes"),
}


def _pick(row: dict, names: tuple[str, ...]) -> str | None:
    for n in names:
        if n in row and row[n] != "":
            return row[n]
    return None


def _tagged_structures(
    spec: dict, raw: bytes, info: dict, R, sites_by_design
) -> list[dict]:
    rows = _rows(raw)
    if rows:
        missing = [
            k for k, al in TAGGED_REQUIRED.items() if not any(a in rows[0] for a in al)
        ]
        if missing:
            raise SystemExit(
                f"{spec}: tagged manifest lacks {missing}; has {list(rows[0])}"
            )
    date = spec["release"]
    prefix = spec.get("pdb_prefix") or spec.get("object", "").rsplit("/", 1)[0] + "/"
    out = []
    for r in rows:
        m = R.get(
            "tagged",
            _pick(r, TAGGED_REQUIRED["design_id"]),
            sha=_pick(r, TAGGED_OPTIONAL["sequence_sha256"]),
        )
        if not m:
            continue
        pdb = Path(_pick(r, TAGGED_REQUIRED["pdb"]) or "").name
        site_id = _pick(r, TAGGED_OPTIONAL["site_id"])
        res = _int(_pick(r, TAGGED_OPTIONAL["insert_after_residue"]))
        if site_id is None:
            cands = [s for s in sites_by_design.get(m["design_id"], [])
                     if s["is_primary"] and (res is None or s["insert_after_residue"] == res)]  # fmt: skip
            site_id = cands[0]["site_id"] if len(cands) == 1 else None
        row = {c: None for c in STRUCT_COLS}
        row.update(
            structure_id=f"{m['design_id']}-tagged-{site_id or res or 'site'}-{date}",
            member_id=m["member_id"], design_id=m["design_id"], gene_symbol=m["gene_symbol"],
            kind="tagged", site_id=site_id, source="colabfold_tagged", release=date,
            s3_uri=prefix.rstrip("/") + "/" + pdb, r2_key=f"{TAGGED_R2_PREFIX}/{date}/{pdb}",
            proteoform_match="tagged_construct", residue_offset=0,
            ordered_length_aa=m.get("ordered_length_aa"),
            model_length_aa=_int(_pick(r, TAGGED_OPTIONAL["model_length_aa"])), is_chosen=1,
            mean_plddt=_float(_pick(r, TAGGED_OPTIONAL["mean_plddt"])),
            cassette_first_model_residue=_int(_pick(r, TAGGED_OPTIONAL["cassette_first"])),
            cassette_last_model_residue=_int(_pick(r, TAGGED_OPTIONAL["cassette_last"])),
            refold_verdict=_pick(r, TAGGED_OPTIONAL["verdict"]), note=_pick(r, TAGGED_OPTIONAL["note"]),
            decided_by=spec["decided_by"], implemented_by=spec["implemented_by"], reason=spec.get("reason"),
        )  # fmt: skip
        out.append(row)
    return out


def _mature_sha(site: dict) -> str | None:
    """The mature tagged protein's sha256 a source recorded for a site (Igk constructs)."""
    try:
        return (json.loads(site.get("rationale_json") or "{}") or {}).get(
            "mature_sha256"
        )
    except TypeError, ValueError:
        return None


def _tagged_refold_v1(
    spec: dict,
    index_raw: bytes,
    metrics_raw: bytes,
    R,
    sites_by_design,
    manifest_raw: bytes | None = None,
) -> list[dict]:
    """The tagged-refold run's own layout: ``structures.tsv`` (+ ``tagged_fold_metrics.tsv``).

    Two revisions of the index are accepted. The current one has ``kind`` (only
    ``tagged`` rows load; ``superseded``, ``control`` and ``native`` do not),
    ``design_id``, ``insert_after_native_residue`` and ``verdict``. The first one had
    ``tagged`` yes/no and an old member id. Either way a model resolves by design id
    + native sequence sha256, falling back to native sequence + gene when the row has
    no design id (loop rows), and never by member id. The folded site is the member's
    site at the insertion residue, when exactly one site sits there.
    """
    metrics = {r["fold_id"]: r for r in _rows(metrics_raw)} if metrics_raw else {}
    # The run's final per-construct verdicts (viewer manifest), keyed by the folded
    # protein's sha256; they override the index's verdict when present.
    final = {r["tagged_sha256"]: r for r in _rows(manifest_raw)} if manifest_raw else {}
    native_rows: list[dict] = []
    date = spec["release"]
    out = []
    for r in _rows(index_raw):
        if "kind" in r:
            if r["kind"] == "native":
                native_rows.append(r)
                continue
            if r["kind"] != "tagged":
                continue
        elif r.get("tagged") != "yes" or r.get("rung") in ("control", "sp_control"):
            continue
        gene = r.get("gene_symbol") or r.get("gene")
        if r.get("design_id"):
            m = R.get("tagged", r["design_id"], sha=r["native_sha256"], gene=gene)
            ms = [m] if m else []
        else:
            ms = [
                m
                for m in R.by_sha.get(r["native_sha256"], [])
                if m["gene_symbol"] == gene
            ]
            if not ms:
                R.dropped.setdefault("tagged", []).append(
                    f"{r['fold_id']}: no member with that native sequence"
                )
        met = metrics.get(r["fold_id"], {})
        res = _int(
            r.get("insert_after_native_residue") or met.get("insert_after_residue")
        )
        fin = final.get(r.get("tagged_sha256") or "", {})
        verdict = fin.get("verdict") or r.get("verdict") or met.get("verdict") or None
        plddt = r.get("mean_plddt") or met.get("mean_plddt")
        pdb = r["pdb_key"].rsplit("/", 1)[-1]
        for m in ms:
            mine = sites_by_design.get(m["design_id"], [])
            # The folded protein's sha256 names the construct exactly; the residue is the fallback.
            cands = [
                s
                for s in mine
                if r.get("tagged_sha256")
                and r["tagged_sha256"] in (s["tagged_protein_sha256"], _mature_sha(s))
            ]
            if not cands:
                cands = [
                    s
                    for s in mine
                    if res is not None and s["insert_after_residue"] == res
                ]
            site_id = cands[0]["site_id"] if len(cands) == 1 else None
            row = {c: None for c in STRUCT_COLS}
            row.update(
                structure_id=f"{m['design_id']}-tagged-{r['fold_id']}-{date}",
                member_id=m["member_id"], design_id=m["design_id"], gene_symbol=m["gene_symbol"],
                kind="tagged", site_id=site_id, source="colabfold_tagged", release=date,
                s3_uri=r["pdb_key"], r2_key=f"{TAGGED_R2_PREFIX}/{date}/{pdb}",
                proteoform_match="tagged_construct", residue_offset=0,
                ordered_length_aa=m.get("ordered_length_aa"), model_length_aa=_int(met.get("tagged_aa")),
                is_chosen=1, mean_plddt=_float(plddt),
                cassette_first_model_residue=_int(r.get("cassette_start_1based")),
                cassette_last_model_residue=_int(r.get("cassette_end_1based")),
                refold_verdict=verdict,
                note="; ".join(x for x in (
                    f"rung {r['rung']}",
                    f"insert after {res}" if res is not None else "",
                    f"TM to native {met['tm_native']}" if met.get("tm_native") else "",
                    f"site lDDT {met['lddt_site']}" if met.get("lddt_site") else "",
                    f"SP {met['sp_state']}" if met.get("sp_state") else "",
                    f"SpyTag003 RSA {fin['spytag003_rsa']}" if fin.get("spytag003_rsa") else "",
                    f"ALFA RSA {fin['alfa_rsa']}" if fin.get("alfa_rsa") else "",
                    fin.get("verdict_reasons") or met.get("verdict_reasons") or "",
                ) if x),
                decided_by=spec["decided_by"], implemented_by=r.get("implemented_by") or spec["implemented_by"],
                reason=spec.get("reason") or r.get("settings"),
            )  # fmt: skip
            out.append(row)
    # Native-only folds: the run folded members that had no native model of their own
    # protein. Loaded as the member's native model only when the payload gave it none.
    for r in native_rows:
        gene = r.get("gene_symbol") or r.get("gene")
        m = (
            R.get(
                "tagged_native", r.get("design_id"), sha=r["native_sha256"], gene=gene
            )
            if r.get("design_id")
            else None
        )
        if not m or m["design_id"] in (spec.get("_has_native") or set()):
            continue
        pdb = r["pdb_key"].rsplit("/", 1)[-1]
        row = {c: None for c in STRUCT_COLS}
        row.update(
            structure_id=f"{m['design_id']}-native-refold-{r['fold_id']}-{date}",
            member_id=m["member_id"], design_id=m["design_id"], gene_symbol=m["gene_symbol"],
            kind="native", source="colabfold", release=date, s3_uri=r["pdb_key"],
            r2_key=f"{TAGGED_R2_PREFIX}/{date}/{pdb}", proteoform_match="ours_by_construction",
            residue_offset=0, ordered_length_aa=m.get("ordered_length_aa"),
            model_length_aa=m.get("ordered_length_aa"), is_chosen=1, mean_plddt=_float(r.get("mean_plddt")),
            note="native fold from the tagged-refold run (no payload model of this protein)",
            decided_by=spec["decided_by"], implemented_by=r.get("implemented_by") or spec["implemented_by"],
            reason=spec.get("reason") or r.get("settings"),
        )  # fmt: skip
        out.append(row)
    return out


# --------------------------------------------------------------------------- build


def build(args) -> int:
    pins_path = Path(args.pins).expanduser()
    out_dir = Path(args.data_dir).expanduser()
    pins = json.loads(pins_path.read_text())
    repo = Path(args.analysis_repo).expanduser()
    if args.refresh_pins:
        _refresh_pins(pins, repo)
        pins_path.write_text(json.dumps(pins, indent=2) + "\n")
    base = pins["base_dir"]
    raw, inputs = {}, {}
    for name, src in pins["sources"].items():
        raw[name], inputs[name] = _read(src, repo, base)
    T = {name: _rows(b) for name, b in raw.items()}

    renum = {r["candidate_id"]: r["design_id"] for r in T["renumbering"]}
    gpcr = {r["design_id"] for r in T["multipass"] if r.get("gpcr") == "1"}
    members: dict[str, dict] = {}
    for r in T["tag_paths"]:
        if r["library"] != "l1":
            continue
        m = {
            "member_id": r["candidate_id"], "design_id": renum.get(r["candidate_id"]),
            "gene_symbol": r["gene_symbol"], "species": r["species"],
            "candidate_set": r["candidate_set"], "rung": r["placement"], "n_tm": _int(r["n_tm"]),
            "ordered_length_aa": _int(r["length_aa"]), "sequence_sha256": r["sequence_sha256"] or None,
            "topology_version": r["topology_version"] or None,
        }  # fmt: skip
        m["membrane_class"] = _membrane_class(m, gpcr)
        members[m["member_id"]] = m
    R = Resolver(members)
    payload_acc = {
        r["candidate_id"]: r.get("uniprot_acc") or None
        for r in T["structure_payload"]
        if r.get("is_chosen") == "1"
    }
    for m in members.values():
        m["proteoform_json"] = None
        m["uniprot_acc"] = payload_acc.get(m["member_id"])
    for r in T.get("proteoform_decisions", []):
        m = R.get("proteoform_decisions", r["design_id"], gene=r["gene_symbol"])
        if m:
            keep = ("decision", "target", "status", "flags", "flag_class", "reason", "alternative_rejected",
                    "decided_by", "implemented_by")  # fmt: skip
            m["proteoform_json"] = json.dumps(
                {k: r.get(k) for k in keep if r.get(k)}, sort_keys=True
            )

    lane = {r["design_id"]: r for r in T["multipass_lane_check"]}
    loops: dict[str, list[dict]] = {}
    for r in T["loop_evidence"]:
        loops.setdefault(r["candidate_id"], []).append(r)
    canonical_sha: dict[str, str] = {}
    for r in T["lit_contacts"]:
        for m in R.by_sha.get(r["sequence_sha256"], []):
            canonical_sha[m["design_id"]] = r["canonical_sequence_sha256"]

    sites: list[dict] = []
    sites += _cterm(
        T["cterm"], inputs["cterm"], R, _cterm_decisions(T.get("cterm_decisions", []))
    )
    # Built internal loop arms (the integration build of the ranker's decisions).
    loop_built = {r["design_id"]: r for r in T.get("internal_constructs", [])}
    snorkel_built = {
        r["design_id"]: r
        for r in T["cterm"]
        if r["placement"].startswith(SNORKEL_PLACEMENT)
    }
    if (
        "nterm_decisions" in T
    ):  # the delegated decisions supersede the reviewer-package picks
        sites += _nterm_decisions(T["nterm_decisions"], inputs["nterm_decisions"], R)
    else:
        sites += _nterm_sp(T["nterm_sp"], inputs["nterm_sp"], R)
    sites += _type3(T["type3"], inputs["type3"], R)
    sites += _multipass(T["multipass"], inputs["multipass"], R, lane)
    snorkels = {r["design_id"]: r for r in T.get("snorkel_designs", [])}
    sites += _internal(T["internal_decisions"], T["internal_proposed"], inputs["internal_decisions"],
                       inputs["internal_proposed"], R, loops, snorkels, snorkel_built, loop_built)  # fmt: skip
    sites += _built_loop_arms(T["internal_gate"], inputs["internal_gate"], R)
    agent, agent_skipped = _agent_picks(
        T["agent_picks"], inputs["agent_picks"], R.by_design, canonical_sha
    )
    sites += agent
    for s in sites:  # member-level columns always come from the resolved member
        m = s.pop("m")
        s.update(member_id=m["member_id"], design_id=m["design_id"], gene_symbol=m["gene_symbol"],
                 species=m["species"], candidate_set=m["candidate_set"])  # fmt: skip

    problems, seen = [], set()
    for s in sites:
        m = members[s["member_id"]]
        if s["site_id"] in seen:
            problems.append(f"duplicate site_id {s['site_id']}")
        seen.add(s["site_id"])
        r = s["insert_after_residue"]
        if (
            r is not None
            and m["ordered_length_aa"] is not None
            and not 0 <= r <= m["ordered_length_aa"]
        ):
            problems.append(
                f"{s['site_id']}: residue {r} outside 0..{m['ordered_length_aa']}"
            )
    if problems:
        print("\n".join(problems[:40]), file=sys.stderr)
        raise SystemExit(f"{len(problems)} integrity problem(s); nothing written")

    structures = _native_structures(
        T["structure_payload"], inputs["structure_payload"], members
    )
    by_design: dict[str, list[dict]] = {}
    for s in sites:
        by_design.setdefault(s["design_id"], []).append(s)
    tagged_inputs = []
    has_native = {
        st["design_id"]
        for st in structures
        if st["kind"] == "native" and st["is_chosen"]
    }
    for spec in pins.get("tagged_structures", []):
        traw, tinfo = _read(spec, repo, base)
        if spec.get("format") == "l1_tag_refold_v1":
            spec = {**spec, "_has_native": has_native}
            msrc = (
                {"object": spec["metrics"]}
                if "metrics" in spec
                else {"commit": spec["commit"], "path": spec["metrics_path"]}
            )
            mraw, minfo = _read(msrc, repo, base)
            tinfo["metrics_sha256"] = minfo["sha256"]
            fraw = None
            if spec.get("manifest_path"):
                fraw, finfo = _read(
                    {"commit": spec["commit"], "path": spec["manifest_path"]},
                    repo,
                    base,
                )
                tinfo["manifest_sha256"] = finfo["sha256"]
            rows = _tagged_refold_v1(spec, traw, mraw, R, by_design, fraw)
        else:
            rows = _tagged_structures(spec, traw, tinfo, R, by_design)
        structures += rows
        tagged_inputs.append({**tinfo, "release": spec["release"], "n": len(rows)})
    inputs["tagged_structures"] = tagged_inputs
    contacts = _contacts(T["lit_contacts"], R)

    members_rows = sorted(members.values(), key=lambda r: r["member_id"])
    sites.sort(key=lambda r: (r["member_id"], -r["is_primary"], r["site_id"]))
    structures.sort(key=lambda r: (r["member_id"], r["structure_id"]))
    contacts.sort(key=lambda r: (r["member_id"], r["residue"], r["source"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    tables = {
        "members": members_rows,
        "sites": sites,
        "structures": structures,
        "contacts": contacts,
    }
    for name, rows in tables.items():
        cols = TABLES[name][1]
        buf = io.StringIO()
        w = csv.DictWriter(
            buf, cols, delimiter="\t", lineterminator="\n", extrasaction="raise"
        )
        w.writeheader()
        for r in rows:
            w.writerow({c: "" if r[c] is None else r[c] for c in cols})
        text = buf.getvalue()
        (out_dir / f"l1_design_{name}.tsv").write_text(text)
        digest.update(text.encode())
    content = digest.hexdigest()

    with_site = {s["member_id"] for s in sites if s["is_primary"]}
    counts = {
        "members": len(members_rows), "sites": len(sites), "structures": len(structures),
        "contacts": len(contacts),
        "sites_by_rung_status": _count(sites, "rung", "status"),
        "sites_by_source": _count(sites, "site_source", "is_primary"),
        "members_by_class": _count(members_rows, "membrane_class"),
        "members_without_primary_site": sorted(set(members) - with_site),
        "structures_by_kind_source": _count(structures, "kind", "source"),
        "contacts_by_source_tier": _count(contacts, "source", "confidence_tier"),
        "dropped_rows": {k: {"n": len(v), "examples": v[:15]} for k, v in R.dropped.items()},
        "agent_picks_without_identical_member": agent_skipped,
    }  # fmt: skip
    manifest = {
        "load_version": f"l1d-{content[:16]}",
        "content_sha256": content,
        "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": inputs,
        "counts": counts,
        "implemented_by": IMPLEMENTED_BY,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    brief = {
        k: v
        for k, v in counts.items()
        if k not in ("members_without_primary_site", "dropped_rows")
    }
    print(json.dumps(brief, indent=2))
    print("dropped:", {k: v["n"] for k, v in counts["dropped_rows"].items()})
    print(
        f"members without a primary site: {len(counts['members_without_primary_site'])}"
    )
    print(f"load_version {manifest['load_version']}")
    return 0


def _count(rows, *keys):
    out: dict[str, int] = {}
    for r in rows:
        k = " | ".join(str(r[x]) for x in keys)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------- sql


def _lit(v) -> str:
    if v is None or v == "":
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _typed(col: str, v: str):
    if v == "":
        return None
    if col in INT_COLS:
        return int(v)
    if col == "mean_plddt":
        return float(v)
    return v


def _redact(col: str, value: str) -> str:
    if col in REDACT_DROP:
        return ""
    if col in REDACT_FILL:
        return REDACTED
    return value


def _public_inputs(inputs: dict) -> dict:
    """Input provenance with the internal coordinates replaced by their content hashes."""
    out = {}
    for name, info in inputs.items():
        if isinstance(info, list):
            out[name] = [{"sha256": x.get("sha256"), "n": x.get("n")} for x in info]
        else:
            out[name] = {"sha256": info.get("sha256")}
    return out


def sql(args) -> int:
    out_dir = Path(args.data_dir).expanduser()
    manifest = json.loads((out_dir / "manifest.json").read_text())
    lv = manifest["load_version"]
    if args.redact_internal:
        # A redacted load is different content, so it gets its own version: applying one
        # variant must never block the other through INSERT OR IGNORE on the same keys.
        lv = (
            "l1d-"
            + hashlib.sha256(
                f"{manifest['content_sha256']}:redacted".encode()
            ).hexdigest()[:16]
        )
    content = hashlib.sha256()
    lines = [
        f"-- L1 design overlay load {lv} (content {manifest['content_sha256']}).",
        "-- INSERT OR IGNORE only: re-applying is a no-op; no row is updated or deleted.",
        "-- Apply cloudflare/migrations/l1_design_v1.sql first.",
    ]
    for name, (table, cols) in TABLES.items():
        text = (out_dir / f"l1_design_{name}.tsv").read_text()
        content.update(text.encode())
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        head = f"INSERT OR IGNORE INTO {table} ({', '.join(['load_version', *cols])}) VALUES\n  "
        chunk: list[str] = []
        size = len(head)
        for r in rows:
            if args.redact_internal:
                r = {c: _redact(c, r[c]) for c in cols}
            tup = (
                "("
                + ", ".join([_lit(lv)] + [_lit(_typed(c, r[c])) for c in cols])
                + ")"
            )
            # D1 rejects a statement over 100 KB (SQLITE_TOOBIG); stay well under it.
            if chunk and (
                size + len(tup.encode()) > MAX_STATEMENT_BYTES
                or len(chunk) >= args.rows_per_statement
            ):
                lines.append(head + ",\n  ".join(chunk) + ";")
                chunk, size = [], len(head)
            chunk.append(tup)
            size += len(tup.encode()) + 4
        if chunk:
            lines.append(head + ",\n  ".join(chunk) + ";")
    if content.hexdigest() != manifest["content_sha256"]:
        raise SystemExit("the TSVs no longer match manifest.json; re-run `build`")
    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    c = manifest["counts"]
    inputs = (
        _public_inputs(manifest["inputs"])
        if args.redact_internal
        else manifest["inputs"]
    )
    # The load row goes LAST: the Worker only serves a load that has one.
    lines.append(
        "INSERT OR IGNORE INTO l1_design_load_public (load_version, content_sha256, created_at, "
        "inputs_json, n_members, n_sites, n_structures, n_contacts, loader, implemented_by, note) VALUES ("
        + ", ".join(
            _lit(v)
            for v in [
                lv,
                manifest["content_sha256"],
                manifest["built_at"],
                json.dumps(inputs, sort_keys=True),
                c["members"],
                c["sites"],
                c["structures"],
                c["contacts"],
                f"scripts/cloud/build_l1_design_tables.py @ {commit}",
                manifest["implemented_by"],
                args.note,
            ]
        )  # fmt: skip
        + ");"
    )
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}: load {lv}, {c['members']} members, {c['sites']} sites, "
          f"{c['structures']} structures, {c['contacts']} contacts")  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="normalize pinned inputs into --data-dir")
    b.add_argument(
        "--pins", required=True, help="pinned-inputs JSON (kept outside this repo)"
    )
    b.add_argument(
        "--data-dir", required=True, help="where the normalized TSVs + manifest.json go"
    )
    b.add_argument("--analysis-repo", default="~/git/deliverome-analysis")
    b.add_argument(
        "--refresh-pins",
        action="store_true",
        help="move PR pins to their current heads (gh)",
    )
    b.set_defaults(func=build)
    s = sub.add_parser("sql", help="write the INSERT-only SQL for the built load")
    s.add_argument("--data-dir", required=True, help="the --data-dir a `build` wrote")
    s.add_argument("--out", required=True)
    s.add_argument("--rows-per-statement", type=int, default=200)
    s.add_argument("--note", default=None)
    s.add_argument("--redact-internal", action="store_true",
                   help="withhold source PR/commit/path, decided_by, implemented_by, reason, rationale")  # fmt: skip
    s.set_defaults(func=sql)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
