"""Grade internalization by mode (basal / native-ligand / therapeutic /
pathogen_entry) from the span-verified evidence ledger (Sonnet).

Emits a ``LiteratureLLMOut``, then runs deterministic post-processing:
1. scrubs unknown ``cited_source_ids`` across ALL modes (including
   ``pathogen_entry``), ``observations``, and ``modulator_observations``;
2. sanitizes bogus ``rate_value`` entries (bare time points or non-uptake units
   like cAMP/peptide matches), infers missing species from unambiguous canonical
   cell lines, corrects ADC/therapeutic-antibody observations misfiled into
   ``basal``, and keeps ``overall_grade`` consistent with the three delivery
   modes (never driven by ``pathogen_entry`` alone).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from accessible_surfaceome.agents.internalization.benchmark import (
    check_observation_mode_issue,
    check_observation_quant_issue,
)
from accessible_surfaceome.agents.internalization.model_prior import (
    SONNET_MODEL,
    call_model_structured,
)
from accessible_surfaceome.agents.internalization.models import (
    Grade,
    InternalizationObservation,
    InternalizationQuant,
    LiteratureLLMOut,
)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "literature_grade_system.md"
_MAX_TOKENS_GRADE = 24_000

_GRADE_RANK: dict[str, int] = {
    "high": 4,
    "moderate": 3,
    "low": 2,
    "no": 1,
    "unknown": 0,
}

# Unambiguous canonical cell lines -> species fallback when the LLM leaves
# ``obs.species`` null despite naming the line (e.g. FOLH1 LNCaP / PC-3).
_CELL_LINE_SPECIES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:hela|hepg2|hek[-\s]?293\w*|293t|sk[-\s]?br[-\s]?3|skbr3|"
            r"bt[-\s]?474|bt474|a431|lncap|pc[-\s]?3|u2os|u[-\s]?2\s*os|"
            r"mcf[-\s]?7|mcf7|jurkat|k562|huvec|mda[-\s]?mb[-\s]?\d+|"
            r"raji|daudi|namalwa|ca46|h441|h1975|a549|h520|ls174t|sw[-\s]?1222|"
            r"lim1215|htcepi|aml193|caco[-\s]?2|thp[-\s]?1|u937|hl[-\s]?60|"
            r"nci[-\s]?h\d+|t47d|t[-\s]?47d|calu[-\s]?3|du[-\s]?145|c4[-\s]?2|"
            r"mm1\.?s|rpmi[-\s]?8226|opm[-\s]?2|n87|nci[-\s]?n87|oe19|ovcar\d*|"
            r"skov[-\s]?3|hct[-\s]?116|ht[-\s]?29|sw480|sw620|panc[-\s]?1|"
            r"mia[-\s]?paca|abc[-\s]?1)\b",
            re.IGNORECASE,
        ),
        "human",
    ),
    (
        re.compile(
            r"\b(?:3t3[-\s]?l1|nih[-\s]?3t3|mef|mefs|b16\w*|ct26|4t1|raw\s*264\.7|"
            r"ba/?f3|el4|mc38|llc1)\b",
            re.IGNORECASE,
        ),
        "mouse",
    ),
    (
        re.compile(r"\b(?:rbl[-\s]?2h3|rbl\b|pc[-\s]?12|nrk|gh3)\b", re.IGNORECASE),
        "rat",
    ),
    (
        re.compile(r"\b(?:cho[-\s]?k1|cho\b)\b", re.IGNORECASE),
        "hamster",
    ),
    (
        re.compile(r"\b(?:mdck|mdck[-\s]?ii)\b", re.IGNORECASE),
        "dog",
    ),
    (
        re.compile(r"\b(?:vero|cos[-\s]?7|cos[-\s]?1|ma104)\b", re.IGNORECASE),
        "monkey",
    ),
    (
        re.compile(r"\b(?:llc[-\s]?pk1\w*)\b", re.IGNORECASE),
        "pig",
    ),
)

_BARE_TIME_UNIT_RE = re.compile(
    r"^(?:s|sec|secs|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
    re.IGNORECASE,
)


def load_grade_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _render_evidence(evidence: list[Any]) -> str:
    lines: list[str] = []
    for e in evidence:
        span = e.spans[0] if getattr(e, "spans", None) else None
        source_id = span.source.source_id if span else "?"
        quote = span.quote if span else ""
        lines.append(f"[{e.evidence_id}] ({source_id}) {e.claim} | quote: {quote}")
    return "\n".join(lines)


# Light normalization of the per-observation species strings the model emits
# ("Homo sapiens" -> "human", etc.) so the rollup below buckets consistently.
_SPECIES_ALIASES = {
    "homo sapiens": "human",
    "h. sapiens": "human",
    "hsapiens": "human",
    "mus musculus": "mouse",
    "m. musculus": "mouse",
    "murine": "mouse",
    "rattus norvegicus": "rat",
    "macaca fascicularis": "cyno",
    "cynomolgus": "cyno",
    "cynomolgus monkey": "cyno",
}


def _norm_species(s: str | None) -> str:
    v = (s or "").strip().lower()
    return _SPECIES_ALIASES.get(v, v)


def _infer_species_from_cell_line(cell_line: str | None) -> str | None:
    if not cell_line:
        return None
    for pat, species in _CELL_LINE_SPECIES:
        if pat.search(cell_line):
            return species
    return None


def rollup_species_scope(observations: list[Any]) -> str:
    """Deterministically derive the record ``species_scope`` from the
    per-observation ``species`` values.

    The dominant named species wins; ``mixed`` when a second species reaches
    >=1/3 of named observations; ``unspecified`` only when no observation names
    a species.
    """
    named = [
        n
        for n in (_norm_species(getattr(o, "species", None)) for o in observations)
        if n and n != "unspecified"
    ]
    if not named:
        return "unspecified"
    counts = Counter(named)
    total = len(named)
    dominant = counts.most_common(1)[0][0]
    minor = [sp for sp, n in counts.items() if sp != dominant and n / total >= 1 / 3]
    return "mixed" if minor else dominant


def _scrub_unknown_cites(out: LiteratureLLMOut, *, known: set[str]) -> LiteratureLLMOut:
    def keep(ids: list[str]) -> list[str]:
        return [i for i in ids if i in known]

    gbm = out.grades_by_mode
    new_gbm = gbm.model_copy(
        update={
            "basal": gbm.basal.model_copy(
                update={"cited_source_ids": keep(gbm.basal.cited_source_ids)}
            ),
            "native_ligand": gbm.native_ligand.model_copy(
                update={"cited_source_ids": keep(gbm.native_ligand.cited_source_ids)}
            ),
            "therapeutic": gbm.therapeutic.model_copy(
                update={"cited_source_ids": keep(gbm.therapeutic.cited_source_ids)}
            ),
            "pathogen_entry": gbm.pathogen_entry.model_copy(
                update={"cited_source_ids": keep(gbm.pathogen_entry.cited_source_ids)}
            ),
        }
    )
    new_obs = [
        o.model_copy(update={"cited_source_ids": keep(o.cited_source_ids)})
        for o in out.observations
    ]
    new_mods = [
        m.model_copy(update={"cited_source_ids": keep(m.cited_source_ids)})
        for m in out.modulator_observations
    ]
    return out.model_copy(
        update={
            "grades_by_mode": new_gbm,
            "observations": new_obs,
            "modulator_observations": new_mods,
        }
    )


_PCT_PER_MIN_UNIT_RE = re.compile(r"^(?:%|percent)\s*(?:/|per\s+)min(?:ute)?s?$", re.IGNORECASE)
_PCT_PER_HR_UNIT_RE = re.compile(r"^(?:%|percent)\s*(?:/|per\s+)(?:h|hr|hour)s?$", re.IGNORECASE)
_PER_MIN_UNIT_RE = re.compile(r"^(?:min\s*[\-−]\s*1|/\s*min(?:ute)?|per\s+min(?:ute)?)$", re.IGNORECASE)
_PER_HR_UNIT_RE = re.compile(r"^(?:h\s*[\-−]\s*1|hr\s*[\-−]\s*1|/\s*(?:h|hr|hour)|per\s+(?:h|hr|hour))$", re.IGNORECASE)
_SEC_UNIT_RE = re.compile(r"^(?:s|sec|secs|second|seconds)$", re.IGNORECASE)
_MIN_UNIT_RE = re.compile(r"^(?:min|mins|minute|minutes)$", re.IGNORECASE)
_HR_UNIT_RE = re.compile(r"^(?:h|hr|hrs|hour|hours)$", re.IGNORECASE)
_DAY_UNIT_RE = re.compile(r"^(?:d|day|days)$", re.IGNORECASE)

_GRADE_SCHEMA_JSON: str = json.dumps(LiteratureLLMOut.model_json_schema(), indent=2)

# Single clean duration in time_point (e.g. "15 min", "~1 h", "2.5 h", "90 min").
# Deliberately rejects ranges ("1-4 h", "0.25–4 h"), multi-clause strings, or
# non-duration labels ("37 C") so apparent_t_half_min is never guessed from noise.
_SINGLE_TIME_POINT_RE = re.compile(
    r"^\s*(?:~|≈|about\s+|approx\.?\s*)?(\d+(?:\.\d+)?)\s*"
    r"(s|sec|secs|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours)\s*$",
    re.IGNORECASE,
)


def _parse_single_time_point_min(time_point: str | None) -> float | None:
    if not time_point:
        return None
    m = _SINGLE_TIME_POINT_RE.match(time_point)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    if num <= 0:
        return None
    if unit.startswith("s"):
        return num / 60.0
    if unit.startswith("m"):
        return num
    if unit.startswith("h"):
        return num * 60.0
    return None


def derive_universal_kinetics(
    quant: InternalizationQuant,
    *,
    rate_class: str,
    cell_context: str = "unknown",
) -> InternalizationQuant:
    """Deterministically normalize ``rate_metric`` from verbatim units and derive:

    1. **Exact cellular first-order kinetics** (``derived_t_half_min`` in min,
       ``derived_ke_min_inv`` in min^-1, ``derived_kinetics_basis``) ONLY for
       directly reported first-order rates/half-lives:
       - ``half_life`` (s / min / h; excludes multi-day ``in_vivo`` PK fits)
       - ``rate_per_min`` (min^-1) and ``ke_h_inv`` (h^-1)
       - ``percent_per_min`` (%/min -> k_e = val / 100 min^-1) and
         ``percent_per_hour`` (%/h -> k_e = val / 6000 min^-1), using the
         instantaneous fractional rate constant (valid for any val > 0,
         including >= 100 %/h such as rapid endocytosis).
    2. **Strictly separated single-endpoint apparent half-life**
       (``apparent_t_half_min``) via ``t * ln(2) / (-ln(1 - f))`` ONLY when
       ``rate_metric == "percent_internalized"``, ``5 <= val <= 95``, and
       ``time_point`` is a single clean duration ``<= 240 min`` (4 h).

    Always overwrites any LLM-supplied derived fields so all conversions are
    100% deterministic and auditable.
    """
    val = quant.rate_value
    unit = (quant.rate_unit or "").strip()
    metric = quant.rate_metric

    # Normalize verbatim rate units into explicit structured RateMetric values
    if val is not None and unit:
        if _PCT_PER_MIN_UNIT_RE.match(unit):
            metric = "percent_per_min"
        elif _PCT_PER_HR_UNIT_RE.match(unit):
            metric = "percent_per_hour"
        elif _PER_MIN_UNIT_RE.match(unit) and metric in ("other", "ke_h_inv", None):
            metric = "rate_per_min"
        elif _PER_HR_UNIT_RE.match(unit) and metric in ("other", None):
            metric = "ke_h_inv"

    t_half_min: float | None = None
    ke_min_inv: float | None = None
    basis: Literal["direct_half_life", "direct_rate_constant", "percent_rate", "none"] = "none"
    apparent_t_half_min: float | None = None

    # Exclude whole-body in_vivo PK/TMDD net_accumulation fits (e.g. 5-day
    # antibody clearance) from cellular entry rate constants.
    is_invivo_pk = cell_context == "in_vivo" and (
        rate_class == "net_accumulation" or _DAY_UNIT_RE.match(unit)
    )

    if (
        val is not None
        and val > 0
        and not is_invivo_pk
        and rate_class not in ("endpoint_fraction", "relative", "qualitative_only")
    ):
        if metric == "half_life":
            if _MIN_UNIT_RE.match(unit):
                t_half_min = val
            elif _HR_UNIT_RE.match(unit):
                t_half_min = val * 60.0
            elif _SEC_UNIT_RE.match(unit):
                t_half_min = val / 60.0
            elif _DAY_UNIT_RE.match(unit):
                t_half_min = val * 1440.0
            if t_half_min is not None and t_half_min > 0:
                ke_min_inv = math.log(2.0) / t_half_min
                basis = "direct_half_life"
        elif metric == "rate_per_min":
            ke_min_inv = val
            t_half_min = math.log(2.0) / ke_min_inv
            basis = "direct_rate_constant"
        elif metric == "ke_h_inv":
            # Guard: only treat as h^-1 if unit isn't per-minute
            if not _PER_MIN_UNIT_RE.match(unit):
                ke_min_inv = val / 60.0
                t_half_min = math.log(2.0) / ke_min_inv
                basis = "direct_rate_constant"
        elif metric == "percent_per_min":
            # Continuous fractional rate constant: X %/min => k_e = (X/100) min^-1
            ke_min_inv = val / 100.0
            t_half_min = math.log(2.0) / ke_min_inv
            basis = "percent_rate"
        elif metric == "percent_per_hour":
            # Continuous fractional rate constant: X %/h => k_e = (X/100) h^-1 = (X/6000) min^-1
            ke_min_inv = val / 6000.0
            t_half_min = math.log(2.0) / ke_min_inv
            basis = "percent_rate"

    # Strictly separated single-endpoint apparent half-life for clean
    # percent_internalized rows (5-95% at a single time_point <= 4 h).
    if (
        t_half_min is None
        and val is not None
        and metric == "percent_internalized"
        and 5.0 <= val <= 95.0
    ):
        tp_min = _parse_single_time_point_min(quant.time_point)
        if tp_min is not None and 0.0 < tp_min <= 240.0:
            denom = -math.log(1.0 - val / 100.0)
            if denom > 0:
                apparent_t_half_min = tp_min * math.log(2.0) / denom

    return quant.model_copy(
        update={
            "rate_metric": metric,
            "derived_t_half_min": round(t_half_min, 2) if t_half_min is not None else None,
            "derived_ke_min_inv": round(ke_min_inv, 5) if ke_min_inv is not None else None,
            "derived_kinetics_basis": basis if t_half_min is not None else None,
            "apparent_t_half_min": (
                round(apparent_t_half_min, 2) if apparent_t_half_min is not None else None
            ),
        }
    )


def _sanitize_observation(obs: InternalizationObservation) -> InternalizationObservation:
    updates: dict[str, Any] = {}

    # 1. Infer species from unambiguous canonical cell line when left blank.
    if not obs.species or obs.species.strip().lower() == "unspecified":
        inferred = _infer_species_from_cell_line(obs.cell_line)
        if inferred:
            updates["species"] = inferred

    # 2. Correct ADC / therapeutic-antibody observations misfiled into basal.
    if check_observation_mode_issue(obs) is not None:
        updates["internalization_mode"] = "therapeutic"

    # 3. Scrub bogus rate_value entries (bare time points or non-uptake units),
    # otherwise compute deterministic universal kinetics (derived_t_half_min / derived_ke_min_inv).
    q = obs.quant
    eff_rate_class = obs.rate_class
    if q.rate_value is not None and check_observation_quant_issue(obs) is not None:
        new_tp = q.time_point
        if (
            not new_tp
            and q.rate_metric == "other"
            and q.rate_unit
            and _BARE_TIME_UNIT_RE.match(q.rate_unit.strip())
        ):
            val_str = str(int(q.rate_value)) if float(q.rate_value).is_integer() else str(q.rate_value)
            new_tp = f"{val_str} {q.rate_unit.strip()}"
        updates["quant"] = InternalizationQuant(
            rate_metric=None,
            rate_value=None,
            rate_unit=None,
            time_point=new_tp,
            quant_summary=q.quant_summary,
            derived_t_half_min=None,
            derived_ke_min_inv=None,
            derived_kinetics_basis=None,
            apparent_t_half_min=None,
        )
        updates["rate_class"] = "qualitative_only"
    else:
        if q.rate_value is None and eff_rate_class == "unknown" and q.quant_summary:
            eff_rate_class = "qualitative_only"
            updates["rate_class"] = eff_rate_class
        derived_q = derive_universal_kinetics(
            q, rate_class=eff_rate_class, cell_context=obs.cell_context
        )
        if derived_q != q:
            updates["quant"] = derived_q

    return obs.model_copy(update=updates) if updates else obs


def _sanitize_grade_output(out: LiteratureLLMOut) -> LiteratureLLMOut:
    """Deterministic guardrails for observation hygiene and overall-grade consistency."""
    moved_from_basal_cites: set[str] = set()
    cleaned_obs: list[InternalizationObservation] = []
    for o in out.observations:
        was_basal = o.internalization_mode == "basal"
        sanitized = _sanitize_observation(o)
        if was_basal and sanitized.internalization_mode != "basal":
            moved_from_basal_cites.update(sanitized.cited_source_ids)
        cleaned_obs.append(sanitized)

    gbm = out.grades_by_mode
    # If ADC/therapeutic-antibody observations were reclassified out of basal
    # and no genuine basal observations remain, reset basal to unknown rather
    # than leaving a stale basal grade anchored on a therapeutic binder.
    if moved_from_basal_cites:
        remaining_basal = [o for o in cleaned_obs if o.internalization_mode == "basal"]
        if not remaining_basal and gbm.basal.grade != "unknown":
            gbm = gbm.model_copy(
                update={
                    "basal": gbm.basal.model_copy(
                        update={
                            "grade": "unknown",
                            "confidence": "low",
                            "cited_source_ids": [
                                cid for cid in gbm.basal.cited_source_ids if cid not in moved_from_basal_cites
                            ],
                        }
                    )
                }
            )

    # Enforce overall_grade consistency against the three delivery-relevant modes
    # (basal, native_ligand, therapeutic — never pathogen_entry).
    delivery_grades: list[Grade] = [
        gbm.basal.grade,
        gbm.native_ligand.grade,
        gbm.therapeutic.grade,
    ]
    non_unknown = [g for g in delivery_grades if g != "unknown"]
    overall_grade = out.overall_grade
    if not non_unknown:
        overall_grade = "unknown"
    elif overall_grade == "unknown":
        overall_grade = max(non_unknown, key=lambda g: _GRADE_RANK[g])

    return out.model_copy(
        update={
            "grades_by_mode": gbm,
            "observations": cleaned_obs,
            "overall_grade": overall_grade,
        }
    )


def grade_from_evidence(
    client: Any,
    *,
    gene: str,
    evidence: list[Any],
    synonyms: list[str] | None = None,
    system_prompt: str | None = None,
    usage_sink: list[Any] | None = None,
    model: str = SONNET_MODEL,
) -> LiteratureLLMOut:
    if not evidence:
        return LiteratureLLMOut()  # nothing to grade → all modes 'unknown'
    base_sys = system_prompt or load_grade_prompt()
    # Hoist the static JSON schema into the cached system prompt so Anthropic's
    # ephemeral prompt cache absorbs ~2.5k static tokens on every gene.
    full_system = (
        f"{base_sys}\n\n# LiteratureLLMOut JSON Schema\n\n```json\n{_GRADE_SCHEMA_JSON}\n```"
    )
    aka = f"Also known as: {', '.join(synonyms)}\n" if synonyms else ""
    user = (
        f"Gene: {gene}\n{aka}\nSpan-verified evidence ledger (cite ONLY these "
        f"evidence_ids):\n\n{_render_evidence(evidence)}\n\n"
        "Emit one ```json block matching the LiteratureLLMOut schema in the system prompt."
    )
    out = call_model_structured(
        client,
        model=model,
        system_prompt=full_system,
        user_prompt=user,
        schema=LiteratureLLMOut,
        max_tokens=_MAX_TOKENS_GRADE,
        usage_sink=usage_sink,
    )
    scrubbed = _scrub_unknown_cites(out, known={e.evidence_id for e in evidence})
    return _sanitize_grade_output(scrubbed)
