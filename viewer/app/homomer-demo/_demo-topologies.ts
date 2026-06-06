/*
 * Hand-baked per-residue DeepTMHMM-style topology strings for the
 * three homomer-demo pages (/homomer-demo/{BSCL2,GJA1,AQP1}).
 *
 * Why hand-baked: the demo pages render WITHOUT a full on-disk
 * SurfaceomeRecord — they're meant to demonstrate the homo-oligomer
 * coloring without standing up a deep-dive record for every showcase
 * gene. The DeepTMHMM cohort doesn't ship per-residue strings for
 * proteins outside the deep-dive set in this branch, so we synthesize
 * an equivalent from each gene's UniProt features:
 *
 *   ``Transmembrane`` features → ``M``
 *   ``Signal`` features        → ``S``
 *   Cytoplasmic gaps           → ``I``
 *   Extracellular / lumenal    → ``O``
 *
 * The starting orientation (I or O at residue 1) comes from the
 * N-terminus topological-domain annotation when UniProt supplies one,
 * otherwise from the convention "TM proteins have a cytoplasmic
 * N-term" (true for BSCL2 / GJA1 / AQP1).
 *
 * Generated 2026-06-06 by ``scripts/synthesize_demo_topology.py``
 * against UniProt release 2026_02. Re-run when bumping UniProt or
 * when adding a new demo gene.
 */

export const DEMO_TOPOLOGIES: Record<
  string,
  { topology: string; deeptmhmm_type: "TM" | "SP+TM" | "SP" | "BETA" | "GLOB" }
> = {
  // BSCL2 / seipin — ER membrane protein, 2 TMs, both termini cyto.
  // Schweke's c13 ring is the seipin oligomer at the ER membrane.
  BSCL2: {
    deeptmhmm_type: "TM",
    topology:
      "IIIIIIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
  },
  // GJA1 / connexin-43 — 4 TMs, both termini cyto. Schweke's c7
  // hemichannel is the connexon (the half-channel docking unit of a
  // gap junction). Six connexons make a connexon hexamer in vivo;
  // Schweke's AnAnaS reconstruction picked c7 for this particular
  // dimer interface scoring — see CALHM5 (c12) and BSCL2 (c13) for
  // higher-order cases.
  GJA1: {
    deeptmhmm_type: "TM",
    topology:
      "OIIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIMMMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
  },
  // AQP1 / aquaporin-1 — water channel, 6 TMs in a hourglass fold,
  // both termini cyto. Schweke's dimer is the AQP1 tetramer's
  // assembly-unit dimer.
  AQP1: {
    deeptmhmm_type: "TM",
    topology:
      "OIIIIIIIIIIMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMIIIOOOOOOOOOOOOOOIIIIIIIIMMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMMMIIIIIIIIIIMMMMMMMMMMMMMMMMMMOOOOOOOOOOOOOOOOOOOOOOOOOMMMMMMMMMMMMMMMMMMIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII",
  },
};
