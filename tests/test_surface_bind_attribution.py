"""Regression: the SURFACE-Bind citation must credit the correct first
author.

The SURFACE-Bind paper is Balbi PEM et al., "Mapping targetable sites on
the human surfaceome for the design of novel binders," PNAS 2026 —
**PMID 41604262 == DOI 10.1073/pnas.2506269123** (verified one paper).
An earlier draft mislabeled the lead author as "Marchand" (the 3rd
author) in the record-facing ``SurfaceBindFeatures`` defaults, which then
travelled into every per-gene record's ``deterministic_features.
surface_bind.source`` / ``.attribution`` (the ``lookup`` builder never
overrides these, so the model defaults are authoritative).

These assertions pin the correction so the mislabel can't silently come
back.
"""
from __future__ import annotations

from accessible_surfaceome.tools._shared.models import SurfaceBindFeatures


def test_surface_bind_default_attribution_credits_balbi() -> None:
    sb = SurfaceBindFeatures()

    # DOI is the durable identifier and was always correct — keep it.
    assert sb.citation == "10.1073/pnas.2506269123"

    # First author (Balbi PEM) must lead both record-facing strings.
    assert "Balbi" in sb.source
    assert "Balbi" in sb.attribution

    # Guard the specific old mislabels: source led "(Marchand 2026 …)" and
    # attribution led "© Marchand, …". Marchand is a real co-author, so we
    # only forbid the *first-author* position.
    assert "Marchand 2026" not in sb.source
    assert not sb.attribution.lstrip("© ").startswith("Marchand")


def test_surface_bind_lookup_uses_model_default_attribution() -> None:
    """The ``lookup`` builder constructs ``SurfaceBindFeatures`` without
    passing source/attribution, so a "miss" carries the corrected default
    too — documents *why* fixing the model default is sufficient."""
    from accessible_surfaceome.tools.surface_bind import lookup

    miss = lookup("___not_a_real_accession___")
    assert miss.has_data is False
    assert "Balbi" in miss.source
    assert miss.citation == "10.1073/pnas.2506269123"
