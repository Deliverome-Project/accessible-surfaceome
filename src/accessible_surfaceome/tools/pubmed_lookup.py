"""Surface-context literature evidence for a gene, via NCBI E-utilities.

Two-stage retrieval — all NCBI, no Europe PMC dependency:

1. **ESearch on db=pubmed**, ranked by relevance, with the query
   ``(<gene> OR <aliases>)[Title/Abstract] AND (<surface keywords>)
   [Title/Abstract]``. Returns PMIDs sorted by PubMed's own relevance
   scorer — surface-specific papers float to the top, which the
   unranked ``gene2pubmed`` link-table doesn't do.
2. **EFetch abstracts** for the top ``N`` PMIDs, sentence-split,
   keep only sentences mentioning both the gene (or an alias) and a
   surface-accessibility keyword. Return the top ``max_results``
   sentences as compact ``EvidenceRecord`` items.

Designed as a context-injection alternative to Anthropic's `web_search`
builtin: peer-reviewed primary literature, sentence-granular signal,
deterministic, free, ~1-2 seconds per call.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Surface-accessibility keyword set used to filter sentences. Inclusive
# because the schema's pre-no checklist already names every contextual
# bucket — any of these terms in primary literature is informative.
SURFACE_KEYWORDS = (
    "cell surface",
    "outer leaflet",
    "plasma membrane",
    "extracellular",
    "ecto-",
    "ectoenzyme",
    "ectokinase",
    "surface biotinylation",
    "flow cytometry",
    "surface proteomics",
    "lysosomal exocytosis",
    "outer face",
    "PM-localized",
    "PM transit",
)

# Modest cap on the number of abstracts to scan per gene — keeps the
# call to a few seconds and bounds the input-token budget for whoever
# downstream renders the result.
DEFAULT_N_ABSTRACTS = 60


@dataclass
class EvidenceRecord:
    pmid: str
    title: str
    sentence: str

    def render(self) -> str:
        """Compact one-line text for the LLM task message."""
        return (
            f"- [PMID {self.pmid}] {self.title}\n"
            f"  {self.sentence}"
        )


def _with_ncbi_api_key(url: str) -> str:
    """Append ``api_key=$NCBI_API_KEY`` to the URL when the env var is set.

    NCBI lifts the per-IP rate limit from 3 → 10 req/sec when an API
    key is presented. The key is free to get from
    https://www.ncbi.nlm.nih.gov/account/settings/ (API Key Management
    section). The runner loads `.env` at startup so adding
    ``NCBI_API_KEY=...`` to the repo-root `.env` is enough.
    """
    import os
    key = os.environ.get("NCBI_API_KEY")
    if not key:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}api_key={urllib.parse.quote(key)}"


def _fetch(url: str, *, timeout: float = 20.0, max_retries: int = 5) -> bytes:
    """GET with exponential backoff for 5xx AND 429 (rate-limit).

    Also honors ``Retry-After`` if the server sends one. Raises any
    other 4xx immediately. Transparently appends the NCBI API key
    when ``NCBI_API_KEY`` is set in the environment.
    """
    import time

    full_url = _with_ncbi_api_key(url)
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            # Retry on 429 (rate-limited) and 5xx; raise other 4xx.
            if status != 429 and 400 <= status < 500:
                raise
            if attempt + 1 >= max_retries:
                raise
            # Honor Retry-After (seconds or HTTP-date). Cap at 30s so a
            # stuck NCBI endpoint can't stall the run for minutes.
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                wait_s = min(30.0, float(retry_after)) if retry_after else 0.0
            except (TypeError, ValueError):
                wait_s = 0.0
            # Exponential backoff floor; jitter to de-sync concurrent callers.
            import random
            wait_s = max(wait_s, 0.5 * (2 ** attempt) + random.random() * 0.5)
            time.sleep(wait_s)
        except urllib.error.URLError:
            if attempt + 1 >= max_retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")


def _fetch_json(url: str, *, timeout: float = 20.0, max_retries: int = 4) -> dict:
    """Fetch + JSON-parse, retrying on transient parse errors too.

    NCBI occasionally returns truncated/intermixed payloads under load
    that decode to bytes but fail json.loads; treating those as
    transient (with backoff) is much more robust than failing fast.
    """
    import time
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return json.loads(_fetch(url, timeout=timeout))
        except json.JSONDecodeError as exc:
            last_err = exc
            if attempt + 1 >= max_retries:
                break
            time.sleep(0.5 * (2 ** attempt))
    assert last_err is not None
    raise last_err


def fetch_abstracts(pmids: list[str]) -> list[tuple[str, str, str]]:
    """Return ``[(pmid, title, abstract_text)]`` for a batch of PMIDs."""
    if not pmids:
        return []
    url = f"{NCBI_EFETCH}?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    )
    try:
        xml_bytes = _fetch(url, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("EFetch failed: %s", exc)
        return []
    out: list[tuple[str, str, str]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("EFetch XML parse failed: %s", exc)
        return []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        abstract_chunks = [
            (el.text or "")
            for el in article.findall(".//Abstract/AbstractText")
        ]
        pmid = (pmid_el.text or "").strip() if pmid_el is not None else ""
        title = (title_el.text or "").strip() if title_el is not None else ""
        abstract = " ".join(s.strip() for s in abstract_chunks if s).strip()
        if pmid and abstract:
            out.append((pmid, title, abstract))
    return out


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter. Adequate for abstract-grade text.

    Splits on period/exclamation/question followed by whitespace + capital
    letter, while preserving common biomedical short-forms (e.g.
    ``Fig.``, ``vs.``). Errs on the side of *under-splitting* so we don't
    fragment evidence quotes.
    """
    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    # Naive split; refine if it gets noisy in practice.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    # Drop tiny fragments.
    return [p.strip() for p in parts if len(p.strip()) >= 30]


def _sentence_mentions_surface(sentence: str) -> bool:
    s = sentence.lower()
    return any(kw.lower() in s for kw in SURFACE_KEYWORDS)


def _sentence_mentions_gene(sentence: str, gene_symbol: str, aliases: tuple[str, ...] = ()) -> bool:
    """Word-boundary check for the gene symbol or any alias."""
    targets = [gene_symbol, *aliases]
    for t in targets:
        if re.search(rf"\b{re.escape(t)}\b", sentence, re.IGNORECASE):
            return True
    return False


def pubmed_esearch_surface(
    gene_symbol: str, *, aliases: tuple[str, ...] = (), retmax: int = 60
) -> list[str]:
    """PubMed esearch ranked by relevance: gene/alias × surface keywords.

    Returns PMIDs sorted by PubMed's native relevance score. Much more
    useful than the unranked gene2pubmed list when the agent needs
    surface-specific evidence rather than "any paper about this gene".
    """
    # Build gene clause from the symbol + aliases.
    gene_tokens = [gene_symbol, *aliases]
    gene_clause = " OR ".join(f'"{t}"[Title/Abstract]' for t in gene_tokens)
    surface_clause = " OR ".join(f'"{kw}"[Title/Abstract]' for kw in SURFACE_KEYWORDS[:6])
    term = f"({gene_clause}) AND ({surface_clause})"
    url = f"{NCBI_ESEARCH}?" + urllib.parse.urlencode(
        {"db": "pubmed", "term": term, "retmode": "json",
         "retmax": retmax, "sort": "relevance"}
    )
    try:
        data = _fetch_json(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PubMed esearch surface query failed for %s: %s", gene_symbol, exc)
        return []
    return data.get("esearchresult", {}).get("idlist", [])


def get_surface_evidence(
    gene_symbol: str,
    *,
    aliases: tuple[str, ...] = (),
    max_results: int = 8,
    n_abstracts: int = DEFAULT_N_ABSTRACTS,
) -> list[EvidenceRecord]:
    """Return up to ``max_results`` surface-relevant sentences from
    relevance-ranked PubMed papers for ``gene_symbol``.

    Approach:

    1. PubMed esearch with the gene name (+ aliases) ANDed with surface
       keywords, sorted by PubMed relevance.
    2. EFetch abstracts for the top ``n_abstracts`` PMIDs.
    3. Sentence-split; keep sentences that mention both the gene/alias
       AND a surface keyword.

    Quiet failure: returns ``[]`` on any network error.
    """
    pmids = pubmed_esearch_surface(gene_symbol, aliases=aliases, retmax=n_abstracts)
    if not pmids:
        return []
    papers = fetch_abstracts(pmids)
    records: list[EvidenceRecord] = []
    seen: set[tuple[str, str]] = set()
    for pmid, title, abstract in papers:
        for sent in _split_sentences(abstract):
            if not _sentence_mentions_surface(sent):
                continue
            if not _sentence_mentions_gene(sent, gene_symbol, aliases):
                continue
            key = (pmid, sent[:120])
            if key in seen:
                continue
            seen.add(key)
            records.append(EvidenceRecord(pmid=pmid, title=title, sentence=sent))
            if len(records) >= max_results:
                return records
    return records


def render_evidence_block(records: list[EvidenceRecord], *, header: str | None = None) -> str:
    """Format an evidence list as a markdown block for the task message."""
    if not records:
        return ""
    lines = [
        header
        or (
            "Surface-context literature evidence (NCBI PubMed esearch ranked by "
            "relevance for gene + surface terms; abstracts efetched and "
            "sentence-filtered to those mentioning both the gene and a "
            "surface / extracellular / membrane / biotinylation / flow-cytometry "
            "keyword):"
        ),
        "",
    ]
    for r in records:
        lines.append(r.render())
    return "\n".join(lines)


def main() -> None:
    """CLI helper: pretty-print surface evidence for one gene."""
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("gene")
    ap.add_argument("--max-results", type=int, default=8)
    ap.add_argument("--n-abstracts", type=int, default=DEFAULT_N_ABSTRACTS)
    args = ap.parse_args()
    records = get_surface_evidence(
        args.gene, max_results=args.max_results, n_abstracts=args.n_abstracts
    )
    print(f"# {args.gene} — {len(records)} surface-context sentences\n")
    print(render_evidence_block(records))


if __name__ == "__main__":
    main()
