"""Second, deeper literature pass over the L1 members that need an INTERNAL
tag site — published BESIDE the first pass rather than over it.

This is a sibling of ``regenerate_tag_site_lit.py`` rather than a flag on it.
The control-panel driver is gene-keyed and numbers against the public API
record's canonical topology; this one is MEMBER-keyed and numbers against the
member's own translated sequence, which for 71 of the 566 internal-site members
is not the canonical protein. Those are different jobs with different inputs,
and the control path is pinned by tests that should not have to care about this.

What it does per member:

1. resolves the member's own sequence + per-residue topology from
   ``topology_public``, **verified by sha256** against the vendored member
   table — never by accession, because ``topology_acc`` is the candidate id for
   the designed-ORF cohort and an isoform-suffixed accession for another 47;
2. builds the proteoform frames a citation might be numbering in — canonical
   (marked EXPECTED, since a paper will essentially never use a designed ORF's
   coordinates), the mature frame when UniProt annotates a signal peptide, and
   sibling isoforms;
3. seeds the clip pool with everything an earlier run cited, so a paper that
   degraded to abstract-only today cannot take a known site with it;
4. drops clips that only restate a junction already published, and STOPS before
   the selector and synthesizer if nothing new survives;
5. publishes under provenance ``literature_enriched`` with the provenance scope
   passed explicitly, so the first pass's rows are never touched.

Runs PER MEMBER rather than per gene. 566 members against 518 genes is only 48
extra runs, and the discovery and triage caches are gene-keyed — triage being
one call per discovered paper, the bulk of a run's cost — so a second member of
the same gene reuses the expensive half and pays only for selection and
synthesis. Running once per gene and re-mapping afterwards would be cheaper
still, but it would mean one member's frame deciding another member's junctions,
which is the whole failure this pass exists to avoid.

    uv run python scripts/enrich_tag_site_lit.py --gene KCNN2 --dry-run
    uv run python scripts/enrich_tag_site_lit.py --candidate-id l1-p1037
    uv run python scripts/enrich_tag_site_lit.py --gene KCNN2 --no-publish
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import logging
import os
import sys
from collections import defaultdict
from typing import Any

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.agents.tag_site.enrichment import seen_key  # noqa: E402
from accessible_surfaceome.agents.tag_site.frames import Frame  # noqa: E402
from accessible_surfaceome.agents.tag_site.member_frames import (  # noqa: E402
    Member,
    MemberFrame,
    load_members,
    loop_inventory,
    resolve_member_frame,
)
from accessible_surfaceome.agents.tag_site.prior_ledger import (  # noqa: E402
    parse_prior_clips,
)
from accessible_surfaceome.agents.tag_site.prompt import prompt_sha  # noqa: E402
from accessible_surfaceome.agents.tag_site.runner import (  # noqa: E402
    run_tag_site_agent,
    to_viewer_sites,
)
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.cloud.tag_site_genes import (  # noqa: E402
    publish_gene_rows,
    row_for as gene_row_for,
    searched_members,
)
from accessible_surfaceome.paths import REPO_ROOT  # noqa: E402

MEMBERS_TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
COHORT_TSV = (
    REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
)
#: Shape of a UniProt accession, optionally isoform-suffixed.
_UNIPROT = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9](-\d+)?$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}(-\d+)?$"
)
RUNS_DIR = REPO_ROOT / "data/external/tag_site_runs"
ENRICHED_PROVENANCE = "literature_enriched"
RUN_SERIES = os.environ.get("TAG_SITE_RUN_SERIES", "literature_enriched_v1")
RUN_ID = os.environ.get("TAG_SITE_RUN_ID", "tag_site_enrichment_v1")

log = logging.getLogger("enrich_tag_site_lit")

#: D1 caps bound parameters per query at 100.
_CHUNK = 60
#: For a query that binds the SAME list twice — ``uniprot_acc IN (...) OR
#: uniprot_acc_full IN (...)`` — the budget is halved, so the chunk must be
#: under 50. At _CHUNK it binds 120 and D1 answers "too many SQL variables".
_CHUNK_DOUBLED = 45


def _chunks(xs: list[Any], n: int = _CHUNK):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def resolve_frames(
    members: list[Member], *, pub: D1Client, accessions: dict[str, str]
) -> tuple[dict[str, MemberFrame], dict[str, list[Frame]], list[Member]]:
    """Per candidate_id: the member's own frame, and the alternates a citation
    might be numbering in. Returns ``(frames, alternates, unresolved)``.

    Candidates are matched on ``uniprot_acc`` **or** ``uniprot_acc_full``, which
    is what covers base accessions, isoform-suffixed ones and designed-ORF
    candidate ids without the caller needing to know which it holds. A member
    whose sha256 matches nothing is returned as unresolved and SKIPPED — never
    silently handed the canonical, which is how a cassette lands in a different
    protein.
    """
    accs = sorted({m.topology_acc for m in members})
    rows: dict[str, list[dict]] = defaultdict(list)
    # Sibling frames key on the RESOLVED accession. Splitting topology_acc
    # yields "l1" for a designed-ORF member, so those 24 would get no sibling
    # frames at all — including no canonical, which is the single frame their
    # citations are most likely to be using.
    bases = sorted({a for a in accessions.values() if a})
    for chunk in _chunks(accs, _CHUNK_DOUBLED):
        marks = ", ".join(["?"] * len(chunk))
        for r in pub.query(
            f"SELECT uniprot_acc, uniprot_acc_full, is_canonical, sequence, "
            f"per_residue_topology, signal_peptide_length FROM topology_public "
            f"WHERE uniprot_acc IN ({marks}) OR uniprot_acc_full IN ({marks});",
            chunk + chunk,
        ):
            for key in {r["uniprot_acc"], r["uniprot_acc_full"]}:
                rows[key].append(r)
    # Siblings for the alternate frames, keyed on the BASE accession.
    sib: dict[str, list[dict]] = defaultdict(list)
    for chunk in _chunks(bases):
        marks = ", ".join(["?"] * len(chunk))
        for r in pub.query(
            f"SELECT uniprot_acc, uniprot_acc_full, is_canonical, sequence, "
            f"per_residue_topology, signal_peptide_length FROM topology_public "
            f"WHERE uniprot_acc IN ({marks}) "
            f"AND cohort IN ('human_canonical', 'human_isoforms');",
            chunk,
        ):
            sib[r["uniprot_acc"]].append(r)

    frames: dict[str, MemberFrame] = {}
    alternates: dict[str, list[Frame]] = {}
    unresolved: list[Member] = []
    for m in members:
        cands = [
            (r["uniprot_acc_full"], r["sequence"], r["per_residue_topology"])
            for r in rows.get(m.topology_acc, [])
        ]
        fr = resolve_member_frame(m, candidates=cands)
        if fr is None:
            unresolved.append(m)
            continue
        frames[m.candidate_id] = fr
        alts: list[Frame] = [
            Frame(label="member", sequence=fr.sequence, offset=0)
        ]
        # topology_public holds roughly two rows per accession (topology
        # vintages), so the same frame would otherwise be added twice and
        # compete with itself in the hit ranking.
        seen_labels: set[str] = {"member"}

        def _add(frame: Frame) -> None:
            if frame.label in seen_labels or not frame.sequence:
                return
            seen_labels.add(frame.label)
            alts.append(frame)

        base = accessions.get(m.candidate_id, "")
        for r in sib.get(base, []):
            if not r["sequence"] or r["sequence"] == fr.sequence:
                continue
            if r["is_canonical"]:
                # Canonical is where papers number, so it is EXPECTED rather
                # than a suspicious alternate — licensed by the strength of its
                # mapping instead of by frame keywords.
                _add(Frame(label="canonical", sequence=r["sequence"],
                           offset=None, expected=True))
                sp = r["signal_peptide_length"] or 0
                if sp:
                    _add(Frame(label="mature", sequence=r["sequence"][sp:],
                               offset=None))
            else:
                _add(Frame(label=f"isoform:{r['uniprot_acc_full']}",
                           sequence=r["sequence"], offset=None))
        alternates[m.candidate_id] = alts
    return frames, alternates, unresolved


def canonical_accessions(members: list[Member], *, pub: D1Client) -> dict[str, str]:
    """``candidate_id -> the gene's canonical UniProt accession``.

    For 542 of the 566 members ``topology_acc`` already IS an accession (base or
    isoform-suffixed), so the base is just the prefix. For the 24
    ``library_designed_orf`` members it is the CANDIDATE ID, because no UniProt
    record exists for that form — and the accession is still needed, for the
    search vocabulary, for the record's provenance, and to find the sibling
    frames a citation might be numbering in.

    Resolved through the **HGNC-ID path**, never from the gene symbol. A bare
    symbol silently resolves to the wrong protein for a small but real subset of
    human genes — the COX1 (cyclooxygenase vs mitochondrial cytochrome c
    oxidase) and WAS (Wiskott-Aldrich vs the MT-RNR1 rRNA) class — and this
    pipeline exists because a position in the wrong protein is invisible
    downstream. gene_symbol -> hgnc_id comes from the cohort file, which has
    100% hgnc_id coverage; hgnc_id -> uniprot_acc comes from
    gene_identifier_public, which is the documented only path for stable-ID
    lookups.
    """
    out: dict[str, str] = {}
    needs: dict[str, list[Member]] = defaultdict(list)
    for m in members:
        if _UNIPROT.match(m.topology_acc):
            out[m.candidate_id] = m.topology_acc.split("-")[0]
        else:
            needs[m.gene_symbol].append(m)
    if not needs:
        return out

    hgnc: dict[str, str] = {}
    with COHORT_TSV.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["gene_symbol"] in needs and row.get("hgnc_id"):
                hgnc[row["gene_symbol"]] = row["hgnc_id"]
    by_hgnc: dict[str, str] = {}
    ids = sorted(set(hgnc.values()))
    for chunk in _chunks(ids):
        marks = ", ".join(["?"] * len(chunk))
        for r in pub.query(
            f"SELECT hgnc_id, uniprot_acc FROM gene_identifier_public "
            f"WHERE hgnc_id IN ({marks});",
            chunk,
        ):
            if r["uniprot_acc"]:
                by_hgnc[r["hgnc_id"]] = r["uniprot_acc"]
    for gene, ms in needs.items():
        acc = by_hgnc.get(hgnc.get(gene, ""))
        for m in ms:
            if acc:
                out[m.candidate_id] = acc
            else:
                log.error(
                    "  %s / %s: no accession via hgnc_id (%s) — cannot build the "
                    "search vocabulary or the sibling frames",
                    gene, m.candidate_id, hgnc.get(gene) or "no hgnc_id",
                )
    return out


def prior_state(
    gene: str, *, pri: D1Client, pub: D1Client
) -> tuple[list, set[str], set[int]]:
    """``(prior_clips, seen_keys, covered_junctions)`` for one gene.

    ``seen_keys`` is only what an earlier run CITED, because v1 never persisted
    its menus — so the first enrichment run re-examines some already-seen text
    once and never again. A bounded, known cost rather than a silent one.
    """
    rows = pri.query(
        "SELECT run_id, ledger_json FROM tag_site_run "
        "WHERE gene_symbol = ? AND run_id != ?;",
        [gene, RUN_ID],
    )
    clips = parse_prior_clips(rows)
    seen = {seen_key(c.source_id, c.quote) for c in clips}
    covered = {
        r["insert_after_residue"]
        for r in pub.query(
            "SELECT DISTINCT insert_after_residue FROM tag_site_public "
            "WHERE gene_symbol = ? AND insert_after_residue IS NOT NULL;",
            [gene],
        )
    }
    return clips, seen, covered


def uniprot_names(acc: str) -> tuple[str, list[str], int]:
    """protein_name, aliases, signal-peptide end — reused from the control
    driver so both passes search on the same vocabulary."""
    # Bare sibling import: scripts/ is on sys.path when this runs as a script,
    # which is how regenerate_tag_sites.py already reaches this same module.
    # Both passes must search on identical vocabulary, so this is shared rather
    # than reimplemented.
    import regenerate_tag_site_lit as lit  # noqa: PLC0415

    name, cands, sp_end = lit.fetch_uniprot_names(acc)
    return name, lit.build_aliases("", name, cands), sp_end


def searched_row(
    m: Member,
    result: Any,
    sites: list[dict[str, Any]],
    *,
    base_acc: str,
    run_series: str,
    n_papers: int | None = None,
) -> dict[str, Any] | None:
    """The "we searched this member, under this prompt, on this date" row.

    Stamped at run time rather than recovered later by a snapshot pass, for two
    reasons: these records live in D1 and only three viewer snapshots are
    committed, so a snapshot-scoped pass would reach almost none of them; and
    the sweep's resume reads exactly this row, so a pass that does not write it
    has an empty skip set forever and re-runs the whole cohort on every resume.

    ``None`` when the run never reached the model (no ``prompt_sha``) — dating a
    search that was not made would make the next resume skip the member for
    good.
    """
    return gene_row_for(
        {
            "gene_symbol": m.gene_symbol,
            "candidate_id": m.candidate_id,
            "run_series": run_series,
            "uniprot_acc": base_acc,
            "generated_at": getattr(result, "generated_at", "") or "",
            "prompt_sha": getattr(result, "prompt_sha", "") or "",
            "prompt_version": getattr(result, "prompt_version", "") or "",
            "model": getattr(result, "model", "") or "",
            "schema_version": getattr(result, "schema_version", "") or "",
            "literature_other_positions": [
                o if isinstance(o, dict) else o.model_dump()
                for o in (getattr(result, "other_positions", None) or [])
            ],
            "literature_notes": getattr(result, "notes", "") or "",
            "sites": sites,
        },
        version=run_series,
        n_papers=n_papers,
        provenance=ENRICHED_PROVENANCE,
    )


def enrich_member(
    m: Member,
    fr: MemberFrame,
    alts: list[Frame],
    *,
    base_acc: str,
    pri: D1Client,
    pub: D1Client,
    dry_run: bool,
    publish: bool,
    run_series: str = RUN_SERIES,
) -> dict[str, Any]:
    name, aliases, sp_end = uniprot_names(base_acc)
    clips, seen, covered = prior_state(m.gene_symbol, pri=pri, pub=pub)
    inventory = loop_inventory(m, fr.topology)
    log.info(
        "  %s / %s: %d prior clip(s), %d seen, %d covered junction(s)",
        m.gene_symbol, m.candidate_id, len(clips), len(seen), len(covered),
    )
    log.info("  %s: %s", m.candidate_id, inventory)
    if dry_run:
        return {"candidate_id": m.candidate_id, "dry_run": True,
                "n_prior": len(clips), "n_covered": len(covered)}

    usage: list[Any] = []
    inter: dict[str, Any] = {}
    result = run_tag_site_agent(
        usage_sink=usage,
        intermediates=inter,
        gene_symbol=m.gene_symbol,
        protein_name=name,
        uniprot_accession=base_acc,
        aliases=aliases,
        sequence=fr.sequence,
        topology=fr.topology,
        sp_end=sp_end,
        mode="production",
        loop_inventory=inventory,
        prior_clips=clips,
        seen_keys=seen,
        covered_junctions=covered,
        numbered_against=fr.numbered_against,
        alternate_frames=alts,
        frame_label="member",
        select_max_batches=4,
        faceted_discovery=True,
    )
    cost = sum(getattr(u, "cost_usd", 0.0) or 0.0 for u in usage)
    inter["cost_usd"] = round(cost, 4)
    inter["candidate_id"] = m.candidate_id
    inter["run_series"] = run_series
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{m.candidate_id}.json").write_text(
        json.dumps(inter, indent=2, default=str)
    )
    log.info("  %s COST: $%.4f  outcome=%s  sites=%d",
             m.candidate_id, cost, inter.get("outcome"), len(result.sites))

    sites = to_viewer_sites(
        result,
        uniprot_acc=base_acc,
        provenance=ENRICHED_PROVENANCE,
        candidate_id=m.candidate_id,
        library=m.library,
        numbered_against=fr.numbered_against,
        topology=fr.topology,
    )
    if publish:
        from accessible_surfaceome.cloud.tag_sites import publish_tag_sites

        # The provenance scope is passed EXPLICITLY. An empty site list would
        # otherwise infer an empty scope and clear nothing, so a member that no
        # longer stands behind a previous enriched site could never retract it.
        n = publish_tag_sites(
            {
                "has_data": bool(sites),
                "gene_symbol": m.gene_symbol,
                "uniprot_acc": base_acc,
                "sites": sites,
            },
            tag_sites_version=run_series,
            client=pub,
            provenances=[ENRICHED_PROVENANCE],
        )
        log.info("  %s: published %d enriched row(s)", m.candidate_id, n)

        # And the fact that we LOOKED. Without this row a member that found
        # nothing is indistinguishable from one never run, so the sweep's skip
        # set stays empty and every resume re-runs the cohort.
        srow = searched_row(
            m, result, sites, base_acc=base_acc, run_series=run_series,
            n_papers=inter.get("n_papers"),
        )
        if srow is not None:
            publish_gene_rows([srow], client=pub)
    return {
        "candidate_id": m.candidate_id,
        "gene_symbol": m.gene_symbol,
        "cost_usd": round(cost, 4),
        "outcome": inter.get("outcome"),
        "n_sites": len(sites),
        "n_new_clips": inter.get("n_new_clips"),
        "n_carried": inter.get("n_carried"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gene", action="append", metavar="SYMBOL")
    ap.add_argument("--candidate-id", action="append", metavar="ID")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve frames and prior state, print the plan, spend nothing")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--run-series", default=RUN_SERIES,
                    help="which search series this run writes and resumes against")
    ap.add_argument("--resume", action="store_true",
                    help="skip members already searched in this series under the "
                         "CURRENT prompt_sha (one archived under a different sha is "
                         "stale and re-runs)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    members = load_members(MEMBERS_TSV)
    if args.gene:
        want = {g.upper() for g in args.gene}
        members = [m for m in members if m.gene_symbol.upper() in want]
    if args.candidate_id:
        want_c = set(args.candidate_id)
        members = [m for m in members if m.candidate_id in want_c]
    if args.limit:
        members = members[: args.limit]
    if not members:
        log.error("no members selected")
        return 1
    log.info("%d member(s) across %d gene(s)",
             len(members), len({m.gene_symbol for m in members}))

    with D1Client.public() as pub, D1Client() as pri:
        if args.resume:
            # Sha-aware: a member archived under a DIFFERENT prompt is stale
            # and runs again, so a prompt edit reaches the rows it invalidated
            # without anyone having to remember a flag.
            done = searched_members(
                pub, run_series=args.run_series, prompt_sha=prompt_sha()
            )
            before = len(members)
            members = [
                m for m in members
                if (m.gene_symbol, m.candidate_id) not in done
            ]
            log.info("resume: %d searched under this sha; %d of %d pending",
                     len(done), len(members), before)
            if not members:
                log.info("nothing to do")
                return 0

        accs = canonical_accessions(members, pub=pub)
        frames, alternates, unresolved = resolve_frames(
            members, pub=pub, accessions=accs
        )
        log.info("resolved %d/%d member frames by sha256", len(frames), len(members))
        for m in unresolved:
            # Skip and report. A member handed the canonical instead would be
            # numbered against a different protein, with a plausible length.
            log.error("  SKIP %s / %s: no topology row matching sha256 %s (cohort %s)",
                      m.gene_symbol, m.candidate_id, m.sequence_sha256[:12],
                      m.topology_cohort)

        results = []
        for m in members:
            fr = frames.get(m.candidate_id)
            base_acc = accs.get(m.candidate_id)
            if fr is None or not base_acc:
                continue
            log.info("\n=== %s / %s ===", m.gene_symbol, m.candidate_id)
            try:
                results.append(
                    enrich_member(
                        m, fr, alternates[m.candidate_id], base_acc=base_acc,
                        pri=pri, pub=pub,
                        dry_run=args.dry_run, publish=not args.no_publish,
                        run_series=args.run_series,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - report per member, keep going
                log.exception("  %s FAILED: %s", m.candidate_id, exc)
                results.append({"candidate_id": m.candidate_id, "error": str(exc)})

    print("\n" + "=" * 78)
    print(f"ENRICHMENT{'  [DRY RUN]' if args.dry_run else ''}")
    print("=" * 78)
    total = 0.0
    for r in results:
        total += r.get("cost_usd") or 0.0
        print("  " + json.dumps(r, default=str))
    print(f"\n  {len(results)} member(s), {len(unresolved)} skipped, "
          f"total ${total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
