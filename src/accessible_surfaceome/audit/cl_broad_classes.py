"""Broad-class rollup for Cell Ontology (CL) terms.

CZI's WMG data uses ~600 leaf CL terms. HPA-style 4× enrichment
classification (designed for ~40 broad tissues) fails on this many
fine-grained entities — many sibling CL terms express at similar
levels (naive B vs memory B vs plasma cell all expressing CD19),
which prevents any single CL term from being 4× higher than the next.

This module maps every leaf CL label to one of ~10 broad cell classes
via priority-ordered keyword rules. The classification axis then
operates on ~10 entities — close to HPA's original tissue-axis design
— so well-known markers (CD19 → Immune, KLK2 → Epithelial, MYH7 →
Muscle) classify correctly.

Categories mirror the deleted `viewer/lib/cellxgene-categories.ts`
(removed in 1f2cb4d41 when the cell-class chart-coloring was dropped).
The TS file's per-bar coloring use case is gone; the classification
use case is back.

This is a HEURISTIC rollup — keyword rules on the human-readable CL
label, not graph-walked ancestry from CL.obo. Trade-off: keyword
rules are zero-dep (just the CL label TSV) and run in microseconds;
ancestry walks would need cl.obo + a parser. The rules are tuned to
match the CZI/Tabula Sapiens "compartment" convention so a reader
familiar with those datasets sees the same buckets.
"""

from __future__ import annotations

from typing import Final

BROAD_CLASSES: Final[tuple[str, ...]] = (
    "Epithelial",
    "Immune",
    "Endothelial",
    "Stromal",
    "Neural",
    "Muscle",
    "Reproductive",
    "Stem",
    "Tumor",
    "Other",
)


# Priority-ordered rules — FIRST match wins. Ordering encodes
# disambiguation: "alveolar macrophage" hits Immune via "macrophage"
# before Epithelial via "alveolar"; "skeletal muscle fibroblast" hits
# Stromal via "fibroblast" before Muscle via "muscle".
#
# **Bare-word rules need leading spaces** to avoid substring
# false-positives — "t cell" without a leading space matches
# "trophoblast cell", "malignant cell", "syncytiotrophoblast cell".
# Use " t cell" so the rule only fires when "t" stands alone.
_RULES: Final[tuple[tuple[str, str], ...]] = (
    # --- Tumor (before Immune so "malignant cell" doesn't fall through " t cell") ---
    ("malignant", "Tumor"),
    ("tumor", "Tumor"),
    ("neoplastic", "Tumor"),
    ("cancer", "Tumor"),
    # --- Reproductive (before Immune so trophoblast/syncytiotrophoblast
    #     don't fall through " t cell" via the "t cell" substring) ---
    ("spermatocyte", "Reproductive"),
    ("spermatid", "Reproductive"),
    ("spermatogonia", "Reproductive"),
    ("trophoblast", "Reproductive"),
    ("syncytiotrophoblast", "Reproductive"),
    ("decidual", "Reproductive"),
    ("germ cell", "Reproductive"),
    ("sertoli", "Reproductive"),
    ("leydig", "Reproductive"),
    ("granulosa", "Reproductive"),
    ("theca", "Reproductive"),
    ("oocyte", "Reproductive"),
    ("sperm cell", "Reproductive"),
    # --- Immune (early so e.g. "alveolar macrophage" doesn't fall to Epithelial) ---
    ("macrophage", "Immune"),
    ("monocyte", "Immune"),
    ("dendritic", "Immune"),
    ("neutrophil", "Immune"),
    ("eosinophil", "Immune"),
    ("basophil", "Immune"),
    ("mast cell", "Immune"),
    ("microglial", "Immune"),
    ("microglia", "Immune"),
    ("kupffer", "Immune"),
    ("langerhans", "Immune"),
    ("natural killer", "Immune"),
    ("nk cell", "Immune"),
    ("nk t", "Immune"),
    (" t cell", "Immune"),
    ("t-helper", "Immune"),
    ("t-regulatory", "Immune"),
    ("treg", "Immune"),
    ("regulatory t", "Immune"),
    ("alpha-beta t", "Immune"),
    ("gamma-delta t", "Immune"),
    ("cd4-positive", "Immune"),
    ("cd8-positive", "Immune"),
    ("cd14-positive", "Immune"),
    ("cd16-", "Immune"),
    ("thymocyte", "Immune"),
    (" b cell", "Immune"),
    ("pre-b", "Immune"),
    ("plasma cell", "Immune"),
    ("plasmablast", "Immune"),
    ("plasmacytoid", "Immune"),
    ("memory b", "Immune"),
    ("naive b", "Immune"),
    ("erythroblast", "Immune"),
    ("erythrocyte", "Immune"),
    ("hematopoietic", "Immune"),
    ("megakaryocyte", "Immune"),
    ("platelet", "Immune"),
    ("lymphocyte", "Immune"),
    ("leukocyte", "Immune"),
    ("innate lymphoid", "Immune"),
    ("myeloid", "Immune"),
    ("granulocyte", "Immune"),
    ("immune", "Immune"),
    ("blood cell", "Immune"),
    ("mononuclear phagocyte", "Immune"),
    # --- Neural (also early so "neural progenitor" → Neural, not Stem) ---
    ("neuron", "Neural"),
    ("neural", "Neural"),
    ("glial", "Neural"),
    ("oligodendrocyte", "Neural"),
    ("astrocyte", "Neural"),
    ("schwann", "Neural"),
    ("ependymal", "Neural"),
    ("photoreceptor", "Neural"),
    ("retinal", "Neural"),
    ("bipolar cell", "Neural"),
    ("ganglion cell", "Neural"),
    ("amacrine", "Neural"),
    ("interneuron", "Neural"),
    ("purkinje", "Neural"),
    ("granule cell", "Neural"),
    ("cerebellar", "Neural"),
    ("pyramidal", "Neural"),
    ("gabaergic", "Neural"),
    ("glutamatergic", "Neural"),
    ("dopaminergic", "Neural"),
    ("serotonergic", "Neural"),
    ("cholinergic", "Neural"),
    ("glycinergic", "Neural"),
    ("muller", "Neural"),
    ("mueller", "Neural"),
    ("horizontal cell", "Neural"),
    ("brainstem", "Neural"),
    ("brain", "Neural"),
    ("cortex", "Neural"),
    ("cortical interneuron", "Neural"),
    ("cortical neuron", "Neural"),
    ("forebrain", "Neural"),
    ("midbrain", "Neural"),
    ("hindbrain", "Neural"),
    ("spinal cord", "Neural"),
    ("sensory neuron", "Neural"),
    ("motor neuron", "Neural"),
    ("sympathetic neuron", "Neural"),
    ("choroid plexus", "Neural"),
    ("ionocyte", "Neural"),
    # --- Endothelial ---
    ("endothelial", "Endothelial"),
    ("pericyte", "Endothelial"),
    ("mural cell", "Endothelial"),
    ("blood vessel", "Endothelial"),
    ("vasculature", "Endothelial"),
    ("perivascular", "Endothelial"),
    # --- Muscle (smooth muscle / skeletal / cardiac) ---
    ("smooth muscle", "Muscle"),
    ("cardiac muscle", "Muscle"),
    ("skeletal muscle satellite", "Stem"),  # special-case: a stem cell
    ("skeletal muscle fibroblast", "Stromal"),
    ("skeletal muscle", "Muscle"),
    ("muscle cell", "Muscle"),
    ("muscle fiber", "Muscle"),
    ("myocyte", "Muscle"),
    ("myoblast", "Muscle"),
    ("cardiomyocyte", "Muscle"),
    ("myofibroblast", "Stromal"),
    ("myocardial", "Muscle"),
    # --- Stromal / connective ---
    ("fibroblast", "Stromal"),
    ("stellate cell", "Stromal"),
    ("mesenchymal stem", "Stem"),
    ("mesenchymal", "Stromal"),
    ("adipocyte", "Stromal"),
    ("preadipocyte", "Stromal"),
    ("chondrocyte", "Stromal"),
    ("osteoblast", "Stromal"),
    ("osteoclast", "Stromal"),
    ("osteocyte", "Stromal"),
    ("connective tissue", "Stromal"),
    ("mesothelial", "Stromal"),
    ("stromal", "Stromal"),
    ("dermis", "Stromal"),
    ("dermal", "Stromal"),
    ("keratocyte", "Stromal"),
    ("tendon", "Stromal"),
    ("ligament", "Stromal"),
    ("trabecular meshwork", "Stromal"),
    # --- Stem / progenitor (Reproductive + Tumor moved above Immune) ---
    ("stem cell", "Stem"),
    ("progenitor cell", "Stem"),
    ("transit amplifying", "Stem"),
    ("precursor cell", "Stem"),
    ("oligodendrocyte precursor", "Neural"),  # specialized
    # --- Epithelial (broad — last among non-other so specific rules above win) ---
    ("epithelial", "Epithelial"),
    ("epithelium", "Epithelial"),
    ("luminal", "Epithelial"),
    ("basal cell", "Epithelial"),
    ("ciliated", "Epithelial"),
    ("secretory cell", "Epithelial"),
    ("goblet", "Epithelial"),
    ("club cell", "Epithelial"),
    ("alveolar", "Epithelial"),
    ("hepatocyte", "Epithelial"),
    ("hepatoblast", "Epithelial"),
    ("enterocyte", "Epithelial"),
    ("colonocyte", "Epithelial"),
    ("acinar", "Epithelial"),
    ("ductal", "Epithelial"),
    ("ionocyte", "Epithelial"),
    ("enteroendocrine", "Epithelial"),
    ("endocrine cell", "Epithelial"),
    ("chromaffin", "Epithelial"),
    ("follicular cell", "Epithelial"),
    ("melanocyte", "Epithelial"),
    ("kidney loop of henle", "Epithelial"),
    ("kidney distal", "Epithelial"),
    ("kidney proximal", "Epithelial"),
    ("kidney collecting", "Epithelial"),
    ("kidney connecting", "Epithelial"),
    ("renal", "Epithelial"),
    ("parietal epithelial", "Epithelial"),
    ("mesangial", "Stromal"),  # mesangial cells are mesenchymal/stromal
    ("mucus secreting", "Epithelial"),
    ("mucous cell", "Epithelial"),
    ("foveolar", "Epithelial"),
    ("squamous epithelial", "Epithelial"),
    ("corneal", "Epithelial"),
    ("salivary", "Epithelial"),
    ("mammary gland", "Epithelial"),
    ("respiratory", "Epithelial"),
    ("nasal mucosa", "Epithelial"),
    ("tracheo", "Epithelial"),
    ("bronchus", "Epithelial"),
    ("bronchial", "Epithelial"),
    ("ciliary muscle", "Muscle"),  # special-case in eye
    ("ciliary", "Epithelial"),
    ("prostate epithelium", "Epithelial"),
    ("prostate stromal", "Stromal"),
    ("prostate", "Epithelial"),
    ("epicardial adipocyte", "Stromal"),
    ("taste receptor", "Epithelial"),
)


def cl_broad_class(label: str) -> str:
    """Return the broad cell class for a CL label. Defaults to ``Other``
    if no rule matches. Match is case-insensitive substring on the
    lower-cased label."""
    if not label:
        return "Other"
    s = label.lower()
    for needle, klass in _RULES:
        if needle in s:
            return klass
    return "Other"
