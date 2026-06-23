"""Durable 4-bucket OA-fetch probe for paywall+bot-block analysis.

Per-gene incremental JSONL writer with resume capability. Supports two
source backends:

* ``--source production`` — production search chain (EuropePMC + PubTator +
  NCBI gene2pubmed + topic_search axes from the kickoff template).
* ``--source openalex`` — broader literature surface via OpenAlex (catches
  bioRxiv/medRxiv/Chemxiv preprints, non-PubMed journals, and grey lit
  that EuropePMC doesn't index).

Both backends run the same ``_fetch_body_drafts`` classifier against the
sampled papers, so the per-bucket counts are directly comparable.
Union analysis happens in ``scripts/union_oa_probes.py`` afterward.

Usage:
    uv run python scripts/probe_oa_buckets.py --source production --n-genes 100 --papers-per-gene 10
    uv run python scripts/probe_oa_buckets.py --source openalex   --n-genes 100 --papers-per-gene 10

Output goes to ``data/analysis/paywall_bot_block/probe_results/cohort{N}x{K}_{source}.jsonl``
— one JSON object per gene. Re-running with the same args resumes from
where it left off (genes already in the output file are skipped).
"""
from __future__ import annotations
import argparse
import csv
import json
import random
import re
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import httpx

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    _fetch_body_drafts,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.models import Paper
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex
from accessible_surfaceome.tools.evidence_retrieval import evidence_retrieval
from accessible_surfaceome.tools.gene_literature import gene_literature
from accessible_surfaceome.tools.gene_lookup import resolve

# Production A1 evidence_retrieval categories (mirrors
# kickoff_templates.py::_A1_CATEGORIES). Each one issues an EuropePMC
# search tuned to a specific assay/method keyword set.
_A1_EVIDENCE_CATEGORIES = (
    "ihc", "if", "flow_cytometry", "surface_biotinylation",
    "mass_spec_surfaceome", "shedding", "overexpression",
    "western_blot_paired", "structure_with_ecd", "other",
)

# Empirically-verified bot-block host list (HEAD-tested 2026-06-07 +
# 50-paper thorough probe finds). Each one returns 403 to our polite UA.
BOT_BLOCKED = re.compile(
    r"(biorxiv\.org|medrxiv\.org|researchsquare\.com|"
    r"wiley\.com|onlinelibrary\.wiley|"
    r"ashpublications\.org|bloodjournal\.org|"
    r"sciencedirect\.com|linkinghub\.elsevier|"
    r"jbc\.org|"
    r"academic\.oup\.com|"
    r"mdpi\.com|"
    # 50-paper-probe additions:
    r"cell\.com|"
    r"ahajournals\.org|"
    r"jcs\.biologists\.org|"
    r"iiarjournals\.org|"
    r"nmd-journal\.com)",
    re.IGNORECASE,
)

# Topic anchors mirroring kickoff_templates.py (production parity for europepmc).
# The surface_method tuple is sourced from kickoff_templates._SURFACE_METHOD_ANCHORS:
# (surface_expression, flow_cytometry, surface_biotinylation, mass_spec_surfaceome, ihc).
# Order matches production for byte-identical EuropePMC query generation.
A1_TOPIC_AXES = [
    ("surface_method", ["surface_expression", "flow_cytometry", "surface_biotinylation", "mass_spec_surfaceome", "ihc"]),
    ("structure_topology", ["topology", "structure"]),
    ("shedding_ptm", ["shedding", "ptm"]),
]
STANDING_AXES = [
    ("normal_tissue_expression", ["normal_tissue_expression"]),
    ("surface_reachability", ["surface_reachability"]),
    ("partner_dependency", ["partner_dependency"]),
    ("membrane_subdomain", ["membrane_subdomain"]),
    ("epitope_masking", ["epitope_masking"]),
    ("cell_state_modulation", ["cell_state_modulation"]),
]

OPENALEX_BASE = "https://api.openalex.org"
UNPAYWALL_EMAIL = "rebeccacarlson95@gmail.com"
# OpenAlex pricing model (per docs as of 2026-06-07):
#   * Free tier: $1/day of free usage, resets at midnight UTC
#   * Search ops: $0.001 per call ($1 per 1,000)
#   * List+filter ops: $0.0001 per call ($0.10 per 1,000)
# Per-IP unauthenticated requests share a smaller bucket. With an API
# key, you get the full $1/day allowance via the "polite pool". The
# key goes into the URL as ?api_key=<KEY>. See:
#   https://developers.openalex.org/api-reference/authentication


def _openalex_url(query_str: str, cursor: str = "*", sort_param: str | None = None) -> str:
    """Build an OpenAlex /works URL. Appends ?api_key=<env:OPENALEX_API_KEY>
    when set, which puts the request in the authenticated $1/day polite pool
    instead of the smaller unauthenticated per-IP bucket."""
    import os
    url = (
        f"{OPENALEX_BASE}/works?"
        f"search={urllib.parse.quote(query_str)}"
        f"&per-page=100&cursor={cursor}"
        f"&select=id,doi,title,publication_year,ids,open_access,best_oa_location"
    )
    if sort_param:
        url += f"&sort={sort_param}"
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if api_key:
        url += f"&api_key={urllib.parse.quote(api_key)}"
    return url


def harvest_europepmc(hgnc_id, http, retraction_index):
    """Full mirror of production A1 kickoff: evidence_retrieval × 10
    categories + gene2pubmed + recent_corpus + 3 topic_search +
    6 standing axes. Same call paths the deep-dive pipeline runs."""
    from accessible_surfaceome.tools.gene_lookup import resolve_by_hgnc_id
    bundle = resolve_by_hgnc_id(hgnc_id, http=http)
    if not bundle.hgnc_symbol:
        return []
    seen, pool = set(), []
    def add_papers(papers):
        for p in papers:
            if p.pmid and p.pmid not in seen:
                seen.add(p.pmid)
                pool.append(p)
    def add(pack):
        add_papers(pack.papers)
    # 1. evidence_retrieval × 10 categories (discover_only — skip body-fetch
    #    + snippet extraction; we just want the candidate paper IDs)
    if bundle.uniprot_acc:
        for cat in _A1_EVIDENCE_CATEGORIES:
            try:
                pack = evidence_retrieval(
                    uniprot_acc=bundle.uniprot_acc,
                    category=cat,
                    http=http,
                    retraction_index=retraction_index,
                    discover_only=True,
                )
                add_papers(pack.papers)
            except Exception:
                pass
    # 2. gene2pubmed (NCBI ELink → EuropePMC bulk)
    if bundle.ncbi_gene_id:
        try:
            add(gene_literature(mode="gene2pubmed", http=http, ncbi_gene_id=int(bundle.ncbi_gene_id),
                                hgnc_symbol=bundle.hgnc_symbol, retraction_index=retraction_index))
        except Exception:
            pass
    # 3. recent_corpus (PubTator date-desc)
    try:
        add(gene_literature(mode="recent_corpus", http=http, uniprot_acc=bundle.uniprot_acc,
                            hgnc_symbol=bundle.hgnc_symbol, aliases=list(bundle.aliases),
                            retraction_index=retraction_index))
    except Exception:
        pass
    # 4. topic_search × (3 A1 + 6 standing) axes
    for _label, anchors in A1_TOPIC_AXES + STANDING_AXES:
        try:
            add(gene_literature(mode="topic_search", http=http, uniprot_acc=bundle.uniprot_acc,
                                hgnc_symbol=bundle.hgnc_symbol, aliases=list(bundle.aliases),
                                previous_symbols=list(bundle.previous_symbols),
                                topic_anchors=anchors, retraction_index=retraction_index))
        except Exception:
            pass
    return pool


def harvest_openalex(hgnc_symbol, aliases, previous_symbols, oa_client):
    """OpenAlex-backed harvest with TRUE 21-axis parity to production.

    Each of production's 21 search axes (build_a1_kickoff) maps to one
    OpenAlex axis below:

    Production axis (21)                   → OpenAlex equivalent
    --------------------------------------------------------------------
    1. gene2pubmed (broad gene recall)     → broad gene-name search
    2. recent_corpus (date-desc)           → broad gene-name + sort=date desc
    3-12. 10 evidence_retrieval categories → 10 gene+method-keyword searches
        (ihc, if, flow_cytometry, surface_biotinylation, mass_spec_surfaceome,
         shedding, overexpression, western_blot_paired, structure_with_ecd, other)
    13. topic_search: surface_method       → gene + surface-expression bundle
    14. topic_search: structure_topology   → gene + structure/topology
    15. topic_search: shedding_ptm         → gene + shedding/PTM
    16. standing: normal_tissue_expression → gene + tissue/atlas
    17. standing: surface_reachability     → gene + BBB/tumor-penetration
    18. standing: partner_dependency       → gene + co-receptor/chaperone
    19. standing: membrane_subdomain       → gene + raft/apical/ciliary
    20. standing: epitope_masking          → gene + epitope-masking/oligomer
    21. standing: cell_state_modulation    → gene + activation/induced
    """
    terms = [hgnc_symbol] + list(aliases or []) + list(previous_symbols or [])
    terms = sorted({t for t in terms if t and len(t) >= 3})
    if not terms:
        return []
    gene_q = " OR ".join(f'"{t}"' for t in terms[:5])

    # Per-axis method/topic keyword bundles. Each runs as (gene_q) AND (method_q)
    # except "broad" axes which use just gene_q.
    METHOD_AXES = [
        # 10 evidence_retrieval analogs
        ("ihc",                  '"immunohistochemistry" OR "IHC"'),
        ("if",                   '"immunofluorescence" OR "confocal"'),
        ("flow",                 '"flow cytometry" OR "FACS"'),
        ("biotinylation",        '"surface biotinylation" OR "sulfo-NHS"'),
        ("ms_surfaceome",        '"surfaceome" OR "cell surface capture" OR "mass spectrometry surfaceome"'),
        ("shedding",             '"ectodomain shedding" OR "sheddase" OR "ADAM10" OR "ADAM17"'),
        ("overexpression",       '"overexpression" OR "ectopic expression" OR "transient transfection"'),
        ("western_blot_paired",  '"western blot" OR "immunoblot"'),
        ("structure_with_ecd",   '"crystal structure" OR "cryo-EM" OR "extracellular domain" OR "ectodomain"'),
        ("other",                '"surface protein" OR "membrane protein" OR "plasma membrane"'),
        # 3 topic_search analogs
        ("surface_method",       '"surface expression" OR "cell-surface" OR "membrane localization"'),
        ("structure_topology",   '"topology" OR "transmembrane domain" OR "membrane topology"'),
        ("shedding_ptm",         '"shedding" OR "post-translational" OR "phosphorylation" OR "glycosylation"'),
        # 6 standing axes
        ("normal_tissue",        '"normal tissue" OR "expression atlas" OR "tissue distribution"'),
        ("surface_reachability", '"blood-brain barrier" OR "BBB" OR "tumor penetration" OR "luminal" OR "abluminal"'),
        ("partner_dependency",   '"co-receptor" OR "obligate partner" OR "chaperone" OR "escort"'),
        ("membrane_subdomain",   '"lipid raft" OR "apical membrane" OR "basolateral" OR "ciliary membrane" OR "synaptic membrane"'),
        ("epitope_masking",      '"epitope masking" OR "glycan masking" OR "homo-oligomer" OR "homodimer interface"'),
        ("cell_state_modulation",'"activation-induced" OR "stress-induced" OR "upregulated" OR "downregulated"'),
    ]

    seen_dois, pool = set(), []

    def harvest_one(query_str, max_pages=2, sort_param=None):
        cursor = "*"
        for _page in range(max_pages):
            url = _openalex_url(query_str, cursor=cursor, sort_param=sort_param)
            try:
                r = oa_client.get(url)
                if r.status_code == 429:
                    # Daily budget exhausted. Log + bail cleanly so per-gene
                    # progress so far is preserved; resume tomorrow.
                    import sys
                    print("  OpenAlex 429 — daily budget exhausted, stopping cleanly", file=sys.stderr, flush=True)
                    raise SystemExit(2)
                if r.status_code != 200:
                    break
                data = r.json()
            except SystemExit:
                raise
            except Exception:
                break
            for w in data.get("results", []):
                doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
                if not doi or doi in seen_dois:
                    continue
                seen_dois.add(doi)
                ids = w.get("ids") or {}
                pmid_raw = ids.get("pmid")
                pmid = None
                if pmid_raw:
                    try:
                        pmid = int(pmid_raw.rstrip("/").split("/")[-1])
                    except (ValueError, IndexError):
                        pass
                pmc_raw = ids.get("pmcid")
                pmc_id = None
                if pmc_raw:
                    pmc_id = pmc_raw.rstrip("/").split("/")[-1]
                # OpenAlex returns None for ~5% of titles (esp. preprint
                # placeholders + retraction records). Paper(title=None)
                # raises Pydantic ValidationError — coerce to empty string
                # so the construction always succeeds.
                try:
                    pool.append(Paper(
                        pmid=pmid or 0,
                        pmc_id=pmc_id,
                        doi=doi,
                        title=w.get("title") or "",
                        year=w.get("publication_year"),
                    ))
                except Exception:
                    continue
            cursor = (data.get("meta") or {}).get("next_cursor") or ""
            if not cursor:
                break

    # 21-axis parity with build_a1_kickoff:
    # Axis 1: broad gene recall (gene2pubmed analog)
    harvest_one(gene_q, max_pages=2)
    # Axis 2: broad gene + date-desc sort (recent_corpus analog)
    harvest_one(gene_q, max_pages=1, sort_param="publication_date:desc")
    # Axes 3-21: 19 method/topic/standing axis searches
    for _label, method_q in METHOD_AXES:
        harvest_one(f"({gene_q}) AND ({method_q})", max_pages=1)
    return pool


def fetch_unpaywall(doi, c):
    """Lookup Unpaywall record for a DOI. Returns dict or None."""
    if not doi:
        return None
    try:
        r = c.get(f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}")
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def classify(paper, http, retraction_index, unpaywall_client):
    """Run prod fetch + Unpaywall lookup, classify into 4 buckets."""
    # 1. Try production fetch chain
    fetched_via = None
    try:
        result = _fetch_body_drafts(paper, http=http, retraction_index=retraction_index)
        if result and result.drafts:
            fetched_via = result.source
    except Exception:
        pass
    if fetched_via == "pmc_xml":
        return "pmc"
    if fetched_via == "unpaywall_pdf":
        return "unpaywall"
    if fetched_via == "datacite_pdf":
        # New tier-3 from abstract_triage._fetch_body_via_datacite_landing —
        # covers DataCite-registered DOIs (arXiv, Zenodo, Stacks, some
        # institutional repos) that Unpaywall doesn't index. A successful
        # fetch here is functionally equivalent to PMC/Unpaywall but
        # categorized separately so we can measure the per-tier contribution.
        return "datacite_pdf"
    # 2. Prod didn't fetch — distinguish bot_blocked vs no_oa via Unpaywall
    d = fetch_unpaywall(paper.doi, unpaywall_client)
    if d is None or not d.get("is_oa", False):
        return "no_oa"
    locs = d.get("oa_locations") or []
    if d.get("best_oa_location"):
        locs = [d["best_oa_location"]] + locs
    has_reachable_pdf = False
    has_blocked = False
    for loc in locs:
        u = (loc.get("url_for_pdf") or loc.get("url") or "").lower()
        if BOT_BLOCKED.search(u):
            has_blocked = True
        elif u.endswith(".pdf") or "pdf" in u or "ncbi.nlm.nih.gov/pmc" in u:
            has_reachable_pdf = True
    if has_blocked and not has_reachable_pdf:
        return "bot_blocked"
    # OA but no usable path — merged into no_oa per user request
    return "no_oa"


def load_existing_genes(out_path):
    """Read the JSONL output file and return set of already-processed gene symbols."""
    if not out_path.exists():
        return set()
    seen = set()
    with out_path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
                seen.add(row["gene"])
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def _process_one_gene(sym, acc, source, papers_per_gene, http, retraction_index,
                      oa_client, unpaywall_client, rng):
    """Single-gene worker: harvest + sample + classify. Returns the JSONL row dict.

    Per-thread http/oa/unpaywall clients should be passed in by the orchestrator
    — sharing one client across threads risks httpx race conditions and inflates
    rate-limit pressure on a single connection pool.
    """
    bundle = resolve(acc, http=http)
    if not bundle or not bundle.hgnc_id:
        return {"gene": sym, "uniprot_acc": acc, "n_avail": 0, "papers": [],
                "source": source, "_status": "resolve_fail"}
    if source == "production":
        papers = harvest_europepmc(bundle.hgnc_id, http, retraction_index)
    else:
        papers = harvest_openalex(
            bundle.hgnc_symbol, list(bundle.aliases),
            list(bundle.previous_symbols), oa_client,
        )
    if not papers:
        return {"gene": sym, "uniprot_acc": acc, "n_avail": 0, "papers": [],
                "source": source, "_status": "0_papers"}
    chosen = rng.sample(papers, min(papers_per_gene, len(papers)))
    paper_rows = []
    for p in chosen:
        bucket = classify(p, http, retraction_index, unpaywall_client)
        paper_rows.append({
            "pmid": p.pmid, "pmc_id": p.pmc_id, "doi": p.doi,
            "year": p.year, "title": (p.title or "")[:100], "bucket": bucket,
        })
    return {
        "gene": sym, "uniprot_acc": acc, "hgnc_id": bundle.hgnc_id,
        "n_avail": len(papers), "n_sampled": len(chosen),
        "source": source, "papers": paper_rows, "_status": "ok",
    }


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["production", "openalex"], required=True)
    ap.add_argument("--n-genes", type=int, default=100)
    ap.add_argument("--papers-per-gene", type=int, default=10)
    ap.add_argument("--seed", type=int, default=2024)
    ap.add_argument(
        "--workers", type=int, default=1,
        help="Concurrent gene-processing threads. Default 1 (serial). "
             "Set to 5-8 for OpenAlex (polite-pool can sustain ~100 req/sec, "
             "but per-axis OpenAlex rate-shaping doesn't like burstiness — "
             "5-8 stays comfortably under the limit while ~5x'ing throughput).",
    )
    args = ap.parse_args()

    # Sample N random genes (same seed across sources → same gene set for comparable runs)
    cohort_path = (
        Path(__file__).resolve().parents[1]
        / "data/processed/candidate_universe/candidate_universe_v2.tsv"
    )
    cohort = []
    with cohort_path.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("uniprot_accession", "").strip():
                cohort.append((row["gene_symbol"], row["uniprot_accession"]))
    cohort = sorted(set(cohort))
    print(f"cohort with uniprot: {len(cohort)}")

    random.seed(args.seed)
    sample = random.sample(cohort, args.n_genes)
    print(f"Sampling {args.n_genes} genes × {args.papers_per_gene} papers each, source={args.source}")

    out_dir = (
        Path(__file__).resolve().parents[1]
        / "data/analysis/paywall_bot_block/probe_results"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cohort{args.n_genes}x{args.papers_per_gene}_{args.source}.jsonl"

    # Resume: skip genes already in the output file
    done = load_existing_genes(out_path)
    if done:
        print(f"Resume: {len(done)} genes already in {out_path.name}")
    remaining = [(s, a) for (s, a) in sample if s not in done]
    print(f"Remaining: {len(remaining)} genes to process")

    # Per-thread state so worker threads don't fight for httpx connection
    # pools, retraction index lookups, or random.sample sequencing. We give
    # each thread its own httpx clients + retraction index + per-gene RNG
    # seeded deterministically from (args.seed, sym) so sample selection is
    # reproducible regardless of worker count.
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    thread_local = threading.local()
    file_lock = threading.Lock()

    def _thread_state():
        if not hasattr(thread_local, "http"):
            thread_local.http = open_default_client()
            thread_local.retraction_index = RetractionIndex()
            thread_local.unpaywall = httpx.Client(
                timeout=15.0,
                headers={"User-Agent": "accessible-surfaceome-probe/1.0"},
            )
        return thread_local

    def _worker(idx, sym, acc):
        s = _thread_state()
        # Deterministic per-gene RNG so sample selection is the same whether
        # we run serial or 16-wide. Falls back to args.seed if the symbol
        # is somehow empty.
        gene_rng = random.Random(f"{args.seed}|{sym}")
        t0 = time.time()
        try:
            row = _process_one_gene(
                sym, acc, args.source, args.papers_per_gene,
                s.http, s.retraction_index, s.unpaywall, s.unpaywall, gene_rng,
            )
        except SystemExit:
            raise  # OpenAlex 429 daily-budget exit — let it propagate
        except Exception as e:
            return idx, sym, None, f"harvest fail {type(e).__name__}: {e}", time.time() - t0
        return idx, sym, row, row.get("_status", "ok"), time.time() - t0

    try:
        with out_path.open("a") as out_f:
            total = len(remaining)
            if args.workers <= 1:
                # Serial path — preserves original log ordering for production
                # which is mostly NCBI-rate-limited anyway.
                for i, (sym, acc) in enumerate(remaining):
                    idx, sym, row, status, elapsed = _worker(i, sym, acc)
                    if row is None:
                        print(f"  [{i+1:3d}/{total}] {sym}: {status}", flush=True)
                        continue
                    row.pop("_status", None)
                    out_f.write(json.dumps(row) + "\n")
                    out_f.flush()
                    if status == "ok":
                        c = Counter(p["bucket"] for p in row["papers"])
                        print(f"  [{i+1:3d}/{total}] {sym}: {row['n_avail']} avail, "
                              f"sampled {row['n_sampled']} ({elapsed:.0f}s) | {dict(c)}", flush=True)
                    else:
                        print(f"  [{i+1:3d}/{total}] {sym}: {status}", flush=True)
            else:
                # Parallel path — N gene-workers in flight at once.
                with ThreadPoolExecutor(max_workers=args.workers) as ex:
                    futures = [ex.submit(_worker, i, sym, acc)
                               for i, (sym, acc) in enumerate(remaining)]
                    completed = 0
                    for fut in as_completed(futures):
                        idx, sym, row, status, elapsed = fut.result()
                        completed += 1
                        with file_lock:
                            if row is not None:
                                row.pop("_status", None)
                                out_f.write(json.dumps(row) + "\n")
                                out_f.flush()
                            if row is None:
                                print(f"  [{completed:3d}/{total}] {sym}: {status}", flush=True)
                            elif status == "ok":
                                c = Counter(p["bucket"] for p in row["papers"])
                                print(f"  [{completed:3d}/{total}] {sym}: {row['n_avail']} avail, "
                                      f"sampled {row['n_sampled']} ({elapsed:.0f}s) | {dict(c)}", flush=True)
                            else:
                                print(f"  [{completed:3d}/{total}] {sym}: {status}", flush=True)
    finally:
        pass  # per-thread clients leak at process exit, acceptable for a one-shot probe

    # Final aggregate
    all_rows = []
    with out_path.open() as f:
        for line in f:
            try:
                all_rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    all_papers = [p for row in all_rows for p in row["papers"]]
    c = Counter(p["bucket"] for p in all_papers)
    total = sum(c.values())
    print(f"\n=== Final: {len(all_rows)} genes, {total} papers (source={args.source}) ===")
    for b in ("pmc", "unpaywall", "bot_blocked", "no_oa"):
        n = c.get(b, 0)
        print(f"  {b:15s}: {n:>4d} ({100*n/max(total,1):.1f}%)")
    print(f"  Full-body success: {100*(c['pmc']+c.get('unpaywall',0))/max(total,1):.0f}%")


if __name__ == "__main__":
    main()
