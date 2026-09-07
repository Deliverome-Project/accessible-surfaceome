"""Probe prompt-cache engagement on the two paths that observed 0/0 caches.

D1 intermediates on TGOLN2 showed:
    builders_a1 / builders_a2 (Sonnet)   — cache_creation=0, cache_read=0
    plan_trim_select_a1 trim (Haiku)     — cache_creation=0, cache_read=0
    synthesizer (Sonnet)                  — cache_creation=39,663, cache_read=39,663

Only the synthesizer is cache-engaging. This probe isolates why the others
aren't, by issuing 2 sequential ``messages.create`` calls per config and
reading the ``usage.cache_creation_input_tokens`` /
``usage.cache_read_input_tokens`` fields from the response.

Configs tested:

1. **Methods builder (Sonnet) with web-search tool + cached_system only.**
   Mirrors today's call shape.
2. **Methods builder (Sonnet) without tools, cached_system only.**
   Isolates whether the ``tools=`` kwarg breaks caching.
3. **Methods builder (Sonnet) with web-search tool + cache_control on the
   LAST tool entry too.** Tests whether marking tools restores the cache.
4. **Haiku trim with cached system (today's shape).** Confirms whether the
   ~2.5k-token cached prefix is under the Haiku 4.5 minimum (per Anthropic
   docs: Haiku 4.5 requires 4,096 tokens to cache).
5. **Haiku trim with cached system that has been padded to push the cached
   prefix above 4,096 tokens.** Confirms (5) is a size issue, not a shape
   issue.

We also call ``client.messages.count_tokens`` on each cached_system block
so we can read off the actual token count of the cached prefix without
issuing a real ``messages.create``.

Run:
    uv run python scripts/probe_cache_engagement.py

Cost: ~$0.10 total — 5 configs × 2 calls × ~5k input tokens at most.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.payload import cached_system
from accessible_surfaceome.agents.plan_trim_select.runner import (
    HAIKU_MODEL,
    _split_trim_template,
)
from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
    SONNET_MODEL,
    load_prompt,
)
from accessible_surfaceome.env import load_env

# Mirrors agents.surfaceome_v2.builders.methods._WEB_SEARCH_TOOL
_WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
]

# A trivial but non-empty user task — small enough that we measure the
# cached-prefix behavior, not output cost. The cache hit/miss depends on
# the cached SYSTEM block + tools, not the user message.
_FAKE_BUILDER_USER = (
    "# Gene: TGOLN2\n\n"
    "## a1_evi_01 (flow_cytometry, cited)\n"
    "Verbatim quote: Surface staining of HEK293 cells with anti-TGOLN2 mAb showed positive signal in flow cytometry.\n"
    "## a1_evi_02 (surface_biotinylation, cited)\n"
    "Verbatim quote: Biotinylation of intact HeLa cells followed by streptavidin pulldown recovered TGOLN2 in surface fraction.\n\n"
    "Emit one fenced ```json block — a JSON ARRAY of MethodObservation entries. "
    "Empty array `[]` is acceptable if no panel can be assembled.\n"
)

_FAKE_TRIM_PAPER_ID = "PMC:11992999"
_FAKE_TRIM_CLIPS = (
    "--- pmc_11992999_results_01 (section=results, score=4.2, hallmark=surface biotinylation) ---\n"
    "Cell-surface biotinylation of intact HEK293 cells with sulfo-NHS-SS-biotin "
    "followed by streptavidin pulldown and Western blot recovered TGOLN2 "
    "in the surface fraction.\n\n"
    "--- pmc_11992999_methods_02 (section=methods, score=2.1, hallmark=antibody clone) ---\n"
    "Anti-TGOLN2 polyclonal antibody (Sigma HPA012723, RRID:AB_1855739) was "
    "used at 1:200 dilution; specificity was confirmed with siRNA knockdown "
    "in HeLa cells.\n"
)

# Pad text we paste in to push a cached prefix above a target token count.
# We use plain ASCII so token counts stay roughly predictable (~4 chars/token
# for English prose).
_PADDING_BLOCK = (
    "## Notes (gene-agnostic) — padding to push the cached prefix above "
    "Haiku's documented 4,096-token cache minimum. None of this changes the "
    "model's behavior, since the trim task instructions stay identical above. "
    "We document the cache mechanism here so the cached prefix carries the "
    "behavioral spec verbatim and we don't accidentally rely on padding for "
    "correctness. Cached: the rules block above (about which clips are load-"
    "bearing, which to drop, calibration). Per-call: the paper id, the clip "
    "pool, and the requested output schema. "
)


@dataclass
class CacheTrace:
    label: str
    cached_prefix_tokens: int | None  # via count_tokens()
    call1_input: int
    call1_cache_create: int
    call1_cache_read: int
    call2_input: int
    call2_cache_create: int
    call2_cache_read: int
    cost_usd_estimate: float  # not authoritative — just a rough total spend


def _measure(
    client: Anthropic,
    label: str,
    *,
    model: str,
    cached_system_blocks: list[dict[str, Any]],
    user: str,
    tools: list[dict[str, Any]] | None = None,
    cached_prefix_tokens: int | None = None,
) -> CacheTrace:
    """Issue two sequential messages.create calls, return cache traces.

    The 5-min ephemeral TTL means the second call (issued ~immediately) is
    when we expect a cache_read > 0 if caching is working.
    """
    print(f"\n=== {label} ===")
    if cached_prefix_tokens is not None:
        print(f"  cached_system tokens (via count_tokens): {cached_prefix_tokens}")

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 256,  # cap output; we only care about input/cache fields
        "system": cached_system_blocks,
        "messages": [{"role": "user", "content": user}],
    }
    if tools is not None:
        kwargs["tools"] = tools

    # Call 1 (cache write)
    resp1 = client.messages.create(**kwargs)
    u1 = resp1.usage
    print(
        f"  call 1: input={u1.input_tokens} "
        f"cwrite={u1.cache_creation_input_tokens} "
        f"cread={u1.cache_read_input_tokens} "
        f"output={u1.output_tokens}"
    )

    # Brief pause, well within the 5-minute TTL but enough that we don't
    # accidentally race the cache writer.
    time.sleep(2.0)

    # Call 2 (expected cache read if working)
    resp2 = client.messages.create(**kwargs)
    u2 = resp2.usage
    print(
        f"  call 2: input={u2.input_tokens} "
        f"cwrite={u2.cache_creation_input_tokens} "
        f"cread={u2.cache_read_input_tokens} "
        f"output={u2.output_tokens}"
    )

    # Rough cost estimate (Sonnet 4.6: $3/M input, $0.30/M cache read,
    # $3.75/M cache write; Haiku 4.5: $1/M input, $0.10/M cache read,
    # $1.25/M cache write).
    if "sonnet" in model:
        i_rate, cw_rate, cr_rate, o_rate = 3.0, 3.75, 0.30, 15.0
    else:
        i_rate, cw_rate, cr_rate, o_rate = 1.0, 1.25, 0.10, 5.0
    total_in = u1.input_tokens + u2.input_tokens
    total_cw = (u1.cache_creation_input_tokens or 0) + (u2.cache_creation_input_tokens or 0)
    total_cr = (u1.cache_read_input_tokens or 0) + (u2.cache_read_input_tokens or 0)
    total_out = u1.output_tokens + u2.output_tokens
    cost = (
        (total_in * i_rate + total_cw * cw_rate + total_cr * cr_rate + total_out * o_rate)
        / 1_000_000
    )
    print(f"  estimated cost (both calls): ${cost:.4f}")
    return CacheTrace(
        label=label,
        cached_prefix_tokens=cached_prefix_tokens,
        call1_input=u1.input_tokens,
        call1_cache_create=u1.cache_creation_input_tokens or 0,
        call1_cache_read=u1.cache_read_input_tokens or 0,
        call2_input=u2.input_tokens,
        call2_cache_create=u2.cache_creation_input_tokens or 0,
        call2_cache_read=u2.cache_read_input_tokens or 0,
        cost_usd_estimate=cost,
    )


def _count_tokens_for_cached_prefix(
    client: Anthropic,
    *,
    model: str,
    system: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int | None:
    """Use messages.count_tokens to measure the cached prefix (system + tools).

    Sends a tiny dummy user message so the API call validates, but the
    interesting figure is roughly the system+tools token count.

    Returns ``None`` when count_tokens can't be called (the API refuses
    server-side tools like ``web_search_20250305`` in count_tokens; we
    fall back to reading input_tokens off the real ``messages.create``
    response in that case).
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "system": system,
        "messages": [{"role": "user", "content": "ping"}],
    }
    if tools is not None:
        kwargs["tools"] = tools
    try:
        return client.messages.count_tokens(**kwargs).input_tokens
    except Exception as exc:  # noqa: BLE001 — diagnostic-only fallback
        print(f"  (count_tokens unavailable: {type(exc).__name__}: {exc!s:.120s})")
        return None


def main() -> int:
    load_env()
    client = get_client()
    traces: list[CacheTrace] = []

    # --- Sonnet methods builder ---
    methods_system = load_prompt("methods_builder_system")
    sonnet_sys_blocks = cached_system(methods_system)

    # Config 1: today's shape — tools=web_search, cache_control on system only
    n_tokens = _count_tokens_for_cached_prefix(
        client, model=SONNET_MODEL, system=sonnet_sys_blocks, tools=_WEB_SEARCH_TOOL
    )
    traces.append(
        _measure(
            client,
            "Sonnet methods: cached system + web_search tool (TODAY'S SHAPE)",
            model=SONNET_MODEL,
            cached_system_blocks=sonnet_sys_blocks,
            user=_FAKE_BUILDER_USER,
            tools=_WEB_SEARCH_TOOL,
            cached_prefix_tokens=n_tokens,
        )
    )

    # Config 2: same system, NO tools — isolates whether tools= breaks caching
    n_tokens = _count_tokens_for_cached_prefix(
        client, model=SONNET_MODEL, system=sonnet_sys_blocks
    )
    traces.append(
        _measure(
            client,
            "Sonnet methods: cached system, NO TOOLS (control)",
            model=SONNET_MODEL,
            cached_system_blocks=sonnet_sys_blocks,
            user=_FAKE_BUILDER_USER,
            tools=None,
            cached_prefix_tokens=n_tokens,
        )
    )

    # Config 3: tools=web_search WITH cache_control on the tool entry too —
    # tests the documented "mark the last tool with cache_control to cache
    # the tools block" recipe.
    tools_with_cc: list[dict[str, Any]] = [
        {
            **_WEB_SEARCH_TOOL[0],
            "cache_control": {"type": "ephemeral"},
        }
    ]
    n_tokens = _count_tokens_for_cached_prefix(
        client, model=SONNET_MODEL, system=sonnet_sys_blocks, tools=tools_with_cc
    )
    traces.append(
        _measure(
            client,
            "Sonnet methods: cached system + tools w/ cache_control on tool (PROPOSED FIX)",
            model=SONNET_MODEL,
            cached_system_blocks=sonnet_sys_blocks,
            user=_FAKE_BUILDER_USER,
            tools=tools_with_cc,
            cached_prefix_tokens=n_tokens,
        )
    )

    # --- Haiku trim ---
    a1_trim_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "accessible_surfaceome"
        / "agents"
        / "plan_trim_select"
        / "prompts"
        / "a1_trim_system.md"
    )
    a1_trim_template = a1_trim_path.read_text()
    # Mirrors runner._run_trim — TrimResponse schema serialized identically
    from accessible_surfaceome.agents.plan_trim_select.schemas import TrimResponse

    schema_str = json.dumps(TrimResponse.model_json_schema(), indent=2, sort_keys=True)
    cached_text, user_template = _split_trim_template(a1_trim_template, schema_str)
    haiku_sys_blocks = cached_system(cached_text)
    user_msg = (
        "Target gene: TGOLN2\n\n"
        + user_template.format(
            gene="TGOLN2",
            paper_id=_FAKE_TRIM_PAPER_ID,
            n_clips=2,
            numbered_clips=_FAKE_TRIM_CLIPS,
            schema=schema_str,
        )
    )

    # Config 4: today's shape — Haiku trim, cached_system ~2.5k tokens
    n_tokens_today = _count_tokens_for_cached_prefix(
        client, model=HAIKU_MODEL, system=haiku_sys_blocks
    )
    traces.append(
        _measure(
            client,
            "Haiku trim: cached system (TODAY'S SHAPE, ~2.5k cached tokens)",
            model=HAIKU_MODEL,
            cached_system_blocks=haiku_sys_blocks,
            user=user_msg,
            cached_prefix_tokens=n_tokens_today,
        )
    )

    # Config 5: padded cached_system — force above Haiku's 4096-token min
    # We need to add ~5k-token's worth of stable, byte-identical-across-calls
    # text. Repeat the padding block enough times to push above the floor.
    # n_tokens_today is ``int | None`` — None when count_tokens errored; in
    # that case fall back to a conservative ~2.5k assumption (matches the
    # measured a1_trim cached prefix).
    today_tokens = n_tokens_today if n_tokens_today is not None else 2500
    n_pad_repeats_needed = max(1, (5000 - today_tokens) // 150 + 1)
    padded_text = cached_text + "\n\n" + (_PADDING_BLOCK + "\n") * n_pad_repeats_needed
    haiku_padded_blocks = cached_system(padded_text)
    n_tokens_padded = _count_tokens_for_cached_prefix(
        client, model=HAIKU_MODEL, system=haiku_padded_blocks
    )
    traces.append(
        _measure(
            client,
            f"Haiku trim: cached system PADDED to {n_tokens_padded} tokens (>4096 min)",
            model=HAIKU_MODEL,
            cached_system_blocks=haiku_padded_blocks,
            user=user_msg,
            cached_prefix_tokens=n_tokens_padded,
        )
    )

    # --- Summary ---
    print("\n\n=== SUMMARY ===")
    print(
        f"{'config':<70s}  {'cached_tok':>10s}  "
        f"{'c1_cw':>6s}  {'c1_cr':>6s}  {'c2_cw':>6s}  {'c2_cr':>6s}"
    )
    for t in traces:
        print(
            f"{t.label:<70s}  {(str(t.cached_prefix_tokens) if t.cached_prefix_tokens else '-'):>10s}  "
            f"{t.call1_cache_create:>6d}  {t.call1_cache_read:>6d}  "
            f"{t.call2_cache_create:>6d}  {t.call2_cache_read:>6d}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
