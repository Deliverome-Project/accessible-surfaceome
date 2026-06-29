"""Size the deep-dive's Modal fan-out to the Anthropic org rate limits.

The sweep runs ``claude-sonnet-4-6``. For the Sonnet 4.x tier the limits are
RPM 20K, ITPM 10M (**excluding cache reads**), OTPM 2M. Two of the three are
non-binding for this workload:

* **RPM** — ~12 ``messages.create`` calls per gene over a multi-minute
  wall-clock is a tiny request rate; at any realistic concurrency it's ~60×
  under 20K/min.
* **ITPM** — the deep-dive caches a large shared prompt, so cache reads (which
  don't count) dominate input; the uncounted-against-limit fraction is small.

**OTPM (2M output tokens / minute) is the binding constraint.** The 9 block
builders emit structured-JSON output concurrently, and a gene's total output
(drafts + repair loops + final record) is on the order of tens of thousands of
tokens. So the safe concurrency is "how many genes can run at once before their
combined output rate approaches 2M/min", with headroom left for the burstiness
of the concurrent-builder phase (the backoff loop in ``api_retry`` absorbs the
rest).

These are estimates (per-gene output is inferred from canary record sizes, not
measured token counts — refine ``DEFAULT_PER_GENE_OUTPUT_TOKENS`` from the
``deep_dive_run`` token columns once D1 is reachable). They drive a *default*;
every input is overridable via env so an operator can dial concurrency up after
watching real OTPM headroom on the canary.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Anthropic Sonnet 4.x org limits (the binding one is OTPM).
SONNET_OTPM_LIMIT = 2_000_000
SONNET_RPM_LIMIT = 20_000

# Estimated output tokens per gene across all model calls (intermediate drafts +
# repair loops + final record), and the typical per-gene wall-clock. The OTPM
# ceiling is the ratio of these scaled to a minute.
DEFAULT_PER_GENE_OUTPUT_TOKENS = 90_000
DEFAULT_GENE_WALL_S = 300.0

# Leave 40% of OTPM as headroom for the concurrent-builder burst + backoff.
DEFAULT_OTPM_HEADROOM = 0.6


def per_gene_otpm(
    output_tokens: float = DEFAULT_PER_GENE_OUTPUT_TOKENS,
    gene_wall_s: float = DEFAULT_GENE_WALL_S,
) -> float:
    """Steady-state output-tokens-per-minute a single gene contributes."""
    return output_tokens / (max(gene_wall_s, 1.0) / 60.0)


def recommended_gene_concurrency(
    *,
    otpm_limit: float = SONNET_OTPM_LIMIT,
    output_tokens: float = DEFAULT_PER_GENE_OUTPUT_TOKENS,
    gene_wall_s: float = DEFAULT_GENE_WALL_S,
    headroom: float = DEFAULT_OTPM_HEADROOM,
) -> int:
    """Max concurrent genes that keeps expected OTPM under ``headroom × limit``.

    Returns at least 1. With the defaults this is ~66 (1.2M ÷ 18K), i.e. an
    order of magnitude below the old ``200 × 4 = 800`` fan-out, which sat ~6-8×
    over the OTPM ceiling and would have churned 429s instead of pacing.
    """
    rate = per_gene_otpm(output_tokens, gene_wall_s)
    return max(1, int((headroom * otpm_limit) / rate))


def resolve_gene_concurrency() -> tuple[int, int]:
    """Resolve ``(max_containers, max_inputs)`` for ``annotate_one`` from env.

    The OTPM-safe quantity is the **total** concurrent genes
    (``max_containers × max_inputs``), not the container count alone, so:

    * ``SURFACEOME_MAX_INPUTS`` — concurrent genes *per container*; defaults to 1
      so two genes' builder thread-pools don't contend on one small container.
    * ``SURFACEOME_MAX_CONTAINERS`` — if set, used verbatim (and we *warn* when
      ``containers × inputs`` exceeds the OTPM recommendation). If unset, derived
      as ``recommended_total // max_inputs`` so raising ``MAX_INPUTS`` alone can't
      silently push total concurrency over the limit.

    The recommendation itself is tunable via ``SURFACEOME_PER_GENE_OUTPUT_TOKENS``
    (total output tokens per gene — **not** a per-minute rate) and
    ``SURFACEOME_GENE_WALL_S``.
    """
    output_tokens = float(
        os.environ.get(
            "SURFACEOME_PER_GENE_OUTPUT_TOKENS", DEFAULT_PER_GENE_OUTPUT_TOKENS
        )
    )
    gene_wall_s = float(os.environ.get("SURFACEOME_GENE_WALL_S", DEFAULT_GENE_WALL_S))
    recommended_total = recommended_gene_concurrency(
        output_tokens=output_tokens, gene_wall_s=gene_wall_s
    )

    max_inputs = max(1, int(os.environ.get("SURFACEOME_MAX_INPUTS") or 1))
    containers_env = os.environ.get("SURFACEOME_MAX_CONTAINERS")
    if containers_env:
        max_containers = max(1, int(containers_env))
        total = max_containers * max_inputs
        if total > recommended_total:
            logger.warning(
                "configured concurrency %d (%d containers × %d inputs) exceeds the "
                "OTPM-safe recommendation of %d concurrent genes; expect Anthropic "
                "backoff / 429s unless the per-gene output estimate is conservative",
                total,
                max_containers,
                max_inputs,
                recommended_total,
            )
    else:
        # Derive containers so total ≈ recommendation regardless of max_inputs.
        max_containers = max(1, recommended_total // max_inputs)
    return max_containers, max_inputs


__all__ = [
    "DEFAULT_GENE_WALL_S",
    "DEFAULT_OTPM_HEADROOM",
    "DEFAULT_PER_GENE_OUTPUT_TOKENS",
    "SONNET_OTPM_LIMIT",
    "SONNET_RPM_LIMIT",
    "per_gene_otpm",
    "recommended_gene_concurrency",
    "resolve_gene_concurrency",
]
