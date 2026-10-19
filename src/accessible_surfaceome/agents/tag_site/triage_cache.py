"""Per-gene cache of abstract-triage verdicts, so a re-run resumes.

Triage is one model call per discovered paper and about 90% of a run's calls —
80 to 167 of them on the control genes. Every one was recomputed from scratch on
every run, so re-running a gene after a SYNTHESIS prompt edit paid the full
triage bill again to reach the identical verdicts. Discovery already persists
(a paper found once is never lost); this gives the next stage the same property.

The key is ``(gene_symbol, paper_source_id, triage prompt_sha)``:

* **gene** because the verdict answers "is this paper about tagging THIS
  protein", not a property of the paper alone;
* **source_id** because that is the pool's own key, so a cached verdict joins
  back to the paper it judged without a second identifier to keep in step;
* **prompt_sha** because a verdict produced by a different triage prompt is
  stale, and the repo's provenance rule is explicit that a changed prompt_sha
  must re-run rather than be silently reused. Editing the triage prompt
  therefore invalidates every cached verdict automatically, with no flag to
  remember and nothing to purge;
* **input_sha** — a hash of the title and abstract the call actually saw —
  because the prompt is only half of what produced the verdict. A paper whose
  abstract is corrected, de-truncated on a later fetch, or replaced when a
  preprint is published is a DIFFERENT input, and a verdict formed on the old
  text is as stale as one formed under the old prompt. It also makes a
  source_id collision harmless rather than silent.

Only a SUCCESSFUL verdict is cached. An error outcome is a transient failure —
a timeout, a rate limit — and caching it would make one bad minute permanent.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: Beside the discovery cache: derived, regenerable, gitignored.
TRIAGE_CACHE_DIR = Path(__file__).resolve().parents[3].parent / "data/external/tag_site_triage"


def triage_prompt_sha() -> str:
    """sha256 of the exact triage system prompt in force."""
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        _SYSTEM_PROMPT_CACHED,
    )

    return hashlib.sha256(_SYSTEM_PROMPT_CACHED.encode("utf-8")).hexdigest()


def input_sha(paper: Any) -> str:
    """Hash of the text triage is shown for a paper: its title and abstract.

    Normalized only by stripping, so a whitespace-identical refetch does not
    churn the cache while any real change to the wording does."""
    title = (getattr(paper, "title", "") or "").strip()
    abstract = (getattr(paper, "abstract", "") or "").strip()
    return hashlib.sha256(f"{title}\n{abstract}".encode()).hexdigest()


def _path(gene_symbol: str, *, cache_dir: Path | None = None) -> Path:
    return Path(cache_dir or TRIAGE_CACHE_DIR) / f"{gene_symbol}.json"


def load(gene_symbol: str, *, cache_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """``{source_id: {decision, reason, prompt_sha}}`` for this gene.

    A missing, unreadable or corrupt cache is an empty dict: a stale local file
    must never take down a run, exactly as the discovery cache treats it."""
    try:
        raw = json.loads(_path(gene_symbol, cache_dir=cache_dir).read_text())
    except Exception:  # noqa: BLE001 - absent, corrupt or unreadable
        return {}
    return raw if isinstance(raw, dict) else {}


def save(
    gene_symbol: str,
    outcomes: list[Any],
    *,
    prompt_sha: str,
    inputs: dict[str, str] | None = None,
    cache_dir: Path | None = None,
) -> int:
    """Merge this run's successful verdicts into the gene's cache.

    Merge rather than replace, so a run that triaged a subset does not discard
    verdicts for papers it never looked at."""
    cached = load(gene_symbol, cache_dir=cache_dir)
    n = 0
    for o in outcomes:
        resp = getattr(o, "response", None)
        if resp is None or getattr(o, "error", None):
            continue  # a transient failure must not become permanent
        cached[o.paper_id] = {
            "decision": getattr(resp, "decision", None),
            "reason": getattr(resp, "reason", None),
            "prompt_sha": prompt_sha,
            "input_sha": (inputs or {}).get(o.paper_id),
        }
        n += 1
    path = _path(gene_symbol, cache_dir=cache_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - a cache write must never fail a run
        log.warning("could not write triage cache for %s: %s", gene_symbol, exc)
        return 0
    return n


def split(
    papers: dict[str, Any],
    cached: dict[str, dict[str, Any]],
    *,
    prompt_sha: str,
) -> tuple[list[Any], list[Any]]:
    """``(to_triage, reusable_outcomes)``.

    A cached entry is reusable only when BOTH its ``prompt_sha`` matches the
    prompt in force AND its ``input_sha`` matches the paper's current title and
    abstract. Anything else re-runs, which is the sha-aware skip the provenance
    rule requires, extended to the input the prompt was applied to.

    An entry written before ``input_sha`` existed carries None and is re-run:
    the cheap, correct reading of "we cannot tell what this verdict saw"."""
    from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
        AbstractTriageResponse,
        TriageOutcome,
    )

    to_triage: list[Any] = []
    reusable: list[Any] = []
    for source_id, paper in papers.items():
        hit = cached.get(source_id)
        if (
            not hit
            or hit.get("prompt_sha") != prompt_sha
            or hit.get("input_sha") != input_sha(paper)
        ):
            to_triage.append(paper)
            continue
        try:
            response = AbstractTriageResponse(
                paper_id=source_id,
                decision=hit["decision"],
                reason=hit.get("reason") or "",
            )
        except Exception:  # noqa: BLE001 - a malformed entry just re-triages
            to_triage.append(paper)
            continue
        reusable.append(
            TriageOutcome(
                paper_id=source_id, response=response, usage=None, elapsed_s=0.0, error=None
            )
        )
    return to_triage, reusable
