"""Lock in the prompt-caching invariants the v2 deep-dive relies on.

Anthropic's prompt cache is a **prefix match** — every byte of the rendered
prompt up to each ``cache_control`` breakpoint is part of the cache key. A
single byte difference anywhere in the prefix invalidates everything after
it, dropping ``cache_read_input_tokens`` to zero across calls without raising
any error.

The v2 deep-dive's cost model assumes the static system prompts cache
cross-gene (synthesizer + 4 plan_trim_select + 7 block builders + abstract
triage = ~36K tokens of byte-identical system per gene; ~$550-1300 net
savings on a full 5,680-gene cohort run at Sonnet 4.6 pricing). If a silent
invalidator slips into a prompt-assembly path, those savings silently
collapse to zero. This test makes that regression noisy.

What's checked
--------------
Each invariant is one test function; failures are pinpointed with file +
line + remediation guidance:

1. **No invalidator patterns in prompt-assembly paths.** ``datetime.now()``,
   ``uuid.*``, ``secrets.token_hex``, ``random.*``, ``time.time()`` —
   anything that would change byte-for-byte on every call. Restricted to
   the modules that build the cached prefix (see ``PROMPT_BUILDER_FILES``).
2. **All cached system prompts are byte-identical across reads.** Every
   ``*_system.md`` file under the agent prompt directories produces the
   same ``cached_system()`` output on two consecutive calls. Catches a
   linter mid-edit, a stray BOM, or filesystem encoding drift.
3. **json.dumps() calls in prompt-builder code use sort_keys=True.**
   Without it, dict key ordering varies across Python builds and the
   cached prefix's bytes vary between callers.
4. **Model + max_tokens are module-level constants.** Per-call variation
   forces a different cache pool (different model) or a different request
   shape (different max_tokens), neither of which read the prior cache.

The test ALSO records the realistic cross-gene cacheable token count per
gene — if someone trims the synthesizer prompt by 40% without realising,
the asserted savings projection in the v2 cost model needs revisiting.

What this test does NOT cover
-----------------------------
- Modal fan-out cold-start (the documented "warm one gene first, then fan
  out" requirement) — a runtime workflow concern, not a static prompt
  property.
- The per-gene USER message (synthesizer's evidence ledger) — by design
  it differs across genes; only its **within-gene repair-loop** cache is
  load-bearing, and the rotating breakpoint pattern in
  ``_support.payload.mark_latest_tool_result_for_cache`` handles that.
- Whether ``ANTHROPIC_API_KEY`` is set / whether the live Anthropic API
  actually serves these prompts from cache — that's a network call,
  belongs behind ``--run-network``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "accessible_surfaceome" / "agents"

# Modules that BUILD the cached prefix. A new one is added when a new agent
# starts caching its system prompt — extend this list, don't widen the scan
# (a wider scan adds false positives from log strings and CLI defaults).
PROMPT_BUILDER_FILES: tuple[Path, ...] = (
    SRC_ROOT / "_support" / "payload.py",
    SRC_ROOT / "surfaceome_synthesizer" / "runner.py",
    SRC_ROOT / "plan_trim_select" / "runner.py",
    SRC_ROOT / "plan_trim_select" / "kickoff_templates.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "_common.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "methods.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "evidence_grade.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "expression.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "contradictions.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "subcellular_localization.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "accessibility_modulation.py",
    SRC_ROOT / "surfaceome_v2" / "builders" / "anatomical_accessibility.py",
)

# Per-gene-varying tokens that would invalidate the cached prefix if they
# landed in it. Each tuple is ``(regex, human-readable-remediation)``.
INVALIDATOR_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"\bdatetime\.(now|today|utcnow)\b",
        "datetime.now() in a cached prefix changes the bytes on every "
        "request. Pin a constant at module-import time OR move the "
        "timestamp into the user message (after the cache breakpoint).",
    ),
    (
        r"\btime\.(time|monotonic)\(\)",
        "time.time() / time.monotonic() in a cached prefix changes every "
        "call. Either pin a constant or move it past the breakpoint.",
    ),
    (
        r"\buuid\.(uuid[1345]|UUID)\b",
        "uuid.uuid4() in a cached prefix makes every request unique. "
        "Use a constant request-id outside the cached blocks.",
    ),
    (
        r"\bsecrets\.token_hex\b",
        "secrets.token_hex in a cached prefix → unique-per-request bytes. "
        "Move outside the cached blocks.",
    ),
    (
        r"\brandom\.(random|choice|randint|sample|shuffle|uniform)\b",
        "random.* in a cached prefix randomizes the cache key. Pin a "
        "seed at module load OR move past the breakpoint.",
    ),
    (
        r"\bos\.urandom\b",
        "os.urandom in a cached prefix → cache hit rate drops to zero. "
        "Use a module-level constant.",
    ),
)

# Per-builder system-prompt directories. The byte-identical check below
# walks every ``*_system.md`` here.
PROMPT_MD_DIRS: tuple[Path, ...] = (
    SRC_ROOT / "surfaceome_synthesizer" / "prompts",
    SRC_ROOT / "plan_trim_select" / "prompts",
    SRC_ROOT / "surfaceome_v2" / "prompts",
)


def _fingerprint(payload: object) -> str:
    """Stable 16-char hex of the JSON-serialized payload."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def test_prompt_assembly_files_exist() -> None:
    """Guard the guard — when a prompt-builder file moves or gets renamed,
    fail this test rather than silently scanning the wrong set of files.

    If a builder is intentionally retired, REMOVE it from
    ``PROMPT_BUILDER_FILES`` in the same PR.
    """
    missing = [str(p.relative_to(REPO_ROOT)) for p in PROMPT_BUILDER_FILES if not p.exists()]
    assert not missing, (
        "Prompt-builder files have moved or been renamed:\n  "
        + "\n  ".join(missing)
        + "\nUpdate PROMPT_BUILDER_FILES in this test to match the new "
        "layout. Don't widen the scan to a directory glob — false "
        "positives from log strings and CLI defaults make the test noisy."
    )


def test_no_silent_invalidators_in_prompt_paths() -> None:
    """No datetime/uuid/random/secrets calls in the prompt-assembly paths.

    These patterns would change the cached prefix byte-for-byte on every
    request, dropping cross-gene cache reads silently. Restricted to the
    files in ``PROMPT_BUILDER_FILES`` so a timestamp in unrelated code
    (logging, CLI default) doesn't fail this test.

    To unblock a real failure: read the docstring next to each
    INVALIDATOR_PATTERNS entry. The fix is almost always "move the
    varying value to the user message" or "pin it as a module constant".
    """
    hits: list[tuple[Path, int, str, str]] = []
    for path in PROMPT_BUILDER_FILES:
        if not path.exists():
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            # Skip comment-only lines (regex below is line-based, not AST)
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pattern, remediation in INVALIDATOR_PATTERNS:
                if re.search(pattern, line):
                    hits.append((path, lineno, line.strip(), remediation))
    if not hits:
        return
    msg_lines = [
        "Silent cache-invalidator patterns found in prompt-assembly paths.",
        "Every byte of the cached prefix is part of the cache key — these "
        "patterns make every request unique and silently drop cache reads "
        "to zero (no error, just zero savings).\n",
    ]
    for path, lineno, snippet, remediation in hits:
        rel = path.relative_to(REPO_ROOT)
        msg_lines.append(f"  {rel}:{lineno}  {snippet}")
        msg_lines.append(f"      Fix: {remediation}\n")
    pytest.fail("\n".join(msg_lines))


def test_json_dumps_in_prompt_paths_uses_sort_keys() -> None:
    """``json.dumps()`` without ``sort_keys=True`` produces non-deterministic
    output across Python builds. In a cached prefix that means intermittent
    cache misses on the same input.

    Allowed exception: ``json.dumps(...)`` that calls a serializer with no
    dict argument (e.g. serializing a primitive int). The regex below is
    narrow enough to allow that — it triggers only when the call site
    visibly dumps a structure but omits sort_keys. To allowlist a real
    call (rare), inline-comment ``# noqa: prompt-caching`` on the line.
    """
    bad: list[tuple[Path, int, str]] = []
    for path in PROMPT_BUILDER_FILES:
        if not path.exists():
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "json.dumps" not in line:
                continue
            if "noqa: prompt-caching" in line:
                continue
            # Allowed shapes: ``sort_keys=True`` anywhere on the line OR
            # the next continuation line. Cheap inspection: peek ahead.
            peek = line
            if line.rstrip().endswith(("(", ",")):
                # Multi-line call — peek up to 5 lines forward
                tail = text.splitlines()[lineno : lineno + 5]
                peek = line + " " + " ".join(tail)
            if "sort_keys=True" in peek or "sort_keys = True" in peek:
                continue
            bad.append((path, lineno, line.strip()))
    if not bad:
        return
    msg_lines = [
        "json.dumps() without sort_keys=True found in prompt-assembly paths.",
        "Dict key order is implementation-defined; the same input can "
        "produce different bytes on different Python builds and "
        "intermittently invalidate the cache.\n",
        "Add sort_keys=True to each call, or annotate with "
        "# noqa: prompt-caching if the call really doesn't serialize a "
        "dict.\n",
    ]
    for path, lineno, snippet in bad:
        rel = path.relative_to(REPO_ROOT)
        msg_lines.append(f"  {rel}:{lineno}  {snippet}")
    pytest.fail("\n".join(msg_lines))


def test_all_cached_system_prompts_are_byte_identical_across_reads() -> None:
    """Every ``*_system.md`` file produces byte-identical bytes on two reads.

    Trivially true today (it's just ``Path.read_text()``), but this test
    catches:
    * A linter mid-edit that touched the file between two reads.
    * Encoding drift (BOM, line endings) introduced by a Windows commit.
    * A future refactor that switches to a templated prompt with a
      timestamp interpolation — every templated read would differ.

    On failure: diff the two reads. If they differ, the prompt is being
    mutated under the test's feet (likely a pre-commit hook or watcher).
    """
    from accessible_surfaceome.agents._support.payload import cached_system

    mismatches: list[tuple[Path, str, str]] = []
    n_checked = 0
    for prompt_dir in PROMPT_MD_DIRS:
        if not prompt_dir.exists():
            continue
        for md_path in sorted(prompt_dir.glob("*_system.md")):
            block_a = cached_system(md_path.read_text())
            block_b = cached_system(md_path.read_text())
            n_checked += 1
            if block_a != block_b:
                mismatches.append(
                    (md_path, _fingerprint(block_a), _fingerprint(block_b))
                )
    assert n_checked >= 5, (
        f"Expected to scan at least 5 system prompts, scanned {n_checked}. "
        "PROMPT_MD_DIRS may be out of date — extend it when a new prompt "
        "directory is added."
    )
    if mismatches:
        msg_lines = ["System prompts read differently on two consecutive reads.\n"]
        for path, sha_a, sha_b in mismatches:
            rel = path.relative_to(REPO_ROOT)
            msg_lines.append(f"  {rel}: read1={sha_a} read2={sha_b}")
        msg_lines.append(
            "\nLikely cause: a linter or watcher is mutating the file under "
            "the test. Confirm by running this test twice in a row — if "
            "the SHAs differ between runs, something is rewriting the .md."
        )
        pytest.fail("\n".join(msg_lines))


def test_synthesizer_model_and_max_tokens_are_module_constants() -> None:
    """``AGENT_MODEL`` and ``MAX_TOKENS`` for the synthesizer are
    module-level constants, not parameters.

    The cache is scoped per ``(model, prompt)`` pair — switching models
    invalidates the cache. Likewise ``max_tokens`` is part of the request
    shape and a varying value (e.g. ``max_tokens = round(some_estimate)``)
    would prevent the cache from coalescing.

    If you intentionally make either dynamic, document the cache impact in
    the docstring and update this test.
    """
    from accessible_surfaceome.agents.surfaceome_synthesizer import runner

    assert isinstance(getattr(runner, "AGENT_MODEL", None), str), (
        "synthesizer.runner.AGENT_MODEL must be a module-level string "
        "constant. The cache pool is keyed on (model, prompt) — a "
        "per-gene model selector silently invalidates cross-gene cache "
        "reads."
    )
    assert isinstance(getattr(runner, "MAX_TOKENS", None), int), (
        "synthesizer.runner.MAX_TOKENS must be a module-level int constant. "
        "A per-call max_tokens changes the request shape and breaks the "
        "cross-gene cache."
    )


def test_cacheable_system_prompt_token_budget_within_expected_range() -> None:
    """Sanity-check the total cacheable system-prompt size per gene.

    The v2 cost model assumes ~36K tokens of byte-identical system prompts
    cache cross-gene (synthesizer + 4 plan_trim_select + 7 block builders +
    abstract_triage). If someone trims a prompt by 50% without realising,
    or if a new builder is added that pushes the total above the band,
    the asserted ~$550-1300 cohort-run savings projection needs revisiting.

    The band below is intentionally wide: this is a smoke test, not a
    contract. A drift outside it should prompt a manual look at whether
    the cost-savings projection still holds.
    """
    chars_per_token = 4.0  # English prose; Sonnet tokenizer estimate
    md_files = []
    for prompt_dir in PROMPT_MD_DIRS:
        if prompt_dir.exists():
            md_files.extend(sorted(prompt_dir.glob("*_system.md")))
    total_chars = sum(p.read_text().__len__() for p in md_files)
    approx_tokens = total_chars / chars_per_token
    assert 20_000 <= approx_tokens <= 80_000, (
        f"Cacheable system-prompt budget drifted to ~{approx_tokens:,.0f} "
        f"tokens (from {len(md_files)} *_system.md files). Expected band: "
        f"20,000-80,000. If a prompt was trimmed deliberately, the v2 "
        f"cost-savings projection in tests/test_prompt_caching_invariants.py "
        f"and docs need updating; if a prompt grew unintentionally, "
        f"investigate. Sizes:\n  "
        + "\n  ".join(
            f"{p.relative_to(REPO_ROOT)}: {p.read_text().__len__():>6} chars"
            for p in md_files
        )
    )
