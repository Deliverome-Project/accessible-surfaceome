#!/usr/bin/env python
"""Build the L1 design overlay (suggested tag sites + folded structures) for public D1.

Requested by Becca Carlson, 2026-11-11 ("update the viewer with suggested tag sites as
well as with folded versions").

Three steps, each re-runnable:

    # 1. normalize the pinned design tables (+ any tagged-refold manifests)
    uv run python scripts/cloud/build_l1_design_tables.py build \
        --pins PINS.json --data-dir DIR --analysis-repo ~/git/deliverome-analysis [--refresh-pins]

    # 2. write the INSERT-only SQL for that load (content-addressed load_version)
    uv run python scripts/cloud/build_l1_design_tables.py sql --data-dir DIR --out load.sql \
        [--redact-internal]

    # 3. apply: locally, or (after review) to production
    npx --yes wrangler d1 execute surfaceome_public --local  --file cloudflare/migrations/l1_design_v1.sql
    npx --yes wrangler d1 execute surfaceome_public --local  --file load.sql

The pins file and the built tables are NOT kept in this repository. They come from the
private design repository: its PR numbers, commits and decision records are internal,
and this repository is public. Keep them next to the design work. ``--pins`` names the
file, and ``--data-dir`` names where the normalized TSVs and ``manifest.json`` go.

Nothing here talks to Cloudflare. ``build`` reads git objects from a local clone of the
design repository at pinned commits, and reads tagged-refold manifests from S3
(read-only). ``sql`` emits statements that only ever ``INSERT OR IGNORE``. A load never
updates or deletes a row, re-applying the same load is a no-op, and the load row goes in
last, so the Worker never serves a half-applied load.

``--redact-internal`` replaces the provenance columns (source PR / commit / path,
decided_by, implemented_by, reason) with a fixed placeholder, so the public API carries
the design and not the internal decision record. Whether to use it is a deploy-time
decision.

Status vocabulary (this loader's mapping; the source's own value is kept verbatim in
``status_detail``):

* ``built``: the rung's builder emitted a tagged arm for this site (C-terminal arms,
  N-after-SP sites marked ``ready``, type III ``tag_alone`` / ``igk_tag``, built loop
  arms). While the source PRs are open this means designed and checked, not ordered.
* ``proposed``: a site or leader is chosen but no arm is built yet (multipass Igk
  leader; internal-loop picks that pass the membrane-side gate).
* ``held``: the source holds, refuses or flags the member (N-after-SP held/refused,
  type III ``held``, multipass ``hold``/``off_rung`` or a failed lane check, internal
  picks the gate fails or sends to review).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import posixpath
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "cloudflare/migrations/l1_design_v1.sql"

IMPLEMENTED_BY = (
    "Claude Code session l1-viewer-tag-sites (scripts/cloud/build_l1_design_tables.py)"
)
#: What --redact-internal writes into the provenance columns.
REDACTED = "withheld: internal design record"
REDACT_COLS = {
    "source_pr",
    "source_commit",
    "source_path",
    "decided_by",
    "implemented_by",
    "reason",
    "s3_uri",
}
#: Rows a source table leaves unattributed follow its rung's rule; say so rather than
#: inventing a decider.
RULE_DECIDER = "no individual decision: rung rule applied by the source builder"

MEMBER_COLS = [
    "member_id",
    "design_id",
    "gene_symbol",
    "species",
    "candidate_set",
    "rung",
    "ordered_length_aa",
    "sequence_sha256",
    "topology_version",
]
SITE_COLS = [
    "site_id",
    "member_id",
    "design_id",
    "gene_symbol",
    "species",
    "candidate_set",
    "rung",
    "insert_after_residue",
    "residue_before",
    "residue_after",
    "leader",
    "cassette",
    "cassette_aa",
    "rank",
    "status",
    "status_detail",
    "tagged_protein_sha256",
    "source_pr",
    "source_pr_state",
    "source_commit",
    "source_path",
    "decided_by",
    "implemented_by",
    "reason",
]
STRUCT_COLS = [
    "structure_id",
    "member_id",
    "design_id",
    "gene_symbol",
    "kind",
    "site_id",
    "source",
    "release",
    "s3_uri",
    "r2_key",
    "model_url",
    "proteoform_match",
    "residue_offset",
    "ordered_length_aa",
    "model_length_aa",
    "is_chosen",
    "mean_plddt",
    "cassette_first_model_residue",
    "cassette_last_model_residue",
    "note",
    "decided_by",
    "implemented_by",
    "reason",
]
TABLES = {
    "members": ("l1_member_public", MEMBER_COLS),
    "sites": ("l1_tag_site_design_public", SITE_COLS),
    "structures": ("l1_structure_design_public", STRUCT_COLS),
}

#: R2 prefix the tagged refolds are ingested under (scripts/cloud/
#: ingest_library_structures_to_r2.py --prefix). Separate from library-colabfold/ so a
#: tagged model can never collide with, or overwrite, a native one.
TAGGED_R2_PREFIX = "library-colabfold-tagged"

#: D1 caps one SQL statement at 100 KB.
MAX_STATEMENT_BYTES = 60_000


# --------------------------------------------------------------------------- inputs


def _git_show(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    ).stdout


def _rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode()), delimiter="\t"))


def _int(v: str | None) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    return int(float(v))


def _refresh_pins(pins: dict, repo: Path) -> None:
    """Move every PR-backed pin to that PR's current head (or its merge commit)."""
    subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin"], check=True)
    main = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    for name, src in pins["sources"].items():
        if src.get("pr") is None or src.get("ref") == "main":
            src["commit"] = main
            continue
        info = json.loads(
            subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(src["pr"]),
                    "--repo",
                    pins["analysis_repo"],
                    "--json",
                    "state,headRefOid,mergeCommit",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        merged = info["state"] == "MERGED" and info.get("mergeCommit")
        new = info["mergeCommit"]["oid"] if merged else info["headRefOid"]
        if new != src["commit"]:
            print(f"  pin {name}: {src['commit'][:8]} -> {new[:8]} ({info['state']})")
        src["commit"] = new
        src["state"] = info["state"].lower()


def _pr_state(src: dict) -> str:
    if src.get("ref") == "main":
        return "merged"
    return src.get("state", "open")


# --------------------------------------------------------------------------- rungs


def _site(src: dict, path: str, **kw) -> dict:
    row = {c: None for c in SITE_COLS}
    row.update(
        source_pr=src.get("pr"),
        source_pr_state=_pr_state(src),
        source_commit=src["commit"],
        source_path=path,
        implemented_by=kw.pop("implemented_by", None) or "",
    )
    row.update(kw)
    if not row["decided_by"]:
        row["decided_by"] = RULE_DECIDER
    if not row["implemented_by"]:
        row["implemented_by"] = f"source builder (design PR {src.get('pr')})"
    return row


def _cterm(rows, src, path, members):
    out = []
    for r in rows:
        res = _int(r["cassette_after_residue"])
        native = _int(r["native_aa"])
        placement = r["placement"]
        out.append(
            _site(
                src,
                path,
                site_id=f"{r['candidate_id']}-cterm-{res}",
                member_id=r["candidate_id"],
                design_id=r["design_id"],
                gene_symbol=r["gene_symbol"],
                species=r["species"],
                candidate_set=r["candidate_set"],
                rung="C-terminal",
                insert_after_residue=res,
                cassette="p003 51-aa tandem (issued encoding)",
                cassette_aa=_diff(r["protein_aa"], r["native_aa"]),
                status="built",
                status_detail=placement
                if res == native
                else f"{placement}; native length {native}",
                tagged_protein_sha256=r["protein_sha256"] or None,
                decided_by=r["decided_by"],
                implemented_by=r["implemented_by"],
                reason=r["reason"] or r["review_flags"] or None,
            )
        )
    return out


def _diff(a: str, b: str) -> int | None:
    a_i, b_i = _int(a), _int(b)
    return None if a_i is None or b_i is None else a_i - b_i


def _nterm_sp(rows, src, path, members):
    out = []
    for r in rows:
        status = {"ready": "built"}.get(r["status"], "held")
        res = _int(r["insert_after_residue"])
        m = members.get(r["candidate_id"], {})
        out.append(
            _site(
                src,
                path,
                site_id=f"{r['candidate_id']}-nsp-{res if res is not None else 'none'}",
                member_id=r["candidate_id"],
                design_id=r["design_id"],
                gene_symbol=r["gene_symbol"],
                species=m.get("species"),
                candidate_set=r["candidate_set"],
                rung="N after SP",
                insert_after_residue=res,
                residue_before=r["residue_before"] or None,
                residue_after=r["residue_after"] or None,
                cassette="p003 51-aa tandem" if status == "built" else None,
                status=status,
                status_detail=f"{r['status']} ({r['subgroup']}); cleavage after {r['cleavage_site'] or '?'}",
                tagged_protein_sha256=r["tagged_protein_sha256"] or None,
                decided_by=r["decided_by"],
                implemented_by=r["implemented_by"],
                reason=r["reason"] or None,
            )
        )
    return out


def _type3(rows, src, path, members):
    out = []
    for r in rows:
        design = r["design"]
        built = design in ("tag_alone", "igk_tag")
        out.append(
            _site(
                src,
                path,
                # The cassette goes after Met1 (build_l1_type3_arms.py: native[0] + cassette
                # + native[1:]); Igk + Asp is prepended for igk_tag.
                site_id=f"{r['candidate_id']}-type3-r1",
                member_id=r["candidate_id"],
                design_id=r["design_id"],
                gene_symbol=r["gene_symbol"],
                species=r["species"],
                candidate_set=r["candidate_set"],
                rung="N at residue 1, single-pass (type III)",
                insert_after_residue=1 if built else None,
                leader="igk" if design == "igk_tag" else None,
                cassette=r["cassette"] or None,
                cassette_aa=_diff(r["mature_aa"], r["native_aa"]) if built else None,
                status="built" if built else "held",
                status_detail=f"{design} ({r['subgroup']})",
                tagged_protein_sha256=r["protein_sha256"] or None,
                decided_by=r["decided_by"],
                implemented_by=r["implemented_by"],
                reason=r["reason"] or None,
            )
        )
    return out


def _multipass(rows, src, path, members, lane):
    out = []
    for r in rows:
        chk = lane.get(r["candidate_id"], {})
        leader = r["planned_leader"]
        lane_bad = chk.get("lane_ok") in ("no", "unsure")
        status = "proposed" if leader == "igk" and not lane_bad else "held"
        detail = f"planned_leader={leader}; group={r['group']}; {r['leader_subgroup']}"
        if chk:
            detail += (
                f"; lane check: lane_ok={chk.get('lane_ok')}, "
                f"recommended={chk.get('recommended_lane')} ({chk.get('confidence')})"
            )
        out.append(
            _site(
                src,
                path,
                # nterm_res1_multipass.py: "The cassette goes after Met1".
                site_id=f"{r['candidate_id']}-res1",
                member_id=r["candidate_id"],
                design_id=r["design_id"],
                gene_symbol=r["gene_symbol"],
                species=r["species"],
                candidate_set=r["candidate_set"],
                rung="N at residue 1, multipass",
                insert_after_residue=1 if leader in ("igk",) else None,
                leader="igk" if leader == "igk" else None,
                cassette=r["cassette"] or None,
                status=status,
                status_detail=detail,
                decided_by=(
                    f"leader: {r['planned_leader_decided_by']}; cassette: {r['cassette_decided_by']}"
                    + (f"; lane: {chk['decided_by']}" if chk.get("decided_by") else "")
                ),
                implemented_by=(
                    f"{r['planned_leader_implemented_by']}"
                    + (
                        f"; lane check: {chk['implemented_by']}"
                        if chk.get("implemented_by")
                        else ""
                    )
                ),
                reason=r["planned_leader_reason"] or None,
            )
        )
    return out


#: membrane-side gate verdicts that keep a pick live as a proposal.
GATE_PASS = {"pass"}


def _internal(rows, src, path, members, design_to_member):
    out = []
    for r in rows:
        if r["source"] not in ("s5e13_v4", "built_loop_arm"):
            # api_surface_loop / api_disorder rows are the candidate pool the gate was
            # calibrated on, not suggestions; they are not loaded.
            continue
        if r["shipped"] != "1":
            continue
        verdict = r["verdict"]
        # The gate table's candidate_id column predates the l1-mNNNN renumbering (most
        # of its rows name another gene's member id), while its design_id + gene agree
        # with the renumbering table everywhere this loader reads. So the member is
        # resolved from design_id, and the source's own id is kept in status_detail.
        member_id = design_to_member.get(r["design_id"])
        if member_id is None:
            raise SystemExit(
                f"{r['site_id']}: design_id {r['design_id']} not in the renumbering table"
            )
        stale = (
            ""
            if member_id == r["candidate_id"]
            else f"; source candidate_id {r['candidate_id']} (pre-renumbering)"
        )
        if r["source"] == "built_loop_arm":
            status = "built"
        else:
            status = "proposed" if verdict in GATE_PASS else "held"
        out.append(
            _site(
                src,
                path,
                site_id=r["site_id"],
                member_id=member_id,
                design_id=r["design_id"],
                gene_symbol=r["gene_symbol"],
                species=r["species"],
                candidate_set=r["candidate_set"],
                rung="internal",
                insert_after_residue=_int(r["insert_after_residue"]),
                residue_before=r["residue_before"] or None,
                residue_after=r["residue_after"] or None,
                rank=_int(r["rank"]),
                status=status,
                status_detail=(
                    f"{r['source']}; membrane-side gate: {verdict}"
                    f" (height {r['height_A'] or '?'} A, pLDDT {r['plddt'] or '?'}){stale}"
                ),
                decided_by=r["decided_by"],
                implemented_by=r["implemented_by"],
                reason=r["reason"] or None,
            )
        )
    return out


def _internal_extra(rows, src, path, members):
    """Ranker picks for an internal member that joined L1 after the gate table was built.

    Scored as its own table; the gate result is recorded in prose only
    (``src['gate_note']``), so these load as ``proposed``.
    """
    mid = src["member_id"]
    m = members[mid]
    out = []
    for r in rows:
        if r["gene"] != m["gene_symbol"]:
            raise SystemExit(
                f"{path}: gene {r['gene']} != {mid} gene {m['gene_symbol']}"
            )
        rank = _int(r["rank"])
        out.append(
            _site(
                src,
                path,
                site_id=f"{m['design_id']}-v4-r{rank}",
                member_id=mid,
                design_id=m["design_id"],
                gene_symbol=m["gene_symbol"],
                species=m["species"],
                candidate_set=m["candidate_set"],
                rung="internal",
                insert_after_residue=_int(r["insert_after_residue"]),
                rank=rank,
                status="proposed",
                status_detail=f"s5e13_v4 (scored separately); {src['gate_note']}",
                decided_by="no decision taken: ranker v4 pick, not yet reviewed by Becca",
                implemented_by=src.get("implemented_by") or "ranker v4 --design",
                reason=r["why"] or None,
            )
        )
    return out


# --------------------------------------------------------------------------- structures


def _native_structures(rows, src, path, members, renum):
    out = []
    for r in rows:
        mid = r["candidate_id"]
        if mid not in renum:
            # Pre-renumbering ids (members the duplicate guard removed) have no l1-m id.
            continue
        m = members.get(mid, {})
        if m and m["gene_symbol"] != r["gene_symbol"]:
            raise SystemExit(
                f"payload {mid}: gene {r['gene_symbol']} != member gene {m['gene_symbol']}"
            )
        row = {c: None for c in STRUCT_COLS}
        row.update(
            structure_id=f"{mid}-native-{r['source']}-{r['release']}",
            member_id=mid,
            design_id=renum.get(mid),
            gene_symbol=m.get("gene_symbol") or r["gene_symbol"],
            kind="native",
            source=r["source"],
            release=r["release"],
            r2_key=r["r2_key"] or None,
            model_url=r["model_url"] or None,
            s3_uri=(
                "processed://sprint4/s4e9-orf-design-fg-panel/predicted-structures/colabfold/"
                + r["r2_key"].split("library-colabfold/", 1)[1]
                if r["r2_key"].startswith("library-colabfold/")
                else None
            ),
            proteoform_match=r["proteoform_match"],
            residue_offset=_int(r["residue_offset"]) or 0,
            ordered_length_aa=_int(r["ordered_length_aa"]),
            model_length_aa=_int(r["model_length_aa"]),
            is_chosen=_int(r["is_chosen"]) or 0,
            mean_plddt=float(r["mean_plddt"]) if r["mean_plddt"] else None,
            note=r["note"] or None,
            decided_by="structure choice by the payload builder (rule)",
            implemented_by=f"{src['path']} @ {src['commit'][:8]}; loaded by {IMPLEMENTED_BY}",
            reason="native model the payload says this member should show",
        )
        out.append(row)
    return out


#: Columns a tagged-refold manifest must carry, with the aliases accepted for each.
TAGGED_REQUIRED = {
    "member_id": ("member_id", "candidate_id"),
    "pdb": ("pdb", "pdb_file", "pdb_name", "filename", "file"),
}
TAGGED_OPTIONAL = {
    "site_id": ("site_id",),
    "design_id": ("design_id",),
    "insert_after_residue": ("insert_after_residue", "cassette_after_residue"),
    "mean_plddt": ("mean_plddt", "plddt"),
    "cassette_first": ("cassette_first_model_residue", "cassette_start", "tag_start"),
    "cassette_last": ("cassette_last_model_residue", "cassette_end", "tag_end"),
    "model_length_aa": ("model_length_aa", "length_aa", "protein_aa"),
    "rung": ("rung", "placement"),
    "note": ("note", "notes"),
}


def _pick(row: dict, names: tuple[str, ...]) -> str | None:
    for n in names:
        if n in row and row[n] != "":
            return row[n]
    return None


def _tagged_structures(spec: dict, members, sites_by_member) -> tuple[list[dict], dict]:
    """Read one tagged-refold manifest (S3 or local) into structure rows."""
    uri = spec["manifest"]
    if uri.startswith(("s3://", "processed://")):
        s3 = uri.replace("processed://", "s3://deliverome-processed/")
        raw = subprocess.run(
            ["aws", "s3", "cp", "--only-show-errors", s3, "-"],
            check=True,
            capture_output=True,
        ).stdout
    else:
        raw = Path(uri).expanduser().read_bytes()
    rows = _rows(raw)
    if rows:
        missing = [
            k for k, al in TAGGED_REQUIRED.items() if not any(a in rows[0] for a in al)
        ]
        if missing:
            raise SystemExit(
                f"{uri}: tagged manifest lacks {missing}; has {list(rows[0])}"
            )
    date = spec["release"]
    prefix = spec.get("s3_prefix") or uri.rsplit("/", 1)[0] + "/"
    out = []
    for r in rows:
        mid = _pick(r, TAGGED_REQUIRED["member_id"])
        pdb = Path(_pick(r, TAGGED_REQUIRED["pdb"])).name
        m = members.get(mid)
        if m is None:
            raise SystemExit(f"{uri}: {mid} is not an L1 member in the tag-paths table")
        site_id = _pick(r, TAGGED_OPTIONAL["site_id"])
        res = _int(_pick(r, TAGGED_OPTIONAL["insert_after_residue"]))
        if site_id is None:
            # Resolve the folded site from the member's site rows by insertion residue.
            cands = [
                s
                for s in sites_by_member.get(mid, [])
                if res is None or s["insert_after_residue"] == res
            ]
            site_id = cands[0]["site_id"] if len(cands) == 1 else None
        row = {c: None for c in STRUCT_COLS}
        plddt = _pick(r, TAGGED_OPTIONAL["mean_plddt"])
        row.update(
            structure_id=f"{mid}-tagged-{site_id or res or 'site'}-{date}",
            member_id=mid,
            design_id=m.get("design_id"),
            gene_symbol=m["gene_symbol"],
            kind="tagged",
            site_id=site_id,
            source="colabfold_tagged",
            release=date,
            s3_uri=prefix.rstrip("/") + "/" + pdb,
            r2_key=f"{TAGGED_R2_PREFIX}/{date}/{pdb}",
            proteoform_match="tagged_construct",
            residue_offset=0,
            ordered_length_aa=m.get("ordered_length_aa"),
            model_length_aa=_int(_pick(r, TAGGED_OPTIONAL["model_length_aa"])),
            is_chosen=1,
            mean_plddt=float(plddt) if plddt else None,
            cassette_first_model_residue=_int(
                _pick(r, TAGGED_OPTIONAL["cassette_first"])
            ),
            cassette_last_model_residue=_int(
                _pick(r, TAGGED_OPTIONAL["cassette_last"])
            ),
            note=_pick(r, TAGGED_OPTIONAL["note"]),
            decided_by=spec["decided_by"],
            implemented_by=spec["implemented_by"],
            reason=spec.get("reason"),
        )
        out.append(row)
    return out, {
        "manifest": uri,
        "release": date,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "n": len(out),
    }


# --------------------------------------------------------------------------- build


def build(args) -> int:
    pins_path = Path(args.pins).expanduser()
    OUT_DIR = Path(args.data_dir).expanduser()
    pins = json.loads(pins_path.read_text())
    repo = Path(args.analysis_repo).expanduser()
    if args.refresh_pins:
        _refresh_pins(pins, repo)
        pins_path.write_text(json.dumps(pins, indent=2) + "\n")
    base = pins["base_dir"]
    raw: dict[str, bytes] = {}
    inputs: dict[str, dict] = {}
    for name, src in pins["sources"].items():
        path = posixpath.normpath(f"{base}/{src['path']}")
        raw[name] = _git_show(repo, src["commit"], path)
        inputs[name] = {
            "repo": pins["analysis_repo"],
            "pr": src.get("pr"),
            "ref": src.get("ref"),
            "commit": src["commit"],
            "path": path,
            "pr_state": _pr_state(src),
            "sha256": hashlib.sha256(raw[name]).hexdigest(),
        }
    S = pins["sources"]

    renum = {r["candidate_id"]: r["design_id"] for r in _rows(raw["renumbering"])}
    members: dict[str, dict] = {}
    for r in _rows(raw["tag_paths"]):
        if r["library"] != "l1":
            continue
        members[r["candidate_id"]] = {
            "member_id": r["candidate_id"],
            "design_id": renum.get(r["candidate_id"]),
            "gene_symbol": r["gene_symbol"],
            "species": r["species"],
            "candidate_set": r["candidate_set"],
            "rung": r["placement"],
            "ordered_length_aa": _int(r["length_aa"]),
            "sequence_sha256": r["sequence_sha256"] or None,
            "topology_version": r["topology_version"] or None,
        }

    def P(name):
        return posixpath.normpath(f"{base}/{S[name]['path']}")

    lane = {r["candidate_id"]: r for r in _rows(raw["multipass_lane_check"])}
    sites: list[dict] = []
    sites += _cterm(_rows(raw["cterm"]), S["cterm"], P("cterm"), members)
    sites += _nterm_sp(_rows(raw["nterm_sp"]), S["nterm_sp"], P("nterm_sp"), members)
    sites += _type3(_rows(raw["type3"]), S["type3"], P("type3"), members)
    sites += _multipass(
        _rows(raw["multipass"]), S["multipass"], P("multipass"), members, lane
    )
    design_to_member = {p: m for m, p in renum.items()}
    sites += _internal(
        _rows(raw["internal_gate"]),
        S["internal_gate"],
        P("internal_gate"),
        members,
        design_to_member,
    )
    sites += _internal_extra(
        _rows(raw["internal_slc67a1"]),
        S["internal_slc67a1"],
        P("internal_slc67a1"),
        members,
    )

    # Integrity: every site belongs to an L1 member, and the source's gene agrees.
    problems = []
    seen = set()
    for s in sites:
        m = members.get(s["member_id"])
        if m is None:
            problems.append(f"{s['site_id']}: {s['member_id']} not in l1_tag_paths")
            continue
        if m["gene_symbol"] != s["gene_symbol"]:
            problems.append(
                f"{s['site_id']}: gene {s['gene_symbol']} != member gene {m['gene_symbol']}"
            )
        if s["design_id"] and m["design_id"] and s["design_id"] != m["design_id"]:
            problems.append(
                f"{s['site_id']}: design_id {s['design_id']} != renumbering {m['design_id']}"
            )
        if s["site_id"] in seen:
            problems.append(f"duplicate site_id {s['site_id']}")
        seen.add(s["site_id"])
        if s["insert_after_residue"] is not None and m["ordered_length_aa"] is not None:
            if not 0 <= s["insert_after_residue"] <= m["ordered_length_aa"]:
                problems.append(
                    f"{s['site_id']}: residue {s['insert_after_residue']} outside 0..{m['ordered_length_aa']}"
                )
        s["species"] = s["species"] or m["species"]
        s["candidate_set"] = s["candidate_set"] or m["candidate_set"]
        s["design_id"] = s["design_id"] or m["design_id"]
    if problems:
        print("\n".join(problems[:40]), file=sys.stderr)
        raise SystemExit(f"{len(problems)} integrity problem(s); nothing written")

    structures = _native_structures(
        _rows(raw["structure_payload"]),
        S["structure_payload"],
        P("structure_payload"),
        members,
        renum,
    )
    by_member: dict[str, list[dict]] = {}
    for s in sites:
        by_member.setdefault(s["member_id"], []).append(s)
    tagged_inputs = []
    for spec in pins.get("tagged_structures", []):
        rows, info = _tagged_structures(spec, members, by_member)
        structures += rows
        tagged_inputs.append(info)
    inputs["tagged_structures"] = tagged_inputs

    members_rows = sorted(members.values(), key=lambda r: r["member_id"])
    sites.sort(key=lambda r: (r["member_id"], r["site_id"]))
    structures.sort(key=lambda r: (r["member_id"], r["structure_id"]))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    for name, rows in (
        ("members", members_rows),
        ("sites", sites),
        ("structures", structures),
    ):
        cols = TABLES[name][1]
        buf = io.StringIO()
        w = csv.DictWriter(
            buf, cols, delimiter="\t", lineterminator="\n", extrasaction="raise"
        )
        w.writeheader()
        for r in rows:
            w.writerow({c: "" if r[c] is None else r[c] for c in cols})
        text = buf.getvalue()
        (OUT_DIR / f"l1_design_{name}.tsv").write_text(text)
        digest.update(text.encode())
    content = digest.hexdigest()

    counts = {
        "members": len(members_rows),
        "sites": len(sites),
        "structures": len(structures),
        "sites_by_rung_status": _count(sites, "rung", "status"),
        "members_without_site": sorted(set(members) - set(by_member)),
        "structures_by_kind_source": _count(structures, "kind", "source"),
    }
    manifest = {
        "load_version": f"l1d-{content[:16]}",
        "content_sha256": content,
        "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": inputs,
        "counts": counts,
        "implemented_by": IMPLEMENTED_BY,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in counts.items() if k != "members_without_site"}, indent=2
        )
    )
    print(f"members without a site row: {len(counts['members_without_site'])}")
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
    if col in {
        "ordered_length_aa",
        "insert_after_residue",
        "cassette_aa",
        "rank",
        "source_pr",
        "residue_offset",
        "model_length_aa",
        "is_chosen",
        "cassette_first_model_residue",
        "cassette_last_model_residue",
    }:
        return int(v)
    if col == "mean_plddt":
        return float(v)
    return v


def _redact(col: str, value: str) -> str:
    if col not in REDACT_COLS:
        return value
    if col in ("source_pr", "s3_uri"):  # nullable: drop outright
        return ""
    return REDACTED  # NOT NULL text columns keep a placeholder


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
    OUT_DIR = Path(args.data_dir).expanduser()
    manifest = json.loads((OUT_DIR / "manifest.json").read_text())
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
        text = (OUT_DIR / f"l1_design_{name}.tsv").read_text()
        content.update(text.encode())
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        collist = ", ".join(["load_version", *cols])
        head = f"INSERT OR IGNORE INTO {table} ({collist}) VALUES\n  "
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
                size + len(tup) > MAX_STATEMENT_BYTES
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
    # The load row goes LAST: the Worker only serves a load that has one.
    lines.append(
        "INSERT OR IGNORE INTO l1_design_load_public (load_version, content_sha256, created_at, "
        "inputs_json, n_members, n_sites, n_structures, loader, implemented_by, note) VALUES ("
        + ", ".join(
            _lit(v)
            for v in [
                lv,
                manifest["content_sha256"],
                manifest["built_at"],
                json.dumps(
                    _public_inputs(manifest["inputs"])
                    if args.redact_internal
                    else manifest["inputs"],
                    sort_keys=True,
                ),
                c["members"],
                c["sites"],
                c["structures"],
                f"scripts/cloud/build_l1_design_tables.py @ {commit}",
                manifest["implemented_by"],
                args.note,
            ]
        )
        + ");"
    )
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(
        f"wrote {args.out}: load {lv}, {c['members']} members, {c['sites']} sites, "
        f"{c['structures']} structures"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser(
        "build", help="normalize pinned inputs into data/processed/l1_design/"
    )
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
        help="move PR pins to their current heads (gh) before building",
    )
    b.set_defaults(func=build)
    s = sub.add_parser("sql", help="write the INSERT-only SQL for the built load")
    s.add_argument("--data-dir", required=True, help="the --data-dir a `build` wrote")
    s.add_argument("--out", required=True)
    s.add_argument(
        "--redact-internal",
        action="store_true",
        help="replace source PR/commit/path, decided_by, implemented_by, reason",
    )
    s.add_argument("--rows-per-statement", type=int, default=200)
    s.add_argument("--note", default=None)
    s.set_defaults(func=sql)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
