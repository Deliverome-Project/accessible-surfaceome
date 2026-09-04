"""Mock + try the paragraph clip-and-judge tool design.

Two things in one script:

1. **API mock** — ``extract_paragraph_clips(paper)`` returns a list of
   ``ParagraphClip`` records. Each carries a verbatim chunk of the
   paper, the section it came from, a stable id, and a pre-computed
   target-mention flag. No NLP, no hallmark filter — just XML-derived
   paragraph boundaries (single ``\\n`` in ``PaperSection.text``, which
   ``parse_jats_sections`` writes one ``<p>`` per line).

2. **Agent-simulation pass** — for each paper, batch the clips into one
   Haiku call asking "which IDs contain load-bearing surface-accessibility
   evidence for {GENE}? reply with JSON {keep: [...], drop: [...]}". This
   simulates the keep/drop loop the real agent would run under a clip-
   based design — no prose typing, just binary judgments per clip.

Outputs:

* ``.runs/paragraph_clip_probe_<gene>.json`` — per-paper clip catalogs
  + Haiku decisions, raw.
* ``.runs/paragraph_clip_probe_<gene>_html/`` — one HTML per paper with
  every paragraph rendered, color-coded by keep/drop, target-mention
  flag, and the Haiku reason (if surfaced). Plus an index.

Usage:

    uv run python scripts/paragraph_clip_probe.py GPR75
    open .runs/paragraph_clip_probe_GPR75_html/index.html
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from anthropic import Anthropic

from accessible_surfaceome.agents._support.pricing import UsageRecord, cost_for_usage
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.retraction_watch import (
    empty as _empty_retraction_index,
)


HAIKU_MODEL = "claude-haiku-4-5-20251001"
HAIKU_PRICING_KEY = "claude-haiku-4-5"
MAX_PARAGRAPH_CHARS = 1500
PARAGRAPH_OVERLAP_SAFETY = 50  # for splitting overlong paragraphs at sentence boundaries


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clip extraction — the proposed API
# ---------------------------------------------------------------------------


@dataclass
class ParagraphClip:
    """One verbatim paragraph from a paper, with stable id + provenance.

    The agent's only job in the proposed design: emit a yes/no on each
    clip (plus classification enums on the yes). The ``text`` is
    substring-anchored by construction — it's a literal slice of
    ``PaperSection.text``.
    """

    clip_id: str
    text: str
    section: str
    source_id: str
    paragraph_index: int  # 0-based within the section
    char_len: int
    has_target_mention: bool


def extract_paragraph_clips(
    *, source_id: str, sections: list, target_tokens: frozenset[str] = frozenset()
) -> list[ParagraphClip]:
    """Pull one ParagraphClip per JATS paragraph (single ``\\n`` boundary).

    Overlong paragraphs (> ``MAX_PARAGRAPH_CHARS``) are split at sentence
    boundaries with a small overlap region so the agent still sees enough
    context to judge. The split-clips keep the same paragraph_index but
    get a sub-letter suffix in their id (``p_results_03a`` / ``03b``).
    """

    clips: list[ParagraphClip] = []
    for sec in sections:
        paragraphs = [p for p in sec.text.split("\n") if p.strip()]
        for p_idx, para in enumerate(paragraphs):
            chunks = _split_overlong(para, MAX_PARAGRAPH_CHARS)
            for sub_idx, chunk in enumerate(chunks):
                suffix = chr(ord("a") + sub_idx) if len(chunks) > 1 else ""
                clip_id = f"p_{sec.name}_{p_idx:02d}{suffix}"
                has_target = bool(target_tokens) and any(
                    tok.lower() in chunk.lower() for tok in target_tokens
                )
                clips.append(
                    ParagraphClip(
                        clip_id=clip_id,
                        text=chunk,
                        section=sec.name,
                        source_id=source_id,
                        paragraph_index=p_idx,
                        char_len=len(chunk),
                        has_target_mention=has_target,
                    )
                )
    return clips


def _split_overlong(text: str, cap: int) -> list[str]:
    """Split a too-long paragraph at sentence boundaries with overlap.

    Each returned chunk is ≤ cap chars; chunks share the last sentence of
    the previous chunk so context flows. Substring-anchored against the
    original text by construction (we only slice, never edit characters).
    """

    if len(text) <= cap:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for sent in sentences:
        if cur_len + len(sent) + 1 > cap and cur:
            chunk_text = " ".join(cur)
            if chunk_text in text:
                chunks.append(chunk_text)
            # Carry one tail sentence as overlap if it fits within safety margin.
            if cur and len(cur[-1]) < PARAGRAPH_OVERLAP_SAFETY * 4:
                cur = [cur[-1]]
                cur_len = len(cur[-1])
            else:
                cur = []
                cur_len = 0
        cur.append(sent)
        cur_len += len(sent) + 1
    if cur:
        chunk_text = " ".join(cur)
        if chunk_text in text:
            chunks.append(chunk_text)
    # Filter out chunks that didn't substring-match (shouldn't happen for
    # JATS paragraphs but be defensive — same invariant evidence_retrieval
    # enforces).
    return [c for c in chunks if c in text]


# ---------------------------------------------------------------------------
# Agent-simulation pass — batch Haiku keep/drop per paper
# ---------------------------------------------------------------------------


KEEP_DROP_PROMPT = """You are reviewing paragraphs from a scientific paper to \
build an evidence corpus for a deep-dive surface-accessibility annotation of \
the protein **{gene}**.

For each paragraph below, decide whether it contains information that would \
be load-bearing for one or more of these evidence categories:

* Surface expression / localization (cell-surface flow cytometry, surface \
biotinylation, mass-spec surfaceome, non-permeabilized IF, IHC with membrane \
staining)
* Topology (single-pass, multi-pass, 7-TM, GPI-anchored, ECD/ICD)
* Subcellular localization including ciliary, junctional, basolateral, \
apical, dual-localization
* Tissue / cell-type expression for {gene}
* State-dependent surface presence (internalization, recycling, ligand-driven, \
post-translational gating)
* Shed / secreted form
* Epitope masking (glycan, partner protein, conformational)
* Therapeutic engagement of the ECD (clinical-stage antibodies, ADCs)
* Genetic / loss-of-function evidence connecting the protein to phenotype

Drop paragraphs that are:
* Generic background / introduction not specifically about {gene}'s surface
* Pure intracellular signaling or downstream pathway descriptions
* Acknowledgments, funding, conflicts of interest
* Pure methods recipes with no result tied to {gene}
* Schematic / figure-pointer captions without underlying data

Paragraphs to review:

{numbered_clips}

Respond ONLY with one JSON object:

{{"keep": [{{"clip_id": "p_results_03", "reason": "<short why>"}}, ...]}}

List ONLY the clips to keep. Anything not listed will be dropped. Reason \
must be ≤80 chars."""


def _format_clips_for_prompt(clips: list[ParagraphClip], max_chars_per_clip: int = 700) -> str:
    """Render clips for the Haiku batch prompt. Truncate per-clip preview
    to keep the prompt bounded — the orchestrator would feed the full clip
    when promoting, but for the keep/drop decision the first 700 chars are
    plenty of signal."""

    lines = []
    for c in clips:
        preview = c.text if len(c.text) <= max_chars_per_clip else c.text[:max_chars_per_clip] + " […]"
        lines.append(f"--- {c.clip_id} (section={c.section}, {c.char_len} chars{', target-mention' if c.has_target_mention else ''}) ---\n{preview}")
    return "\n\n".join(lines)


def _haiku_keep_drop(
    client: Anthropic, *, gene: str, clips: list[ParagraphClip]
) -> tuple[dict, dict[str, int], float]:
    """One Haiku call per paper. Returns (parsed_decisions, usage, latency_s)."""

    prompt = KEEP_DROP_PROMPT.format(
        gene=gene,
        numbered_clips=_format_clips_for_prompt(clips),
    )
    t0 = time.time()
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.time() - t0
    text_blocks = [b.text for b in resp.content if b.type == "text"]
    text = "\n".join(text_blocks).strip()
    # Strip code-fence markers if Haiku wrapped the JSON.
    fence = re.match(r"^```(?:json)?\s*([\s\S]+?)\s*```$", text)
    if fence:
        text = fence.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Haiku reply not valid JSON; storing raw: %r", text[:200])
        parsed = {"keep": [], "raw_reply": text}
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
    }
    return parsed, usage, latency


# ---------------------------------------------------------------------------
# Per-gene driver
# ---------------------------------------------------------------------------


def _pmc_sources_from_annotation(annotation_path: Path) -> list[str]:
    """Return unique PMC source_ids cited by either anchored or unanchored
    evidence rows in the gene's annotation."""

    record = json.loads(annotation_path.read_text())
    seen: dict[str, None] = {}
    for ev in record.get("evidence", []) or []:
        for span in ev.get("spans", []) or []:
            sid = span.get("source", {}).get("source_id") or ""
            if sid.startswith("PMC:") and sid not in seen:
                seen[sid] = None
        # Also pull source_ids from validation_warnings (unanchored rows
        # where spans were dropped).
        for w in ev.get("validation_warnings", []) or []:
            m = re.search(r"PMC:PMC\d+", w)
            if m and m.group(0) not in seen:
                seen[m.group(0)] = None
    return list(seen)


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("gene", help="Gene symbol (reads data/annotations/<GENE>.json for source list).")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of papers probed.")
    parser.add_argument("--no-haiku", action="store_true", help="Skip the Haiku keep/drop pass (extract only).")
    args = parser.parse_args(argv)

    ann_path = Path(f"data/annotations/{args.gene}.json")
    if not ann_path.exists():
        print(f"no annotation at {ann_path}", file=sys.stderr)
        return 1
    pmcids = _pmc_sources_from_annotation(ann_path)
    if args.limit:
        pmcids = pmcids[: args.limit]
    if not pmcids:
        print(f"no PMC sources in {ann_path}", file=sys.stderr)
        return 1
    print(f"{args.gene}: probing {len(pmcids)} PMC source(s)")

    target_tokens = frozenset({args.gene, args.gene.lower(), args.gene.upper()})
    http = open_default_client()
    client = None if args.no_haiku else Anthropic()
    retraction = _empty_retraction_index()

    per_paper: list[dict] = []
    total_cost = 0.0
    try:
        for sid in pmcids:
            pmcid = sid.split(":", 1)[1]
            print(f"\n=== {sid} ===")
            try:
                paper = fetch_fulltext(http=http, pmcid=pmcid, retraction_index=retraction)
            except Exception as exc:  # noqa: BLE001 — probe robustness
                print(f"  FETCH FAILED: {type(exc).__name__}: {exc}")
                continue
            clips = extract_paragraph_clips(
                source_id=sid, sections=paper.sections, target_tokens=target_tokens
            )
            n_target = sum(1 for c in clips if c.has_target_mention)
            print(f"  {len(clips)} paragraph clip(s) across {len(paper.sections)} section(s)")
            print(f"    target-mentions: {n_target}/{len(clips)}")
            print(f"    avg char_len: {sum(c.char_len for c in clips) // max(1, len(clips))}")
            section_counts = {}
            for c in clips:
                section_counts[c.section] = section_counts.get(c.section, 0) + 1
            for k, v in section_counts.items():
                print(f"    {k}: {v}")

            decisions: dict = {"keep": []}
            usage: dict[str, int] = {}
            latency = 0.0
            cost = 0.0
            if client is not None and clips:
                decisions, usage, latency = _haiku_keep_drop(
                    client, gene=args.gene, clips=clips
                )
                cost = cost_for_usage(UsageRecord(**usage), HAIKU_PRICING_KEY)
                total_cost += cost
                kept = decisions.get("keep", [])
                print(f"  haiku: kept {len(kept)}/{len(clips)}  (${cost:.4f}, {latency:.1f}s)")

            per_paper.append(
                {
                    "source_id": sid,
                    "title": (paper.title or "").strip(),
                    "n_clips": len(clips),
                    "n_target_mentions": n_target,
                    "clips": [asdict(c) for c in clips],
                    "haiku_decisions": decisions,
                    "haiku_usage": usage,
                    "haiku_cost_usd": cost,
                    "haiku_latency_s": latency,
                }
            )
    finally:
        http.close()

    out_path = Path(f".runs/paragraph_clip_probe_{args.gene}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "gene": args.gene,
                "papers": per_paper,
                "total_cost_usd": total_cost,
                "n_papers": len(per_paper),
                "n_clips_total": sum(p["n_clips"] for p in per_paper),
                "n_kept_total": sum(
                    len(p["haiku_decisions"].get("keep", []) or []) for p in per_paper
                ),
            },
            indent=2,
        )
    )
    print("\n=== summary ===")
    print(f"papers: {len(per_paper)}")
    print(f"clips total: {sum(p['n_clips'] for p in per_paper)}")
    if client is not None:
        kept_total = sum(len(p["haiku_decisions"].get("keep", []) or []) for p in per_paper)
        print(f"haiku kept: {kept_total}")
        print(f"haiku cost: ${total_cost:.4f}")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
