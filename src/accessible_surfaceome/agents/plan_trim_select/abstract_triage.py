"""Abstract triage — Haiku per-paper 3-way routing.

Sits between discovery (gene2pubmed / topic_search / recent_corpus +
evidence_retrieval in discover-only mode all return paper metadata)
and trim/select. For each discovered paper, makes a single Haiku call
against the abstract to decide:

  discard         → drop from pool
  keep_abstract   → add the abstract as preview clip(s) to the pool
  worth_fetching  → fetch the body (PMC native → PMID→PMCID eLink →
                    Unpaywall), let it flow through normal body-clip
                    extraction; fall back to abstract clip(s) if the
                    body can't be retrieved

This is the cheap routing step; the selector (Sonnet) no longer has
to decide what to fetch — by the time it sees the menu, abstracts
that warrant a fetch have already been fetched and abstracts that
warrant inclusion are already preview clips.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import TextBlock
from pydantic import ValidationError

from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents._support.pricing import (
    UsageRecord,
    record_from_response,
)
from accessible_surfaceome.agents.plan_trim_select.pdf_parse import (
    parse_pdf_to_sections,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    AbstractTriageResponse,
)
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaimDraft,
    IdentifierBundle,
    Paper,
)
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex
from accessible_surfaceome.tools.evidence_retrieval import (
    _split_sentences,
    extract_paper_drafts,
)

# runner._add_to_pool is passed in to the action layer as ``add_to_pool_fn``
# rather than imported, so abstract_triage never imports runner (runner
# imports abstract_triage — keeping the dependency one-directional).

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ABSTRACT_TRIAGE_PROMPT_PATH = PROMPTS_DIR / "abstract_triage_system.md"

HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_PRICING_KEY = "claude-haiku-4-5"
MAX_TOKENS_TRIAGE = 512
TRIAGE_CONCURRENCY = 10

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# Cache the system prompt at module load — it carries the rules + schema and
# is byte-identical across every per-paper triage call. Hoisting the JSON
# schema serialization to module scope keeps the cached prefix stable across
# calls (was: re-serialized per call, which created subtle whitespace drift
# that defeated the cache key). Caching is the highest-ROI cost lever on the
# Haiku triage path — ~50 calls/gene × ~1.9k cached input tokens → ~$0.08
# saved per gene at $0.10/M cached read vs $1/M cold input.
_SCHEMA_JSON: str = json.dumps(
    AbstractTriageResponse.model_json_schema(), indent=2
)
_SYSTEM_PROMPT_CACHED: str = ABSTRACT_TRIAGE_PROMPT_PATH.read_text().format(
    schema=_SCHEMA_JSON
)


def _build_user_message(
    *,
    gene: str,
    synonyms: str,
    paper_id: str,
    title: str,
    year: str,
    abstract: str,
) -> str:
    """Per-paper user message — the only thing that varies between calls.

    The system prompt (rules + schema) is cached; only this payload is billed
    at full input-token rate on each call. Keep the structure stable so the
    cached system prefix never falls out of cache due to message-formatting
    drift.
    """
    return (
        f"Gene: {gene}\n"
        f"Synonyms: {synonyms}\n"
        f"Paper id: {paper_id}\n"
        f"Title: {title}\n"
        f"Year: {year}\n"
        f"\n"
        f"Abstract:\n"
        f"{abstract}"
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    match = _FENCED_JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


@dataclass
class TriageOutcome:
    paper_id: str
    response: AbstractTriageResponse | None
    usage: UsageRecord | None
    elapsed_s: float
    error: str | None = None


def triage_one_abstract(
    client: Anthropic,
    *,
    paper: Paper,
    gene: str,
    bundle: IdentifierBundle | None = None,
    prompt_template: str | None = None,
) -> TriageOutcome:
    """Single Haiku call to triage one paper's abstract.

    ``bundle`` carries the gene's synonyms (HGNC aliases + previous
    symbols + approved name). Without it, the agent has only the HGNC
    symbol to identify the gene, which leads it to treat the common
    name as a different protein (e.g. CD20 vs MS4A1). Passing the
    bundle is strongly recommended.

    The rules + schema live in a cached system prompt (loaded once at
    module import); only the per-paper user message is billed at full
    input rate on each call. ``prompt_template`` is kept as a kwarg
    for back-compat with tests that override the prompt path, but it
    is now respected by re-serializing into the user-message format
    rather than by re-templating the system block — semantic-identical
    to the pre-caching path.
    """

    if not paper.abstract or not paper.abstract.strip():
        return TriageOutcome(
            paper_id=_paper_source_id(paper),
            response=None,
            usage=None,
            elapsed_s=0.0,
            error="no abstract",
        )

    paper_id = _paper_source_id(paper)
    user_msg = _build_user_message(
        gene=gene,
        synonyms=_format_synonyms(bundle),
        paper_id=paper_id,
        title=paper.title or "(no title)",
        year=str(paper.year) if paper.year else "(unknown)",
        abstract=paper.abstract.strip(),
    )
    # Tests may override the prompt template by passing a custom one — when
    # they do, fall back to the legacy single-message path so test-side prompt
    # substitutions still flow into the call body. Production never sets this.
    if prompt_template is not None:
        legacy_prompt = prompt_template.format(
            gene=gene,
            synonyms=_format_synonyms(bundle),
            paper_id=paper_id,
            title=paper.title or "(no title)",
            year=str(paper.year) if paper.year else "(unknown)",
            abstract=paper.abstract.strip(),
            schema=_SCHEMA_JSON,
        )
        create_kwargs: dict[str, Any] = {
            "model": HAIKU_MODEL,
            "max_tokens": MAX_TOKENS_TRIAGE,
            "messages": cast("Any", [{"role": "user", "content": legacy_prompt}]),
        }
    else:
        create_kwargs = {
            "model": HAIKU_MODEL,
            "max_tokens": MAX_TOKENS_TRIAGE,
            "system": cast("Any", cached_system(_SYSTEM_PROMPT_CACHED)),
            "messages": cast("Any", [{"role": "user", "content": user_msg}]),
        }

    t0 = time.perf_counter()
    try:
        resp = client.messages.create(**create_kwargs)
    except Exception as exc:  # noqa: BLE001
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=None,
            elapsed_s=round(time.perf_counter() - t0, 3),
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed = round(time.perf_counter() - t0, 3)
    usage = record_from_response(resp.usage, HAIKU_PRICING_KEY)
    text = "\n".join(
        b.text for b in resp.content if isinstance(b, TextBlock)
    ).strip()
    raw = _extract_json(text)
    if raw is None:
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=usage,
            elapsed_s=elapsed,
            error="no fenced JSON block in model output",
        )

    try:
        parsed = AbstractTriageResponse.model_validate(raw)
        parsed = parsed.model_copy(update={"paper_id": paper_id})
        return TriageOutcome(
            paper_id=paper_id, response=parsed, usage=usage, elapsed_s=elapsed
        )
    except ValidationError as exc:
        return TriageOutcome(
            paper_id=paper_id,
            response=None,
            usage=usage,
            elapsed_s=elapsed,
            error=f"schema validation: {exc}",
        )


def triage_abstracts(
    client: Anthropic,
    *,
    papers: list[Paper],
    gene: str,
    bundle: IdentifierBundle | None = None,
    concurrency: int = TRIAGE_CONCURRENCY,
) -> list[TriageOutcome]:
    """Fan out per-paper triage across ``concurrency`` threads."""

    if not papers:
        return []
    template = ABSTRACT_TRIAGE_PROMPT_PATH.read_text()
    out: list[TriageOutcome] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                triage_one_abstract,
                client,
                paper=p,
                gene=gene,
                bundle=bundle,
                prompt_template=template,
            )
            for p in papers
        ]
        for f in as_completed(futures):
            out.append(f.result())
    return out


def _format_synonyms(bundle: IdentifierBundle | None) -> str:
    """Build the human-readable synonyms string for the prompt.

    Returns something like "CD20, B-lymphocyte antigen CD20, Bp35, Leu-16"
    when the bundle carries aliases + previous_symbols + approved_name,
    or "(no known synonyms)" if the bundle is absent or empty.
    """

    if bundle is None:
        return "(no known synonyms)"
    parts: list[str] = []
    seen: set[str] = {bundle.hgnc_symbol.upper()}
    if bundle.approved_name:
        parts.append(bundle.approved_name)
        seen.add(bundle.approved_name.upper())
    for s in (*bundle.aliases, *bundle.previous_symbols):
        if not s:
            continue
        key = s.upper()
        if key in seen:
            continue
        seen.add(key)
        parts.append(s)
    if not parts:
        return "(no known synonyms)"
    return ", ".join(parts)


def paper_source_id(paper: Paper) -> str:
    """Canonical pool/source key for a paper: ``PMC:<id>`` > ``PMID:<id>``.

    This is the key both the clip pool's ``source_id`` and the triage
    outcome's ``paper_id`` agree on, so the runner can join triage
    outcomes back to discovered papers and to the body pool.
    """
    if paper.pmc_id:
        return f"PMC:{paper.pmc_id}"
    if paper.pmid:
        return f"PMID:{paper.pmid}"
    return "UNKNOWN"


# Internal alias retained for the existing call sites in this module.
_paper_source_id = paper_source_id


# ---------------------------------------------------------------------------
# Acting on triage outcomes — drop / keep-abstract / fetch
# ---------------------------------------------------------------------------


@dataclass
class TriageAction:
    """Result of applying one triage decision to the pool.

    Carries audit detail for the case where ``worth_fetching`` couldn't
    actually retrieve a body and fell back to ``keep_abstract``.
    """

    paper_id: str
    decision: str  # discard | keep_abstract | worth_fetching | error
    drafts_added: int = 0
    fetched_body: bool = False
    # Which retrieval path produced the body, set only when fetched_body is
    # True: "pmc_xml" (PMC JATS) or "unpaywall_pdf" (OA publisher PDF). PDF
    # text is noisier than JATS, so downstream debugging can filter on it.
    fetch_source: str | None = None
    # Raw Unpaywall OA license of the recovered copy (e.g. "cc-by",
    # "cc-by-nc-nd", or None for bronze/unknown). Set only on the unpaywall_pdf
    # path; recorded for redistribution provenance ("must track per-item
    # license"). Not gated — snippet redistribution rests on fair use.
    fetch_license: str | None = None
    fetch_error: str | None = None
    fell_back_to_abstract: bool = False
    elapsed_s: float = 0.0


_ABSTRACT_QUOTE_CAP = 600  # matches EvidenceClaimDraft.quote max_length


def _chunk_abstract(text: str, cap: int) -> list[str]:
    """Greedy sentence-pack ``text`` into chunks of at most ``cap`` chars.

    Packs whole sentences until the next would overflow ``cap``, then
    starts a new chunk. A single sentence longer than ``cap`` (rare in
    abstracts) is hard-split on a word boundary. Preserves local context
    within each chunk so anaphora resolves — "such cells" stays adjacent
    to the sentence it refers to, unlike a sentence-level split.
    """

    sentences = _split_sentences(text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > cap:
            # Flush what we have, then hard-split the long sentence.
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(sentence):
                window = sentence[start : start + cap]
                if start + cap < len(sentence):
                    cut = window.rfind(" ")
                    if cut > cap * 2 // 3:
                        window = window[:cut]
                chunks.append(window.strip())
                start += len(window)
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > cap:
            if current:
                chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _abstract_clips(paper: Paper) -> list[EvidenceClaimDraft]:
    """Build preview clip(s) from a paper's abstract for keep_abstract.

    Greedy sentence-packs the abstract into <=600-char chunks (the
    ``EvidenceClaimDraft.quote`` cap), one draft per chunk. Most abstracts
    yield 2-3 chunks. Earlier chunks score higher so the trim/select
    layers see the lead (where the load-bearing finding usually sits)
    first. All chunks tagged ``hallmark_phrase='abstract_preview'`` so
    downstream can distinguish abstract-derived from body-derived clips.
    """
    if not paper.abstract or not paper.abstract.strip():
        return []
    source_id = _paper_source_id(paper)
    if source_id == "UNKNOWN":
        return []
    bare = source_id.split(":", 1)[-1]
    chunks = _chunk_abstract(paper.abstract, _ABSTRACT_QUOTE_CAP)
    drafts: list[EvidenceClaimDraft] = []
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        # Score 2.0 → 1.0 across chunks so the lead ranks above the tail
        # but all abstract previews sit below typical body clips.
        score = 1.0 + (n - i) / n if n else 1.0
        drafts.append(
            EvidenceClaimDraft(
                suggested_evidence_id=f"draft_{bare}_abstract_{i + 1:02d}",
                quote=chunk,
                source_id=source_id,
                section="abstract",
                figure_or_table_id=None,
                context_excerpt=None,
                hallmark_phrase="abstract_preview",
                score=score,
            )
        )
    return drafts


_NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
_UNPAYWALL_API = "https://api.unpaywall.org/v2"
# Unpaywall requires an email as a polite-pool identifier (free, no signup).
# Overridable via UNPAYWALL_EMAIL; defaults to the project contact so the
# fallback works out of the box without per-worktree .env edits.
_DEFAULT_UNPAYWALL_EMAIL = "michael.smallegan@gmail.com"
# Skip absurdly large downloads before parsing — DoS guard for untrusted
# publisher PDFs. A paper + supplement is well under this.
_MAX_PDF_BYTES = 40 * 1024 * 1024
# At most this many OA locations are attempted per paper, bounding download
# load/latency when Unpaywall lists many copies (most list 1–3).
_MAX_PDF_LOCATIONS = 4
# Courtesy floor between PDF requests to the same publisher host — politeness at
# cohort scale, since publisher hosts aren't in the rate-limiter's per-host table.
_PDF_COURTESY_INTERVAL_MS = 500.0


@dataclass
class UnpaywallLocation:
    """One OA location reported by Unpaywall."""

    url: str
    url_for_pdf: str | None
    url_for_landing_page: str | None
    host_type: str | None  # "publisher" or "repository"
    version: str | None  # "publishedVersion" | "acceptedVersion" | "submittedVersion"
    license: str | None
    has_pdf: bool


def _lookup_oa_via_unpaywall(
    doi: str, *, http: CachedHTTP, email: str
) -> list[UnpaywallLocation]:
    """Resolve DOI → OA locations via Unpaywall.

    Returns an empty list if the DOI isn't in Unpaywall or the paper
    has no OA copies. Each ``UnpaywallLocation`` describes one OA host
    (publisher landing page, repository PDF, etc.). The caller decides
    which one to attempt fetching first — typically publisher
    publishedVersion > repository acceptedVersion > submittedVersion.

    Cached for 90 days; Unpaywall data is stable for old DOIs and
    only changes when new OA copies are deposited.
    """

    if not doi:
        return []
    try:
        payload = http.get_json(
            f"{_UNPAYWALL_API}/{doi.lstrip('/')}",
            source="unpaywall",
            ttl_days=90,
            params={"email": email},
        )
    except Exception:  # noqa: BLE001
        return []

    if not payload.get("is_oa"):
        return []

    locations: list[UnpaywallLocation] = []
    for loc in payload.get("oa_locations") or []:
        locations.append(
            UnpaywallLocation(
                url=loc.get("url") or "",
                url_for_pdf=loc.get("url_for_pdf"),
                url_for_landing_page=loc.get("url_for_landing_page"),
                host_type=loc.get("host_type"),
                version=loc.get("version"),
                license=loc.get("license"),
                has_pdf=bool(loc.get("url_for_pdf")),
            )
        )
    return locations


def _rank_pdf_urls(locations: list[UnpaywallLocation]) -> list[str]:
    """All distinct OA PDF URLs, best-quality first.

    ``publishedVersion`` ranks above accepted/submitted; within a version, a
    publisher host ranks above a repository. The caller tries them **in order**,
    falling through on 403 / non-PDF — so a paper whose publisher copy is
    bot-blocked (PNAS, Wiley, ASH all 403 our polite UA) can still be recovered
    from a green-OA repository copy (institutional repo, OSTI, …). Returns an
    empty list when no location exposes a direct ``url_for_pdf`` (HTML-only OA).
    """

    def rank(loc: UnpaywallLocation) -> tuple[int, int]:
        published = 1 if loc.version == "publishedVersion" else 0
        publisher = 1 if loc.host_type == "publisher" else 0
        return (published, publisher)

    out: list[str] = []
    seen: set[str] = set()
    for loc in sorted(
        [loc for loc in locations if loc.url_for_pdf], key=rank, reverse=True
    ):
        url = loc.url_for_pdf
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _pick_best_pdf_url(locations: list[UnpaywallLocation]) -> str | None:
    """The single best OA PDF URL (top of :func:`_rank_pdf_urls`), or ``None``."""

    urls = _rank_pdf_urls(locations)
    return urls[0] if urls else None


def _lookup_pmcid_for_pmid(pmid: int, *, http: CachedHTTP) -> str | None:
    """Resolve PMID → PMCID via NCBI eLink ``pubmed_pmc`` linkname.

    The gene2pubmed metadata path goes through EuropePMC's bulk search
    with ``SRC:MED``, which surfaces MEDLINE records and doesn't always
    carry the PMCID even when the paper is also in PMC. NCBI's eLink
    is the canonical authoritative PMID↔PMCID cross-reference.

    Returns ``"PMC{N}"`` if the PMID is linked to a PMC record, else
    ``None``. Cached aggressively — the link is stable once published.
    """

    params: dict[str, Any] = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": str(pmid),
        "linkname": "pubmed_pmc",
        "retmode": "json",
    }
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    try:
        payload = http.get_json(
            _NCBI_ELINK,
            source="ncbi",
            ttl_days=90,
            params=params,
        )
    except Exception:  # noqa: BLE001
        return None

    linksets = payload.get("linksets") or []
    for ls in linksets:
        for ldb in ls.get("linksetdbs") or []:
            if ldb.get("dbto") != "pmc":
                continue
            links = ldb.get("links") or []
            if links:
                return f"PMC{links[0]}"
    return None


@dataclass
class _BodyFetch:
    """A successfully fetched body: its drafts + which path produced it.

    ``source`` is ``"pmc_xml"`` or ``"unpaywall_pdf"`` and flows onto the
    ``TriageAction.fetch_source`` audit field. ``oa_license`` is the raw
    Unpaywall license string of the recovered copy (e.g. ``"cc-by"``,
    ``"cc-by-nc-nd"``, or ``None`` for bronze OA / unknown) — captured for
    redistribution provenance, not gated here.
    """

    drafts: list[EvidenceClaimDraft]
    source: str
    oa_license: str | None = None


def _fetch_body_drafts(
    paper: Paper,
    *,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
) -> _BodyFetch:
    """Pull the full body for ``paper`` and convert to drafts.

    Resolution chain — each step falls through to the next on miss/empty:

    1. **PMC JATS** via ``paper.pmc_id``, or PMID → PMCID via NCBI eLink
       (many older papers are in PMC but the gene2pubmed metadata pipeline
       didn't carry the link).
    2. **Unpaywall OA PDF**: DOI → best OA PDF → pdfplumber section parse.
       Recovers landmark publisher-PDF papers (and the PMC-PDF-only case
       where JATS XML comes back empty).

    Raises if every step fails (caller falls back to keep_abstract). Uses the
    same no-filter ``extract_paper_drafts`` as ``gene_literature(mode=
    fetch_fulltext)`` so triage-driven body clips are indistinguishable from
    selector-driven ones downstream.
    """

    # Step 1: PMC JATS.
    pmcid = paper.pmc_id
    if not pmcid and paper.pmid:
        pmcid = _lookup_pmcid_for_pmid(paper.pmid, http=http)
    if pmcid:
        try:
            body_paper = fetch_fulltext(
                http=http, pmcid=pmcid, retraction_index=retraction_index
            )
            if body_paper.sections:
                drafts = extract_paper_drafts(
                    source_id=f"PMC:{pmcid}",
                    abstract=body_paper.abstract,
                    sections=body_paper.sections,
                )
                if drafts:
                    return _BodyFetch(drafts=drafts, source="pmc_xml")
        except Exception as exc:  # noqa: BLE001 — any PMC error falls through to Unpaywall
            logger.info("PMC JATS fetch failed for PMC:%s (%s); trying Unpaywall", pmcid, exc)
        # PMC resolved but JATS was empty/errored (PMC-PDF-only) — fall through.

    # Step 2: Unpaywall OA PDF.
    pdf_drafts, oa_license = _fetch_body_via_unpaywall_pdf(paper, http=http)
    if pdf_drafts:
        return _BodyFetch(
            drafts=pdf_drafts, source="unpaywall_pdf", oa_license=oa_license
        )

    raise ValueError(
        f"no body for {_paper_source_id(paper)}: no PMC JATS and no "
        f"Unpaywall OA PDF (DOI:{paper.doi or '—'})"
    )


def _fetch_body_via_unpaywall_pdf(
    paper: Paper, *, http: CachedHTTP
) -> tuple[list[EvidenceClaimDraft], str | None]:
    """Fetch the paper's OA PDF via Unpaywall and parse it into body drafts.

    Returns ``(drafts, oa_license)``. ``drafts`` is ``[]`` (never raises) when
    there's no DOI, no stable source key, no OA PDF, every copy is blocked /
    non-PDF / unparseable — all of which mean "fall through to the abstract".
    ``oa_license`` is the raw Unpaywall license of the copy we actually used
    (e.g. ``"cc-by"``, ``"cc-by-nc-nd"``, or ``None`` for bronze/unknown),
    captured for redistribution provenance (not gated).

    Body drafts are keyed on the paper's canonical ``PMID:``/``PMC:`` source id
    (not ``DOI:``) so clip ids stay clean; provenance lives on the
    ``TriageAction``. At most ``_MAX_PDF_LOCATIONS`` copies are tried, with a
    per-host courtesy interval so we don't hammer publisher servers at scale.
    """

    if not paper.doi:
        return [], None
    source_id = _paper_source_id(paper)
    if source_id == "UNKNOWN":
        return [], None  # no stable PMID/PMCID to key clips on

    email = os.environ.get("UNPAYWALL_EMAIL") or _DEFAULT_UNPAYWALL_EMAIL
    locations = _lookup_oa_via_unpaywall(paper.doi, http=http, email=email)
    license_by_url = {loc.url_for_pdf: loc.license for loc in locations if loc.url_for_pdf}
    pdf_urls = _rank_pdf_urls(locations)[:_MAX_PDF_LOCATIONS]

    # Try each OA PDF location in quality order, falling through on a blocked /
    # non-PDF / unparseable copy, so a bot-blocked publisher copy doesn't sink a
    # paper that also has a working repository copy.
    for pdf_url in pdf_urls:
        try:
            pdf_bytes = http.get_bytes(
                pdf_url,
                source="unpaywall_pdf",
                ttl_days=180,
                headers={"Accept": "application/pdf"},
                max_bytes=_MAX_PDF_BYTES,  # streamed cap: aborts oversized downloads
                min_interval_ms=_PDF_COURTESY_INTERVAL_MS,
            )
        except Exception as exc:  # noqa: BLE001 — 403 / paywall / timeout / too large
            logger.info("Unpaywall PDF fetch failed for %s at %s: %s", source_id, pdf_url, exc)
            continue
        if b"%PDF" not in pdf_bytes[:1024]:
            # 200 OK but an HTML interstitial / paywall page, not a PDF.
            logger.info("Unpaywall URL for %s was not a PDF: %s", source_id, pdf_url)
            continue
        sections = parse_pdf_to_sections(pdf_bytes)
        if not sections:
            continue
        oa_license = license_by_url.get(pdf_url)
        if not oa_license or "nc" in oa_license or "nd" in oa_license:
            # Bronze OA (no license) or NC/ND — redistribution of our short
            # snippets rests on fair use; flag for provenance visibility.
            logger.info(
                "Unpaywall PDF for %s used a restricted/unknown OA license: %r (%s)",
                source_id, oa_license, pdf_url,
            )
        return (
            extract_paper_drafts(
                source_id=source_id, abstract=paper.abstract, sections=sections
            ),
            oa_license,
        )
    return [], None


def apply_triage_outcomes(
    outcomes: list[TriageOutcome],
    papers_by_id: dict[str, Paper],
    *,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    add_to_pool_fn: Any,
    fetch_concurrency: int = 5,
) -> list[TriageAction]:
    """Apply all triage outcomes.

    Discards and keep_abstract actions run on the main thread (no I/O).
    worth_fetching actions are dispatched in parallel up to
    ``fetch_concurrency`` since each is an HTTP call. Results are
    applied to the pool on the main thread to avoid concurrent mutation.
    """

    actions: list[TriageAction] = []

    # Phase 1: parallel fetch for worth_fetching outcomes.
    to_fetch: list[tuple[TriageOutcome, Paper]] = []
    for o in outcomes:
        if o.response is None or o.response.decision != "worth_fetching":
            continue
        paper = papers_by_id.get(o.paper_id)
        if paper is None:
            continue
        to_fetch.append((o, paper))

    fetched: dict[str, _BodyFetch | Exception] = {}
    if to_fetch:
        with ThreadPoolExecutor(max_workers=fetch_concurrency) as ex:
            futures = {
                ex.submit(
                    _fetch_body_drafts,
                    p,
                    http=http,
                    retraction_index=retraction_index,
                ): o.paper_id
                for o, p in to_fetch
            }
            for f in as_completed(futures):
                pid = futures[f]
                try:
                    fetched[pid] = f.result()
                except Exception as exc:  # noqa: BLE001
                    fetched[pid] = exc

    # Phase 2: apply all actions on main thread.
    for o in outcomes:
        paper = papers_by_id.get(o.paper_id)
        if paper is None:
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="error",
                    fetch_error="paper not in inventory",
                )
            )
            continue
        if o.response is None:
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="error",
                    fetch_error=o.error,
                )
            )
            continue

        decision = o.response.decision
        if decision == "discard":
            actions.append(TriageAction(paper_id=o.paper_id, decision="discard"))
        elif decision == "keep_abstract":
            clips = _abstract_clips(paper)
            for clip in clips:
                add_to_pool_fn(clip, pool, by_source)
            actions.append(
                TriageAction(
                    paper_id=o.paper_id,
                    decision="keep_abstract",
                    drafts_added=len(clips),
                    fetch_error=None if clips else "no abstract text to clip",
                )
            )
        elif decision == "worth_fetching":
            result = fetched.get(o.paper_id)
            if isinstance(result, _BodyFetch) and result.drafts:
                for d in result.drafts:
                    add_to_pool_fn(d, pool, by_source)
                actions.append(
                    TriageAction(
                        paper_id=o.paper_id,
                        decision="worth_fetching",
                        drafts_added=len(result.drafts),
                        fetched_body=True,
                        fetch_source=result.source,
                        fetch_license=result.oa_license,
                    )
                )
            else:
                # Fetch failed OR produced zero body clips (e.g. every
                # sentence failed the substring check) — fall back to the
                # abstract preview so the paper isn't silently dropped.
                if isinstance(result, Exception):
                    fetch_error = f"{type(result).__name__}: {result}"
                elif isinstance(result, _BodyFetch):
                    fetch_error = "fetched body yielded zero clips"
                else:
                    fetch_error = "unknown fetch result"
                clips = _abstract_clips(paper)
                for clip in clips:
                    add_to_pool_fn(clip, pool, by_source)
                actions.append(
                    TriageAction(
                        paper_id=o.paper_id,
                        decision="worth_fetching",
                        drafts_added=len(clips),
                        fetched_body=False,
                        fetch_error=fetch_error,
                        fell_back_to_abstract=len(clips) > 0,
                    )
                )

    # Observability: per-run body-fetch breakdown for production monitoring.
    wf = [a for a in actions if a.decision == "worth_fetching"]
    if wf:
        by_src = Counter(a.fetch_source for a in wf if a.fetched_body)
        fell_back = sum(1 for a in wf if not a.fetched_body)
        logger.info(
            "triage body fetch: %d worth_fetching → pmc_xml=%d unpaywall_pdf=%d fell_back=%d",
            len(wf), by_src.get("pmc_xml", 0), by_src.get("unpaywall_pdf", 0), fell_back,
        )

    return actions


__all__ = [
    "TriageOutcome",
    "TriageAction",
    "triage_one_abstract",
    "triage_abstracts",
    "apply_triage_outcomes",
    "paper_source_id",
    "ABSTRACT_TRIAGE_PROMPT_PATH",
]
