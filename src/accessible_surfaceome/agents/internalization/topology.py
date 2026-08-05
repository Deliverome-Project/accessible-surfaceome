"""Render UniProt topology features into a compact prose summary for the
model-prior prompt. Topology features are annotated on the canonical isoform;
the summary is shared across isoforms and the prompt says so."""

from __future__ import annotations

from collections import Counter

from accessible_surfaceome.tools._shared.models import TopologyFeature


def summarize_topology(features: list[TopologyFeature]) -> str:
    if not features:
        return "No UniProt topology features annotated."

    counts: Counter[str] = Counter(f.feature_type for f in features)
    parts: list[str] = []

    if counts.get("signal_peptide"):
        parts.append(f"{counts['signal_peptide']} signal peptide")
    if counts.get("transmembrane"):
        parts.append(f"{counts['transmembrane']} transmembrane segment(s)")
    if counts.get("gpi_anchor"):
        parts.append("GPI-anchored")
    if counts.get("intramembrane"):
        parts.append(f"{counts['intramembrane']} intramembrane segment(s)")

    sides = {
        (f.description or "").strip().lower()
        for f in features
        if f.feature_type == "topological_domain"
    }
    if "extracellular" in sides:
        parts.append("extracellular domain(s) present")
    if "cytoplasmic" in sides:
        parts.append("cytoplasmic domain(s) present")

    if not parts:
        kinds = ", ".join(sorted(counts))
        return f"Topology features present ({kinds}) but no TM/sidedness resolved."
    return "; ".join(parts) + "."
