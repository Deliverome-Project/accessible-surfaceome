// Serve-time Schweke homomer, paralog/ortholog, SURFACE-Bind, and bindome enrichment.

export async function enrichSchwekeHomomer(env, record, soft) {
  // Enrich with Schweke 2024 homo-oligomer prediction at serve time.
  // The annotator already bakes ``deterministic_features.homo_oligomerization``
  // into newly-annotated records (consistent with how the other deterministic
  // blocks — topology, paralogs, orthologs, structure, surface_bind — are
  // populated at annotation time). This LEFT JOIN is the back-compat hatch
  // for records annotated BEFORE the schweke_homomer wiring landed: any
  // record whose homo_oligomerization block is missing OR carries
  // is_homo_oligomer=false despite the gene appearing in
  // schweke_homomer_public gets the row injected. Records that already
  // carry a positive Schweke entry from the annotator are left alone
  // (annotator's bake wins; ensures the data the LLM saw at annotation
  // time matches what the viewer renders).
  const uniprot = record?.gene?.uniprot_acc;
  if (uniprot) {
    const existing = record?.deterministic_features?.homo_oligomerization;
    const needsEnrichment = !existing || existing.is_homo_oligomer === false;
    if (needsEnrichment) {
      const schwekeRow = await soft(
        env.DB.prepare(
          `SELECT stoichiometry, af_model_num, is_ecd_only,
                  has_higher_order_complex, dimer_pdb_filename,
                  complex_pdb_filename
             FROM schweke_homomer_public
            WHERE uniprot_acc = ?
            ORDER BY universe_version DESC
            LIMIT 1`
        ).bind(uniprot).first(),
        "schweke_homomer_public",
      );
      if (schwekeRow) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.homo_oligomerization = {
          is_homo_oligomer: true,
          stoichiometry: schwekeRow.stoichiometry ?? null,
          af_model_num: schwekeRow.af_model_num ?? null,
          is_ecd_only: !!schwekeRow.is_ecd_only,
          has_higher_order_complex: !!schwekeRow.has_higher_order_complex,
          dimer_pdb_filename: schwekeRow.dimer_pdb_filename ?? null,
          complex_pdb_filename: schwekeRow.complex_pdb_filename ?? null,
          source: "Schweke 2024 (PMID 38325366)",
          citation: "10.1016/j.cell.2024.01.022",
        };
        // Cat 3 mitigation — also derive
        // ``accessibility_risks.homo_oligomerization_prediction`` from the
        // injected block. This field is normally populated at annotation
        // time by the orchestrator's ``_attach_homo_oligomerization_prediction``
        // post-pass (see ``agents/surfaceome_v2/orchestrator.py``); the
        // Worker mirrors the same derivation so old records served before
        // re-annotation also carry the structured risk chip the viewer
        // renders next to ``epitope_masking``. Severity bands MUST match
        // the Python implementation's ``_homo_oligomerization_severity``
        // helper — keep them in sync (≤2 → low, 3..7 → moderate, 8..24 →
        // high, None → unknown). Annotator-populated risk chips win: only
        // inject when the served record doesn't already carry one (mirrors
        // the same "annotator-bake wins" convention as every other
        // serve-time enrichment in handleGene).
        const existingRisk =
          record?.accessibility_risks?.homo_oligomerization_prediction;
        if (!existingRisk) {
          const n = schwekeRow.stoichiometry;
          let severity = "unknown";
          if (typeof n === "number") {
            if (n <= 2) severity = "low";
            else if (n <= 7) severity = "moderate";
            else if (n <= 24) severity = "high";
          }
          if (!record.accessibility_risks) record.accessibility_risks = {};
          record.accessibility_risks.homo_oligomerization_prediction = {
            present: true,
            stoichiometry: n ?? null,
            severity,
            is_ecd_only: !!schwekeRow.is_ecd_only,
            source: "Schweke 2024 (PMID 38325366)",
            cited_evidence_ids: [],
          };
        }
      }
    }
  }
}

export async function enrichParalogsAndOrthologs(env, record, uniprot, { canonicalTopoVersion, paralogVersion, orthologEcdVersion }, soft, dedupeByKey) {
    // ----- paralogs -----
    // Mirror _fetch_paralogs. Enrich when the field is missing OR (the
    // array is empty AND ``paralogs_checked`` is not True). Close paralogs
    // (>=80% full-length identity, the CLOSE_PARALOG_THRESHOLD constant in
    // d1_deterministic.py) get their DeepTMHMM topology + sequence threaded
    // on via LEFT JOIN against topology_public; far/ECD-less paralogs stay
    // chip-only. PARALOG_TOP_N is 50 in the Python annotator — same cap here.
    const existingParalogs = record?.deterministic_features?.paralogs;
    const paralogsChecked = record?.deterministic_features?.paralogs_checked === true;
    const paralogsNeedEnrich = !Array.isArray(existingParalogs)
      || (existingParalogs.length === 0 && !paralogsChecked);
    if (paralogsNeedEnrich && paralogVersion) {
      const paralogRows = await soft(
        env.DB.prepare(
          `SELECT cp.paralog_gene_symbol, cp.paralog_uniprot_acc, cp.ecd_pct_identity,
                  cp.ecd_pct_similarity, cp.biomart_percent_identity, cp.family_id,
                  cp.compara_version, cp.rank_by_ecd_identity,
                  tp.per_residue_topology, tp.deeptmhmm_label, tp.tm_helix_count,
                  tp.ecd_length_residues, tp.icd_length_residues,
                  tp.n_terminal_orientation, tp.c_terminal_orientation,
                  tp.signal_peptide_length, tp.sequence
             FROM compara_paralog cp
             LEFT JOIN topology_public tp
               ON tp.uniprot_acc = cp.paralog_uniprot_acc
              AND tp.cohort = 'human_canonical' AND tp.topology_version = ?
            WHERE cp.human_uniprot_acc = ? AND cp.paralog_version = ?
              AND cp.paralog_gene_symbol IS NOT NULL
              AND cp.paralog_uniprot_acc IS NOT NULL
            ORDER BY cp.rank_by_ecd_identity ASC NULLS LAST LIMIT 50`
        ).bind(canonicalTopoVersion ?? "", uniprot, paralogVersion).all(),
        "compara_paralog",
      );
      // Belt-and-suspenders dedup: the LEFT JOIN against topology_public
      // is keyed on (uniprot_acc, cohort, topology_version); a stale
      // topology_release would let multiple cohort/version rows survive
      // per paralog and double-count entries here.
      const presults = dedupeByKey(
        paralogRows?.results ?? [],
        (r) => r.paralog_uniprot_acc,
      );
      if (presults.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        const CLOSE_PARALOG_THRESHOLD = 80.0;
        record.deterministic_features.paralogs = presults.map((r) => {
          const fullId = r.biomart_percent_identity != null ? Number(r.biomart_percent_identity) : null;
          const ecdId = r.ecd_pct_identity != null ? Number(r.ecd_pct_identity) : null;
          const isClose = fullId !== null && fullId >= CLOSE_PARALOG_THRESHOLD;
          // Topology + sequence surfaced only for close paralogs (same gate
          // as the Python annotator). Far/ECD-less paralogs stay chip-only.
          let topo = null, tmc = null, ecdl = null, seq = null;
          if (isClose && r.per_residue_topology) {
            topo = r.per_residue_topology;
            seq = r.sequence ?? null;
            tmc = r.tm_helix_count != null ? Number(r.tm_helix_count) : null;
            ecdl = r.ecd_length_residues != null ? Number(r.ecd_length_residues) : null;
          }
          return {
            paralog_symbol: r.paralog_gene_symbol,
            paralog_uniprot_acc: r.paralog_uniprot_acc,
            ecd_pct_identity: ecdId,
            full_length_pct_identity: fullId,
            family_id: r.family_id || "",
            compara_version: r.compara_version || "",
            per_residue_topology: topo,
            tm_helix_count: tmc,
            ecd_length_residues: ecdl,
            sequence: seq,
          };
        });
      }
    }

    // ----- orthologs (mouse + cynomolgus) -----
    // Mirror _fetch_orthologs. Enrich when the field is missing OR (both
    // species lists are empty AND ``checked`` is not True). The Python
    // annotator projects the human canonical topology onto each ortholog
    // (via merge.ortholog_topology_projection) — that's a global alignment
    // not feasible in a Worker, so we ship the RAW DeepTMHMM-on-ortholog
    // topology (cohort='mouse_ortholog' / 'cyno_ortholog') with
    // topology_projection_source=null. Records that need the projected
    // topology get it via re-annotation, not at serve time. Higher-order
    // (one-to-many) ortholog rows are emitted as-is, same as the Python
    // path — there's no is_canonical filter on compara_ortholog_ecd.
    const existingOrthologs = record?.deterministic_features?.orthologs;
    const orthologsChecked = existingOrthologs?.checked === true;
    const orthologsEmpty = !existingOrthologs
      || ((existingOrthologs.mouse?.length ?? 0) === 0
          && (existingOrthologs.cynomolgus?.length ?? 0) === 0);
    const orthologsNeedEnrich = orthologsEmpty && !orthologsChecked;
    if (orthologsNeedEnrich && orthologEcdVersion) {
      // Pick the topology_version that has ortholog cohorts. The Python
      // annotator resolves mouse_topo_version specifically; in practice
      // mouse_ortholog + cyno_ortholog share a version. Default to the
      // canonical topology_version if no mouse-cohort row exists.
      const mouseTopoRow = await soft(
        env.DB.prepare(
          `SELECT r.topology_version FROM topology_release r
              WHERE EXISTS (
                SELECT 1 FROM topology_public p
                 WHERE p.cohort = 'mouse_ortholog' AND p.topology_version = r.topology_version
              )
              ORDER BY r.loaded_at DESC LIMIT 1`
        ).first(),
        "topology_release_ortholog",
      );
      const orthoTopoVersion = mouseTopoRow?.topology_version ?? canonicalTopoVersion ?? "";
      const orthologRows = await soft(
        env.DB.prepare(
          `SELECT eo.species, eo.ortholog_uniprot_acc, eo.ortholog_ensembl_gene,
                  eo.ortholog_gene_symbol, eo.ecd_pct_identity,
                  co.percent_identity AS full_length_pct_identity,
                  tp.tm_helix_count, tp.ecd_length_residues,
                  tp.per_residue_topology, tp.deeptmhmm_label,
                  tp.sequence AS ortholog_sequence,
                  eo.compara_release
             FROM compara_ortholog_ecd eo
             LEFT JOIN topology_public tp
               ON tp.uniprot_acc = eo.ortholog_uniprot_acc
              AND tp.topology_version = ?
              AND (
                (eo.species = 'mouse' AND tp.cohort = 'mouse_ortholog') OR
                (eo.species IN ('cynomolgus','cyno') AND tp.cohort = 'cyno_ortholog')
              )
             LEFT JOIN compara_ortholog co
               ON co.release_version = eo.compara_release
              AND co.human_ensembl_gene = eo.human_ensembl_gene
              AND co.species = eo.species
              AND co.ortholog_ensembl_gene = eo.ortholog_ensembl_gene
            WHERE eo.human_uniprot_acc = ?
              AND eo.ortholog_ecd_version = ?
            ORDER BY eo.species ASC`
        ).bind(orthoTopoVersion, uniprot, orthologEcdVersion).all(),
        "compara_ortholog_ecd",
      );
      // Belt-and-suspenders dedup: the LEFT JOIN against topology_public is
      // gated on topology_version; a stale topology_release lets multiple
      // versions slip through and produce two rows per (species, ortholog).
      // Key by (species, ortholog_uniprot_acc) — same gene's mouse + cyno
      // rows are legitimately distinct.
      const oresults = dedupeByKey(
        orthologRows?.results ?? [],
        (r) => `${r.species}::${r.ortholog_uniprot_acc}`,
      );
      const mouse = [];
      const cyno = [];
      const nowIso = new Date().toISOString();
      for (const r of oresults) {
        const species = String(r.species || "").toLowerCase();
        const ecdPct = r.ecd_pct_identity != null ? Number(r.ecd_pct_identity) : null;
        const fullPct = r.full_length_pct_identity != null ? Number(r.full_length_pct_identity) : null;
        const entry = {
          is_canonical: true,
          isoform_id: r.ortholog_uniprot_acc || "",
          ensembl_id: r.ortholog_ensembl_gene || "",
          ortholog_uniprot_acc: r.ortholog_uniprot_acc || "",
          ortholog_symbol: r.ortholog_gene_symbol || "",
          type: "one2one",
          ecd_pct_identity_to_human_canonical: ecdPct,
          // Similarity not yet wired in the underlying table; mirror identity.
          ecd_pct_similarity_to_human_canonical: ecdPct,
          full_length_pct_identity_to_human_canonical: fullPct,
          ecd_length_residues: Number(r.ecd_length_residues || 0),
          tm_helix_count: Number(r.tm_helix_count || 0),
          compara_version: r.compara_release || "",
          retrieved_at: nowIso,
          // Raw DeepTMHMM-on-ortholog values; the Python annotator's
          // projection is skipped at serve time (no alignment library in
          // the Worker). projection_source=null signals "raw values".
          per_residue_topology: r.per_residue_topology ?? null,
          deeptmhmm_label: r.deeptmhmm_label != null ? String(r.deeptmhmm_label) : null,
          topology_projection_source: null,
          tm_absent_from_model: false,
          n_tm_regions_absent: 0,
          sequence: r.ortholog_sequence ?? null,
        };
        if (species === "mouse") {
          mouse.push(entry);
        } else if (species === "cynomolgus" || species === "cyno") {
          cyno.push(entry);
        }
      }
      if (mouse.length > 0 || cyno.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.orthologs = {
          mouse,
          cynomolgus: cyno,
          checked: true,
        };
      }
    }
}

export async function enrichSurfaceBindAndBindome(env, record, uniprot, soft) {
    // ----- surface_bind -----
    // Mirror tools.surface_bind.lookup (D1-first). SURFACE-Bind's
    // ``surface_bind_protein`` table is keyed PRIMARY KEY on uniprot_acc
    // (one row per acc), and ``surface_bind_site`` is keyed (uniprot_acc,
    // site_id). There's no separate release table; the version is the
    // per-row ``surfacebind_version`` column. ORDER BY surfacebind_version
    // DESC LIMIT 1 is defensive — today the PK guarantees uniqueness, so
    // the ORDER BY is a no-op, but it keeps the query future-proof if the
    // schema ever allows multi-version coexistence (e.g. v1 + v2 atlases).
    //
    // Enrich when the record's surface_bind is missing OR carries
    // ``has_data=false`` despite a row existing in D1. Annotator-baked
    // positives win — a v2-orchestrator record with a real
    // SurfaceBindFeatures block is left alone so the data the LLM saw at
    // annotation time matches what the viewer renders.
    const existingSurfaceBind = record?.deterministic_features?.surface_bind;
    // A record baked before per-site topology existed carries sites with no
    // ``anchor_topology`` key. Those need enriching too, otherwise every
    // already-published gene keeps serving sites that don't say which side
    // of the membrane they're on — which is the whole point of the field.
    const sbSitesLackTopology = Array.isArray(existingSurfaceBind?.sites)
      && existingSurfaceBind.sites.length > 0
      && existingSurfaceBind.sites.every((s) => s?.anchor_topology === undefined);
    const sbNeedsEnrichment = !existingSurfaceBind
      || existingSurfaceBind.has_data === false
      || sbSitesLackTopology;
    if (sbNeedsEnrichment) {
      const sbProteinRow = await soft(
        env.DB.prepare(
          `SELECT chain, main_class, sub_class, protein_name, n_sites,
                  n_seeds_alpha, n_seeds_beta, n_seeds_total, pdbs
             FROM surface_bind_protein
            WHERE uniprot_acc = ?
            ORDER BY surfacebind_version DESC
            LIMIT 1`
        ).bind(uniprot).first(),
        "surface_bind_protein",
      );
      if (sbProteinRow) {
        const sbSiteRows = await soft(
          env.DB.prepare(
            `SELECT site_id, anchor_residue, area_a2, n_seeds_alpha,
                    n_seeds_beta, hydrophobicity
               FROM surface_bind_site
              WHERE uniprot_acc = ?
              ORDER BY site_id`
          ).bind(uniprot).all(),
          "surface_bind_site",
        );
        // Which side of the membrane each anchor residue sits on.
        // SURFACE-Bind scores the whole solved structure, so a scored
        // patch is not necessarily reachable from outside the cell:
        // cohort-wide, 23% of sites anchor somewhere other than the
        // extracellular face (EGFR alone contributes three kinase-domain
        // sites). Served as its own scalar pull rather than a JOIN so a
        // missing topology row degrades to nulls instead of dropping the
        // whole surface_bind block.
        // Pinned to the served canonical release: topology_public also holds
        // unregistered runs from other predictors (a full DeepTMHMM2 sweep
        // since 2026-09-27), and an unpinned LIMIT 1 could return any of them.
        const sbTopoRow = canonicalTopoVersion
          ? await soft(
              env.DB.prepare(
                `SELECT per_residue_topology
                   FROM topology_public
                  WHERE uniprot_acc = ? AND species = 'human'
                    AND is_canonical IN ('1', 1) AND cohort = 'human_canonical'
                    AND topology_version = ?
                  LIMIT 1`
              ).bind(uniprot, canonicalTopoVersion).first(),
              "topology_public_surface_bind",
            )
          : null;
        const prt = sbTopoRow?.per_residue_topology ?? null;
        // DeepTMHMM alphabet, per the per_residue_topology column comment
        // in cloudflare/d1_public_schema.sql ("O/M/I/S/B chars").
        const TOPO_CHARS = {
          O: "extracellular",
          I: "intracellular",
          M: "membrane",
          B: "membrane",
          S: "signal_peptide",
        };
        const anchorTopology = (residue) => {
          if (!prt || !Number.isFinite(residue)) return null;
          if (residue < 1 || residue > prt.length) return null;
          return TOPO_CHARS[prt[residue - 1]] ?? null;
        };
        // ``pdbs`` is stored as a JSON-encoded array string (see
        // scripts/sync_surface_bind_to_d1.py: ``json.dumps(entry.get("pdbs",
        // []))``). Defensively accept a real array (forward-compat), an
        // empty / null cell, or a comma-separated string (legacy snapshots).
        let pdbs = [];
        const rawPdbs = sbProteinRow.pdbs;
        if (Array.isArray(rawPdbs)) {
          pdbs = rawPdbs.map((x) => String(x)).filter(Boolean);
        } else if (typeof rawPdbs === "string" && rawPdbs.trim()) {
          const trimmed = rawPdbs.trim();
          if (trimmed.startsWith("[")) {
            try {
              const decoded = JSON.parse(trimmed);
              if (Array.isArray(decoded)) {
                pdbs = decoded.map((x) => String(x)).filter(Boolean);
              }
            } catch {
              // Fall through to comma-split below.
            }
          }
          if (pdbs.length === 0) {
            pdbs = trimmed.split(",").map((x) => x.trim()).filter(Boolean);
          }
        }
        const sites = (sbSiteRows?.results ?? []).map((s) => ({
          site_id: Number(s.site_id),
          anchor_residue: Number(s.anchor_residue),
          area_a2: Number(s.area_a2),
          n_seeds_alpha: Number(s.n_seeds_alpha),
          n_seeds_beta: Number(s.n_seeds_beta),
          hydrophobicity: Number(s.hydrophobicity),
          anchor_topology: anchorTopology(Number(s.anchor_residue)),
        }));
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.surface_bind = {
          has_data: true,
          n_sites: Number(sbProteinRow.n_sites ?? 0),
          n_seeds_alpha: Number(sbProteinRow.n_seeds_alpha ?? 0),
          n_seeds_beta: Number(sbProteinRow.n_seeds_beta ?? 0),
          n_seeds_total: Number(sbProteinRow.n_seeds_total ?? 0),
          chain: sbProteinRow.chain ?? null,
          sites,
          main_class: sbProteinRow.main_class ?? null,
          sub_class: sbProteinRow.sub_class ?? null,
          protein_name: sbProteinRow.protein_name ?? null,
          pdbs,
          // ``representative_structure`` is sourced from PDBe SIFTS at
          // annotation time (PR #54), not from the SURFACE-Bind tables.
          // Preserve whatever the record carried (often null) rather than
          // dropping it — the structure ranker isn't wired to the Worker.
          representative_structure:
            existingSurfaceBind?.representative_structure ?? null,
          source: "SURFACE-Bind v1 (Balbi 2026 PNAS)",
          attribution: "© Balbi et al., Correia lab — EPFL / Inria / Novo Nordisk",
          citation: "10.1073/pnas.2506269123",
        };
      }
    }

    // ----- bindome -----
    // Bindome (Wenckstern 2026, doi 10.64898/2026.07.30.741542) is a second
    // answer to "where could a binder go", from 305,806 BindCraft designs.
    // It publishes no target-side site list -- its own InterfaceResidues
    // column is the *binder* chain and every design ran `no_hotspot` -- so
    // `bindome_site_public` holds sites recovered from where the designs
    // land (scripts/build/build_bindome_sites.py).
    //
    // Served as its own block rather than merged into surface_bind: the two
    // are different methods with different per-site metrics (seed pools vs
    // design counts), and collapsing them would make the viewer's source
    // toggle a lie. `compartment` is computed from the same DeepTMHMM string
    // that labels surface_bind anchors, so one EC filter spans both.
    //
    // Attached only when D1 has rows. Every other enrichment here leaves the
    // body untouched when its query returns nothing, and
    // test_healthy_request_has_no_degraded_header_and_stable_body pins that:
    // an empty block on the ~4,800 genes with no Bindome data is noise.
    const bindomeRows = await soft(
      env.DB.prepare(
        `SELECT site_id, anchor_residue, compartment, n_residues,
                n_designs_supporting, n_designs_total, mean_design_fraction,
                residues, bindome_release
           FROM bindome_site_public
          WHERE uniprot_acc = ?
          ORDER BY site_id`
      ).bind(uniprot).all(),
      "bindome_site_public",
    );
    const bindomeSites = (bindomeRows?.results ?? []).map((s) => ({
      site_id: Number(s.site_id),
      anchor_residue: Number(s.anchor_residue),
      // Same key as surface_bind's per-site field, so the viewer reads one
      // property across both sources.
      anchor_topology: s.compartment ?? null,
      n_residues: Number(s.n_residues),
      n_designs_supporting: Number(s.n_designs_supporting),
      n_designs_total: Number(s.n_designs_total),
      mean_design_fraction:
        s.mean_design_fraction === null ? null : Number(s.mean_design_fraction),
      residues: String(s.residues ?? "")
        .split(",")
        .map((x) => Number(x))
        .filter(Number.isFinite),
    }));
    if (bindomeSites.length > 0) {
      if (!record.deterministic_features) record.deterministic_features = {};
      record.deterministic_features.bindome = {
        has_data: true,
        n_sites: bindomeSites.length,
        n_sites_extracellular: bindomeSites.filter(
          (s) => s.anchor_topology === "extracellular",
        ).length,
        sites: bindomeSites,
        release: bindomeRows?.results?.[0]?.bindome_release ?? null,
        source: "Bindome (Wenckstern 2026, BindCraft)",
        attribution: "\u00a9 Wenckstern et al., Correia lab \u2014 EPFL",
        citation: "10.64898/2026.07.30.741542",
      };
    }
}
