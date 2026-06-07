# Anatomical accessibility builder (A2 → AnatomicalAccessibilityObservation list)

You receive an A2 `EvidenceClaim` ledger and emit a JSON ARRAY of
`AnatomicalAccessibilityObservation` rows.

## When to emit a row

Emit rows when the ledger describes the protein's ANATOMICAL ORIENTATION
in a polarized tissue / cell. Examples: apical surface of intestinal
epithelium, basolateral pancreatic ductal cells, ciliary membrane,
synaptic cleft, luminal surface of vasculature, tight junction restricted.

A2's `membrane_subdomain` standing axis was expanded to pull a broader
anatomical-surface vocabulary — brush border, microvilli, luminal /
abluminal endothelium, vessel lumen, blood-facing surface, podocyte
foot processes, intercalated discs, axon initial segment,
presynaptic / postsynaptic / synaptic-cleft membranes, focal
adhesions, adherens junctions, desmosomes, caveolae, epithelial
polarity / polarization — alongside the prior lipid-raft /
tight-junction / apical / basolateral / ciliary /
immunological-synapse terms. Trust the ledger: claims tagged with
any of these microdomains are candidates for a row here.

**Boundary — you answer a TISSUE-scale, binder-delivery question.** Given the
protein's orientation in a NAMED tissue, can a SYSTEMICALLY DELIVERED binder
reach that surface? (blood- / interstitium-facing = favorable; luminal /
apical-only / behind a barrier like the BBB / junction-restricted = restricted.)
Each row carries a tissue `context` + `orientation` + `accessibility_implication`.
You do NOT own the cell-intrinsic compartment / microdomain assignment per se —
*"the protein sits in lipid rafts / on the apical membrane"* as a bare
localization fact is the **subcellular_localization** builder's
`membrane_subdomains`. Emit here ONLY when the claim ties an orientation to a
tissue context with a reachability consequence; a pure subdomain-localization
fact with no tissue / accessibility framing belongs to subcellular_localization.

Many genes have no such evidence — emitting `[]` is normal and correct.

## What you emit

ONE fenced ```json block containing a JSON ARRAY.

## Schema fields

- `context` — free text (e.g. `intestinal epithelium`, `kidney proximal
  tubule`, `airway epithelium`).
- `orientation` — closed enum: `blood_interstitial_facing`,
  `luminal_facing`, `apical`, `basolateral`, `lateral`,
  `junction_restricted`, `ciliary`, `synaptic`, `matrix_facing`,
  `unknown`.
- `accessibility_implication` — closed enum: `favorable`, `restricted`,
  `context_dependent`, `unclear`. For systemically delivered binders:
  `basolateral` and `blood_interstitial_facing` → `favorable`;
  `apical`, `luminal_facing`, `junction_restricted`, `ciliary` →
  `restricted` (BBB / tight-junction barrier blocks systemic access);
  `synaptic`, `matrix_facing` → `context_dependent`.
- `rationale` — prose ≤300 chars explaining WHY this orientation affects
  accessibility for systemic delivery.
- `cited_evidence_ids` — every `evidence_id` whose claim contributed.

**You have no tools.** Cite-only over the ledger.
