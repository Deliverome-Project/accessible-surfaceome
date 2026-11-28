"""Empirical evaluation & before-vs-after benchmark for the tag-site literature
pipeline on L1 internal-site members and curated internal positive controls.

NEVER mutates D1 (strictly read-only D1 baseline + local JSON/Markdown report).

Examples:
    uv run python scripts/benchmark_tag_site_internal_lit.py \
        --mode l1-recovery --genes KCNN3,TSPAN4,SLC4A3,SLC16A3,KCND2,SV2A,SLC12A5,AQP4

    uv run python scripts/benchmark_tag_site_internal_lit.py \
        --mode controls --genes SLC5A6,AQP1,SLC19A1,PMP22,VANGL1,SLC4A1,KCNQ1,CFTR
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from accessible_surfaceome.env import load_env

load_env()

import importlib.util  # noqa: E402
from accessible_surfaceome.agents._support.client import get_client  # noqa: E402
from accessible_surfaceome.agents.tag_site.benchmark import (  # noqa: E402
    load_controls,
    score_predictions,
)
from accessible_surfaceome.agents.tag_site.frames import Frame  # noqa: E402
from accessible_surfaceome.agents.tag_site.member_frames import (  # noqa: E402
    Member,
    MemberFrame,
    load_members,
    loop_inventory,
)
from accessible_surfaceome.agents.tag_site.ortholog_frames import (  # noqa: E402
    build_aliases,
    fetch_rodent_ortholog_frames,
    fetch_uniprot_names_cached,
)
from accessible_surfaceome.agents.tag_site.runner import (  # noqa: E402
    DEFAULT_TAG_SITE_MODEL,
    DEFAULT_TAG_SITE_TRIAGE_MODEL,
    DEFAULT_TAG_SITE_WEB_SCOUT_MODEL,
    WebSearchMode,
    run_tag_site_agent,
    to_viewer_sites,
)
from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402
from accessible_surfaceome.paths import REPO_ROOT  # noqa: E402
from accessible_surfaceome.tools._shared.http import open_default_client  # noqa: E402


def _load_enrich_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "enrich_tag_site_lit", REPO_ROOT / "scripts/enrich_tag_site_lit.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

log = logging.getLogger("benchmark_tag_site_internal_lit")

CONTROLS_TSV = REPO_ROOT / "data/tag_sites/positive_controls.tsv"
MEMBERS_TSV = REPO_ROOT / "data/tag_sites/l1_internal_members.tsv"
DEFAULT_OUT_DIR = REPO_ROOT / "data/runs/tag_site_eval"

# Default L1 recovery panel: pilot failures/region-only genes + never-searched +
# rodent-numbered / hard internal-loop channels & transporters.
DEFAULT_L1_RECOVERY_GENES = [
    "KCNN3",
    "TSPAN4",
    "SLC4A3",
    "SLC16A3",
    "ATP2B1",
    "SLC2A2",
    "AQP4",
    "SCARB1",
    "SERINC2",
    "KCND2",
    "SV2A",
    "SLC12A5",
]


def _load_d1_baseline(pub: D1Client, genes: list[str]) -> dict[str, dict[str, Any]]:
    """Read current live D1 literature sites per gene for before-vs-after diff."""
    out: dict[str, dict[str, Any]] = {
        g: {
            "n_total_lit": 0,
            "n_pinned_internal": 0,
            "n_validated_internal": 0,
            "n_unpinned_internal": 0,
            "pinned_residues": [],
            "provenances": [],
        }
        for g in genes
    }
    for i in range(0, len(genes), 50):
        chunk = genes[i : i + 50]
        marks = ", ".join(["?"] * len(chunk))
        rows = pub.query(
            f"SELECT gene_symbol, provenance, site_kind, insert_after_residue, "
            f"extracellular, compartment, position_evidence, validation_level "
            f"FROM tag_site_public "
            f"WHERE gene_symbol IN ({marks}) "
            f"AND provenance IN ('literature_retrieved', 'literature_enriched');",
            chunk,
        )
        for r in rows:
            g = r["gene_symbol"]
            b = out.setdefault(
                g,
                {
                    "n_total_lit": 0,
                    "n_pinned_internal": 0,
                    "n_validated_internal": 0,
                    "n_unpinned_internal": 0,
                    "pinned_residues": [],
                    "provenances": [],
                },
            )
            b["n_total_lit"] += 1
            if r["provenance"] not in b["provenances"]:
                b["provenances"].append(r["provenance"])
            if r["site_kind"] == "internal":
                is_ec = bool(r.get("extracellular")) or r.get("compartment") == "extracellular"
                if r["insert_after_residue"] is not None and is_ec:
                    b["n_pinned_internal"] += 1
                    b["pinned_residues"].append(int(r["insert_after_residue"]))
                    if r["position_evidence"] == "validated":
                        b["n_validated_internal"] += 1
                elif r["insert_after_residue"] is None:
                    b["n_unpinned_internal"] += 1
    for b in out.values():
        b["pinned_residues"] = sorted(set(b["pinned_residues"]))
    return out


def _eval_one_member(
    m: Member,
    fr: MemberFrame,
    alts: list[Frame],
    *,
    base_acc: str,
    model: str,
    triage_model: str,
    web_scout_model: str,
    web_search_mode: str,
    faceted: bool,
    follow_refs: bool,
    include_rodents: bool,
) -> dict[str, Any]:
    t0 = time.monotonic()
    client = get_client()
    with open_default_client() as http:
        name, cands, sp_end = fetch_uniprot_names_cached(base_acc, http=http)
        aliases = build_aliases("", name, cands)
        full_alts = list(alts)
        if include_rodents:
            existing_seqs = {f.sequence for f in full_alts if f.sequence}
            full_alts.extend(
                fetch_rodent_ortholog_frames(
                    m.gene_symbol, http=http, exclude_sequences=existing_seqs
                )
            )
        inv = loop_inventory(m, fr.topology)
        usage: list[Any] = []
        inter: dict[str, Any] = {}
        result = run_tag_site_agent(
            client=client,
            http=http,
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
            loop_inventory=inv,
            numbered_against=fr.numbered_against,
            alternate_frames=full_alts,
            frame_label="member",
            select_max_batches=4,
            faceted_discovery=faceted,
            web_search_mode=cast(WebSearchMode, web_search_mode),
            model=model,
            triage_model=triage_model,
            web_scout_model=web_scout_model,
            follow_construct_refs=follow_refs,
        )
        sites = to_viewer_sites(
            result,
            uniprot_acc=base_acc,
            provenance="literature_enriched",
            candidate_id=m.candidate_id,
            library=m.library,
            numbered_against=fr.numbered_against,
            topology=fr.topology,
        )

    cost = round(sum(getattr(u, "cost_usd", 0.0) or 0.0 for u in usage), 4)
    # Strictly count extracellular internal loop sites (never cytoplasmic/TM or terminal).
    ec_internal_pinned = [
        s
        for s in sites
        if s.get("insert_after_residue") is not None
        and s.get("site_kind") == "internal"
        and bool(s.get("extracellular"))
    ]
    non_ec_or_terminal = [
        s
        for s in sites
        if s.get("insert_after_residue") is not None
        and not (s.get("site_kind") == "internal" and bool(s.get("extracellular")))
    ]
    pinned = sorted({int(s["insert_after_residue"]) for s in ec_internal_pinned})
    validated_pinned = sorted(
        {
            int(s["insert_after_residue"])
            for s in ec_internal_pinned
            if s.get("position_evidence") == "validated"
        }
    )
    unpinned = sum(
        1
        for s in sites
        if s.get("insert_after_residue") is None and s.get("site_kind") == "internal"
    )
    return {
        "candidate_id": m.candidate_id,
        "gene_symbol": m.gene_symbol,
        "species": m.species,
        "topology_cohort": m.topology_cohort,
        "outcome": inter.get("outcome"),
        "n_papers": inter.get("n_papers", 0),
        "n_papers_fetched": inter.get("n_papers_fetched", 0),
        "n_clips": inter.get("n_clips", 0),
        "n_boosted": inter.get("n_boosted", 0),
        "web_search_used": inter.get("web_search_used", False),
        "web_search_reason": inter.get("web_search_reason"),
        "followup_ref_ids": inter.get("followup_ref_ids", []),
        "n_refusals": inter.get("n_refusals", 0),
        "cache_read_tokens": inter.get("cache_read_tokens", 0),
        "n_sites": len(sites),
        "pinned_residues": pinned,
        "validated_pinned_residues": validated_pinned,
        "n_unpinned": unpinned,
        "n_non_ec_or_terminal": len(non_ec_or_terminal),
        "position_frames": sorted({s["position_frame"] for s in sites if s.get("position_frame")}),
        "validation_levels": [s.get("validation_level") for s in sites],
        "sites": sites,
        "notes": result.notes,
        "cost_usd": cost,
        "elapsed_s": round(time.monotonic() - t0, 1),
    }


def _render_markdown(
    rows: list[dict[str, Any]],
    baselines: dict[str, dict[str, Any]],
    *,
    controls_summary: dict[str, Any] | None = None,
) -> str:
    lines = [
        "# Tag-Site Extracellular Internal-Loop Recovery Evaluation",
        "",
        f"Evaluated **{len(rows)}** member(s) (`--no-publish`, zero D1 writes; counts strictly extracellular internal loop sites where `site_kind == 'internal'` and `extracellular == True`).",
        "",
        "| Gene | Member | Before pinned EC (D1) | After pinned EC | After validated EC | Unpinned | Papers / Fetched / Clips | Ref follow-up | Refusals | Cost |",
        "|---|---|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    total_cost = 0.0
    before_any_pinned = 0
    after_any_pinned = 0
    newly_pinned = 0
    before_any_val = 0
    after_any_val = 0
    for r in rows:
        g = r["gene_symbol"]
        b = baselines.get(g, {})
        b_pin = b.get("pinned_residues") or []
        a_pin = r.get("pinned_residues") or []
        a_val = r.get("validated_pinned_residues") or []
        if b_pin:
            before_any_pinned += 1
        if a_pin:
            after_any_pinned += 1
        if a_pin and not b_pin:
            newly_pinned += 1
        if b.get("n_validated_internal", 0) > 0:
            before_any_val += 1
        if a_val:
            after_any_val += 1
        total_cost += float(r.get("cost_usd", 0.0) or 0.0)
        lines.append(
            f"| {g} | `{r['candidate_id']}` | `{b_pin}` | `{a_pin}` | `{a_val}` | "
            f"{r.get('n_unpinned', 0)} | {r.get('n_papers', 0)} / {r.get('n_papers_fetched', 0)} / {r.get('n_clips', 0)} | "
            f"{len(r.get('followup_ref_ids') or [])} | {r.get('n_refusals', 0)} | ${r.get('cost_usd', 0.0):.3f} |"
        )
    mean_cost = total_cost / max(1, len(rows))
    lines += [
        "",
        "## Summary",
        f"- Members with ≥1 pinned internal site: **{before_any_pinned}/{len(rows)}** (D1 baseline) → **{after_any_pinned}/{len(rows)}** (new pipeline; **+{newly_pinned}** newly pinned)",
        f"- Members with ≥1 validated pinned site: **{before_any_val}/{len(rows)}** (D1 baseline) → **{after_any_val}/{len(rows)}** (new pipeline)",
        f"- Total cost: **${total_cost:.2f}** (mean **${mean_cost:.3f}/member**)",
    ]
    if controls_summary:
        lines += [
            "",
            "## Internal Positive Controls Score",
            f"- Exact: **{controls_summary['n_exact']}/{controls_summary['n_total']}**, "
            f"Near (±1): **{controls_summary['n_near']}**, Miss: **{controls_summary['n_miss']}**",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("l1-recovery", "controls"), default="l1-recovery")
    ap.add_argument("--genes", default="", help="Comma-separated gene symbols")
    ap.add_argument("--candidate-ids", default="", help="Comma-separated L1 candidate IDs")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--web-search-mode", choices=("always", "adaptive", "off"), default="adaptive")
    ap.add_argument("--model", default=DEFAULT_TAG_SITE_MODEL)
    ap.add_argument("--triage-model", default=DEFAULT_TAG_SITE_TRIAGE_MODEL)
    ap.add_argument("--web-scout-model", default=DEFAULT_TAG_SITE_WEB_SCOUT_MODEL)
    ap.add_argument("--no-faceted", action="store_true")
    ap.add_argument("--no-ref-followup", action="store_true")
    ap.add_argument("--no-rodents", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--run-name", default="")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    all_members = load_members(MEMBERS_TSV)
    by_gene: dict[str, list[Member]] = {}
    for m in all_members:
        by_gene.setdefault(m.gene_symbol.upper(), []).append(m)

    selected: list[Member] = []
    controls = [c for c in load_controls(CONTROLS_TSV) if c.site_kind == "internal"]
    if args.candidate_ids:
        want_cids = {x.strip() for x in args.candidate_ids.split(",") if x.strip()}
        selected = [m for m in all_members if m.candidate_id in want_cids]
    else:
        if args.genes:
            want_genes = [g.strip().upper() for g in args.genes.split(",") if g.strip()]
        elif args.mode == "controls":
            want_genes = list(dict.fromkeys(c.gene_symbol.upper() for c in controls))
        else:
            want_genes = list(DEFAULT_L1_RECOVERY_GENES)
        for g in want_genes:
            # Prefer human canonical member when a gene has multiple L1 members
            cands = by_gene.get(g, [])
            if cands:
                human = [m for m in cands if m.species == "human"]
                selected.append((human or cands)[0])
            else:
                log.warning("Gene %s not in l1_internal_members.tsv — skipping", g)

    if args.limit > 0:
        selected = selected[: args.limit]
    if not selected:
        log.error("No members selected")
        return 1

    enrich = _load_enrich_module()
    with D1Client.public() as pub:
        accs = enrich.canonical_accessions(selected, pub=pub)
        frames, alternates, unresolved = enrich.resolve_frames(
            selected, pub=pub, accessions=accs
        )
        baselines = _load_d1_baseline(pub, [m.gene_symbol for m in selected])

    if unresolved:
        log.warning("Unresolved in topology_public: %s", [m.candidate_id for m in unresolved])

    runnable = [m for m in selected if m.candidate_id in frames and m.candidate_id in accs]
    log.info("Running evaluation on %d member(s) (parallel=%d, model=%s, triage=%s)",
             len(runnable), args.parallel, args.model, args.triage_model)

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        futs = {
            ex.submit(
                _eval_one_member,
                m,
                frames[m.candidate_id],
                alternates[m.candidate_id],
                base_acc=accs[m.candidate_id],
                model=args.model,
                triage_model=args.triage_model,
                web_scout_model=args.web_scout_model,
                web_search_mode=args.web_search_mode,
                faceted=not args.no_faceted,
                follow_refs=not args.no_ref_followup,
                include_rodents=not args.no_rodents,
            ): m
            for m in runnable
        }
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                r = fut.result()
                results.append(r)
                log.info(
                    "  DONE %-10s (%s) pinned=%s val=%s unpinned=%d papers=%d fetched=%d clips=%d cost=$%.3f (%.0fs)",
                    r["gene_symbol"],
                    r["candidate_id"],
                    r["pinned_residues"],
                    r["validated_pinned_residues"],
                    r["n_unpinned"],
                    r["n_papers"],
                    r["n_papers_fetched"],
                    r["n_clips"],
                    r["cost_usd"],
                    r["elapsed_s"],
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("  FAIL %s (%s): %s", m.gene_symbol, m.candidate_id, exc)
                results.append(
                    {
                        "candidate_id": m.candidate_id,
                        "gene_symbol": m.gene_symbol,
                        "error": str(exc),
                        "pinned_residues": [],
                        "validated_pinned_residues": [],
                        "cost_usd": 0.0,
                    }
                )

    order = {m.candidate_id: i for i, m in enumerate(runnable)}
    results.sort(key=lambda r: order.get(r["candidate_id"], 9999))

    controls_summary: dict[str, Any] | None = None
    eval_genes = {r["gene_symbol"] for r in results}
    relevant_controls = [c for c in controls if c.gene_symbol in eval_genes]
    if relevant_controls:
        pred_by_gene = {r["gene_symbol"]: r.get("pinned_residues", []) for r in results}
        rep = score_predictions(pred_by_gene, relevant_controls, tolerance=1)
        controls_summary = {
            "n_exact": rep.n_exact,
            "n_near": rep.n_near,
            "n_miss": rep.n_miss,
            "n_total": rep.n_total,
            "outcomes": rep.outcomes,
        }

    run_name = args.run_name or datetime.now(UTC).strftime(f"{args.mode}_%Y%m%d_%H%M%S")
    out_dir = args.out_dir / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(
            {
                "run_name": run_name,
                "mode": args.mode,
                "model": args.model,
                "triage_model": args.triage_model,
                "web_scout_model": args.web_scout_model,
                "web_search_mode": args.web_search_mode,
                "baselines": baselines,
                "results": results,
                "controls_summary": controls_summary,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    md = _render_markdown(results, baselines, controls_summary=controls_summary)
    (out_dir / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"Saved report -> {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
