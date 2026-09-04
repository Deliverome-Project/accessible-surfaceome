"""Probe: can Haiku 4.5 find the verbatim substring a paraphrased quote was based on?

Out-of-band test — does NOT modify the orchestrator agent flow. Loads a gene's
annotation, finds rows whose ``validation_warnings`` carry
"substring not found in normalized ... text" (the paraphrase failure mode
named in the 2026-05-15 GPR75 audit), re-fetches the source body via Europe
PMC, and asks Haiku to return the verbatim substring the paraphrase summarizes.

Reports per-row: (paraphrase, Haiku-suggested verbatim, substring-anchors?,
char counts, latency). Aggregates total cost at the end.

Usage:

    uv run python scripts/haiku_paraphrase_repair_probe.py GPR75
    uv run python scripts/haiku_paraphrase_repair_probe.py GPR75 --limit 3

If the probe is reliable across the GPR75 unanchored rows (and on a wider
sweep), the next step is wiring this as a post-validation repair pass in
the orchestrator's evidence-promotion step. Not landed by this script —
this is the proof-of-concept that goes before the integration decision.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord, cost_for_usage
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_search,
    fetch_fulltext,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    empty as _empty_retraction_index,
)


HAIKU_MODEL = "claude-haiku-4-5-20251001"
# pricing.PRICING uses the base model id without date suffix.
HAIKU_PRICING_KEY = "claude-haiku-4-5"

PROMPT_TEMPLATE = """You are repairing a citation. A scientist wrote a paraphrased \
sentence that they intended to be supported by a verbatim quote from a paper, \
but the paraphrase doesn't substring-match the paper body. Your job is to find \
the verbatim substring in the paper that the paraphrase was based on.

PARAPHRASED CLAIM:
{quote}

PAPER BODY:
\"\"\"
{body}
\"\"\"

Find ONE contiguous span in the PAPER BODY that supports the PARAPHRASED CLAIM. \
HARD RULES (the call fails if any rule is broken):

1. The span must be a single contiguous range of characters in the PAPER BODY. \
   Copy the characters in order, exactly as they appear, with NO edits, NO \
   deletions, NO substitutions, NO concatenation across non-adjacent regions.
2. Do NOT skip over intervening sentences. Do NOT drop citation markers like \
   "(14)" or "[3]" or "(Figure 1A)" — if they appear inside your span, keep them.
3. Do NOT remove inline markup tags like <sub>, <sup>, <i>, <b> — keep them \
   exactly as they appear in the body.
4. Stay under 600 characters. If the paraphrase covers more than 600 chars of \
   the paper, pick the SINGLE most load-bearing sentence (the one that most \
   directly states the claim).
5. If no single contiguous span in the paper supports the paraphrase, respond \
   with the single word NULL — do not stitch together a span that doesn't \
   exist in the paper.

Output ONLY the verbatim contiguous span (or NULL). No quotation marks around \
it, no commentary, no preamble, no explanation."""


logger = logging.getLogger(__name__)


def _strip_source_prefix(source_id: str) -> tuple[str, str]:
    """Return (prefix, bare) for source ids like 'PMC:PMC12345' or 'PMID:67890'."""
    if ":" not in source_id:
        return "", source_id
    prefix, bare = source_id.split(":", 1)
    return prefix, bare


def _fetch_source_body(source_id: str, http) -> str:
    """Fetch the paper body Europe PMC has for this source_id.

    PMC:PMCxxxx → fullTextXML through ``fetch_fulltext`` (returns sections).
    PMID:xxxxx → abstract via search.

    Returns the raw concatenated body (title + abstract + sections joined by
    paragraph breaks); the substring check operates on the normalized form.
    """
    prefix, bare = _strip_source_prefix(source_id)
    retraction = _empty_retraction_index()
    if prefix == "PMC":
        paper = fetch_fulltext(http=http, pmcid=bare, retraction_index=retraction)
        parts = [paper.title or ""]
        if paper.abstract:
            parts.append(paper.abstract)
        parts.extend(s.text for s in paper.sections)
        return "\n\n".join(p for p in parts if p)
    if prefix == "PMID":
        payload = europepmc_search(
            http=http, query=f"EXT_ID:{bare} AND SRC:MED", page_size=1
        )
        hits = (payload.get("resultList") or {}).get("result") or []
        if not hits:
            raise LookupError(f"PMID:{bare} not found in Europe PMC")
        paper = paper_from_europepmc(hits[0], retraction_index=retraction)
        parts = [paper.title or ""]
        if paper.abstract:
            parts.append(paper.abstract)
        return "\n\n".join(p for p in parts if p)
    raise ValueError(f"unrecognized source_id prefix: {source_id!r}")


def _ask_haiku(
    client: Anthropic, *, quote: str, body: str, max_body_chars: int = 60_000
) -> tuple[str, dict[str, int], float]:
    """Single Haiku call. Returns (text, usage_dict, latency_s)."""
    body_trimmed = body[:max_body_chars]
    prompt = PROMPT_TEMPLATE.format(quote=quote, body=body_trimmed)
    t0 = time.time()
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.time() - t0
    text_blocks = [b.text for b in resp.content if b.type == "text"]
    text = "\n".join(text_blocks).strip()
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_creation_input_tokens": getattr(
            resp.usage, "cache_creation_input_tokens", 0
        )
        or 0,
        "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0)
        or 0,
    }
    return text, usage, latency


def _check_substring(repaired: str, body: str) -> bool:
    """Same normalization the orchestrator uses at promotion time."""
    if repaired.strip().upper() == "NULL":
        return False
    normalized_quote = normalize_for_quote_matching(repaired)
    normalized_body = normalize_for_quote_matching(body)
    return find_quote_in_normalized(normalized_quote, normalized_body) is not None


def _select_unanchored_paraphrase_rows(record: dict, limit: int | None) -> list[dict]:
    """Filter to evidence rows that failed substring anchoring with the
    'substring not found in normalized ...' warning — i.e. the paraphrase
    failure mode, NOT the 'not in session source store' mode."""
    out = []
    for e in record.get("evidence", []):
        if e.get("entailment_verified"):
            continue
        warnings = e.get("validation_warnings", []) or []
        if not any("substring not found in normalized" in w for w in warnings):
            continue
        out.append(e)
        if limit is not None and len(out) >= limit:
            break
    return out


def _paraphrased_quote_for(row: dict) -> str:
    """The paraphrase to be repaired. Prefer the row's ``claim`` text since
    span.quote may be empty when the substring check rejected it."""
    if row.get("spans"):
        q = row["spans"][0].get("quote", "")
        if q:
            return q
    return row.get("claim", "")


def _row_source_id(row: dict) -> str | None:
    """Extract source_id from validation_warnings if spans were dropped."""
    if row.get("spans"):
        return row["spans"][0]["source"].get("source_id")
    for w in row.get("validation_warnings", []) or []:
        # warning format: "substring not found in normalized PMC:PMCxxxx text..."
        if "normalized " in w and (" text after" in w or " text " in w):
            after = w.split("normalized ", 1)[-1]
            cand = after.split(" text", 1)[0].strip()
            if cand.startswith(("PMC:", "PMID:")):
                return cand
    return None


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("gene", help="Gene symbol (e.g. GPR75). Reads data/annotations/<GENE>.json.")
    parser.add_argument("--limit", type=int, default=None, help="Max unanchored rows to probe.")
    args = parser.parse_args(argv)

    annotation_path = Path(f"data/annotations/{args.gene}.json")
    if not annotation_path.exists():
        print(f"no annotation at {annotation_path}", file=sys.stderr)
        return 1
    record = json.loads(annotation_path.read_text())

    rows = _select_unanchored_paraphrase_rows(record, args.limit)
    if not rows:
        print(f"no paraphrase-mode unanchored rows in {args.gene}")
        return 0
    print(f"probing {len(rows)} unanchored row(s) for {args.gene}")

    client = Anthropic()
    http = open_default_client()
    total_cost = 0.0
    repaired_ok = 0
    out_records: list[dict] = []

    try:
        for i, row in enumerate(rows, 1):
            source_id = _row_source_id(row)
            quote = _paraphrased_quote_for(row)
            print(f"\n=== row {i}/{len(rows)} [{row['evidence_id']}] ===")
            print(f"  source_id: {source_id}")
            print(f"  paraphrase ({len(quote)}c): {quote[:160]}{'…' if len(quote) > 160 else ''}")

            if not source_id or not quote:
                print("  SKIP — missing source_id or quote")
                continue
            try:
                body = _fetch_source_body(source_id, http)
            except Exception as exc:  # noqa: BLE001 — probe-level robustness
                print(f"  FETCH FAILED: {type(exc).__name__}: {exc}")
                continue
            print(f"  body fetched: {len(body)} chars")

            repaired, usage, latency = _ask_haiku(client, quote=quote, body=body)
            cost = cost_for_usage(UsageRecord(**usage), HAIKU_PRICING_KEY)
            total_cost += cost
            anchored = _check_substring(repaired, body)
            repaired_ok += int(anchored)

            preview = repaired if len(repaired) <= 200 else repaired[:200] + "…"
            print(f"  haiku reply ({len(repaired)}c, {latency:.1f}s, ${cost:.4f}): {preview}")
            print(f"  substring-anchors after repair: {'YES ✓' if anchored else 'NO ✗'}")
            out_records.append({
                "evidence_id": row["evidence_id"],
                "source_id": source_id,
                "paraphrase": quote,
                "haiku_repair": repaired,
                "anchored": anchored,
                "body_len": len(body),
                "cost_usd": cost,
                "latency_s": latency,
            })
    finally:
        http.close()

    out_path = Path(f".runs/haiku_repair_probe_{args.gene}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": out_records, "total_cost_usd": total_cost}, indent=2))
    print(f"\n=== summary: {repaired_ok}/{len(rows)} rows repaired | total cost ${total_cost:.4f} ===")
    print(f"full report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
