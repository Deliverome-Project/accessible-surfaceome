# Subcellular localization builder (A2 → SubcellularLocalization)

You receive an A2 `EvidenceClaim` ledger and emit EXACTLY ONE
`SubcellularLocalization` object.

## What you emit

ONE fenced ```json block containing a JSON OBJECT (NOT an array).

## Source claims

Claims with `claim_type=surface_expression` that describe the protein's
compartment / subdomain (plasma membrane, cilium, endosome, lipid raft,
tight junction, lateral membrane, etc.). HPA `db_annotation` claims
listing subcellular locations are also primary input.

## Schema fields

- `primary_compartment` — closed enum: `plasma_membrane`, `endosome`,
  `lysosome`, `ER`, `Golgi`, `mitochondrion`, `nucleus`, `cytosol`,
  `secreted`, `other`. Default to `plasma_membrane` for surfaceome
  candidates UNLESS the ledger strongly indicates the dominant pool is
  elsewhere.
- `dual_localization` — JSON ARRAY of `DualLocalization` rows, ONE per
  non-primary **whole compartment** the protein is reported in. Each row:
    - `compartment` — a SHORT canonical compartment NAME, not a sentence.
      Use the plain organelle / compartment term: `endosome`, `lysosome`,
      `Golgi`, `ER`, `mitochondrion`, `nucleus`, `cytosol`, `secreted`,
      `extracellular matrix`, `extracellular vesicle`. Do NOT pack the
      condition, the membrane leaflet, or a clause into this field — e.g.
      write `compartment="endosome"` with `condition="EGF-induced
      internalization"`, NOT `compartment="endosome (upon EGF ligand
      stimulation)"`. Do NOT use this field for plasma-membrane *subdomains*
      or *leaflets* (apical, basolateral, inner leaflet, lipid raft) — those
      go in `membrane_subdomains` below.
    - `fraction_estimate` — float between 0 and 1, OR null when no
      quantitative estimate exists.
    - `condition` — the qualifier that the localization in this compartment
      depends on (e.g. `EGF-induced internalization`, `in polarized cells`,
      `cancer cells`) or null. This is where the "when / where" clause goes.
    - `cited_evidence_ids` — list.
- `membrane_subdomains` — JSON ARRAY of `MembraneSubdomain` rows for
  **plasma-membrane surface microdomains** the protein localizes to — the
  region of the OUTER, extracellular-facing membrane an antibody would
  encounter. Each row:
    - `subdomain` — a SHORT canonical subdomain NAME: `apical membrane`,
      `basolateral membrane`, `lateral membrane`, `tight junction`,
      `lipid raft`, `primary cilium`, `microvilli`, `synapse`,
      `leading edge`, `filopodia`. Keep it terse — no parenthetical
      mechanism.
    - `cited_evidence_ids` — list.
  ONLY for outer-leaflet / surface microdomains. Do NOT put whole
  compartments (endosome, lysosome, Golgi) here — those are
  `dual_localization`. Do NOT put the **inner leaflet / cytoplasmic face**
  of the plasma membrane here (e.g. myristoylated/palmitoylated SRC, LYN):
  that is NOT surface-accessible, so it belongs in `dual_localization` with
  a compartment like `inner leaflet of plasma membrane` instead — never as
  a surface subdomain.

## Empty cases

If the ledger has no compartment claims at all, emit
`primary_compartment="other"`, empty `dual_localization`, empty
`membrane_subdomains`.

**You have no tools.** Cite-only over the ledger. Every `cited_evidence_ids` value must appear
in the input ledger as an `evidence_id`.
