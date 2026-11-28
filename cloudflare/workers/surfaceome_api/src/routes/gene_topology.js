// Serve-time canonical, library-designed, and isoform topology enrichment for /v1/genes/:symbol.

export async function enrichGeneTopology(env, record, sym, uniprot, { canonicalTopoVersion, isoformTopoVersion }, soft, dedupeByKey) {
    // ----- canonical_topology -----
    // Mirror _fetch_canonical_topology. Enrich when the record's
    // canonical_topology is missing OR carries the
    // ``tool_version='placeholder-no-d1-row'`` stub the Python annotator
    // emits when no D1 row was available at annotation time. Annotator
    // records with a real DeepTMHMM row are left alone.
    const existingCanonTopo = record?.deterministic_features?.canonical_topology;
    const canonTopoIsPlaceholder = existingCanonTopo?.tool_version === "placeholder-no-d1-row";
    // Records baked before the DeepTMHMM call / length columns were carried
    // through have the block but not these keys. Without this every already
    // published gene keeps hiding the tool's own classification behind the
    // derived ECD/ICD numbers.
    // Records store the call as an explicit null too (the Python builder
    // didn't select the column until 2026-10-17), so test == null, not
    // === undefined, or the call stays blank on nearly every gene.
    const canonTopoLacksCall = !!existingCanonTopo
      && existingCanonTopo.predicted_surface_membrane == null;
    const canonTopoNeedsEnrich =
      !existingCanonTopo || canonTopoIsPlaceholder || canonTopoLacksCall;
    if (canonTopoNeedsEnrich && canonicalTopoVersion) {
      const tr = await soft(
        env.DB.prepare(
          `SELECT uniprot_acc_full, isoform_id, tm_helix_count,
                  n_terminal_orientation, c_terminal_orientation,
                  signal_peptide_length, ecd_length_residues, icd_length_residues,
                  per_residue_topology, sequence, tool_version, retrieved_at,
                  predicted_surface_membrane, predicted_secreted,
                  beta_strand_count, protein_length
             FROM topology_public
            WHERE uniprot_acc = ? AND cohort = 'human_canonical'
              AND topology_version = ?
            LIMIT 1`
        ).bind(uniprot, canonicalTopoVersion).first(),
        "topology_public_canonical",
      );
      if (tr) {
        // DeepTMHMM's own call. Stored as 0/1 INTEGER in D1; null stays null
        // so "column absent" never reads as a confident false.
        const call = {
          predicted_surface_membrane:
            tr.predicted_surface_membrane == null ? null : Boolean(Number(tr.predicted_surface_membrane)),
          predicted_secreted:
            tr.predicted_secreted == null ? null : Boolean(Number(tr.predicted_secreted)),
          beta_strand_count:
            tr.beta_strand_count == null ? null : Number(tr.beta_strand_count),
          protein_length:
            tr.protein_length == null ? null : Number(tr.protein_length),
        };
        if (existingCanonTopo && !canonTopoIsPlaceholder) {
          // A real annotator block that only lacks the call: fill those
          // fields and keep every other key as the record stores it.
          // Rebuilding the block here dropped the record's explicit-null
          // keys (ecd_pct_identity_to_canonical and friends) on every gene.
          for (const [k, v] of Object.entries(call)) {
            if (existingCanonTopo[k] == null) existingCanonTopo[k] = v;
          }
        } else {
          if (!record.deterministic_features) record.deterministic_features = {};
          record.deterministic_features.canonical_topology = {
            isoform_id: tr.isoform_id || `${uniprot}-1`,
            uniprot_acc: tr.uniprot_acc_full || uniprot,
            tm_helix_count: Number(tr.tm_helix_count || 0),
            n_terminal_orientation: tr.n_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
            c_terminal_orientation: tr.c_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
            signal_peptide_length: Number(tr.signal_peptide_length || 0),
            ecd_length_residues: Number(tr.ecd_length_residues || 0),
            icd_length_residues: Number(tr.icd_length_residues || 0),
            per_residue_topology: tr.per_residue_topology || "",
            sequence: tr.sequence ?? null,
            tool_version: tr.tool_version || "deeptmhmm-1.0.24",
            retrieved_at: tr.retrieved_at || new Date().toISOString(),
            ...call,
          };
        }
      }
    }

    // ----- deterministic_features.library_designed_topology -----
    // The topology of the protein each LIBRARY MEMBER actually encodes, as opposed
    // to canonical_topology above, which is the topology of the gene's canonical
    // UniProt sequence. Those are frequently different proteins: a member's ORF is
    // its designed CDS, an Ensembl-transcript product, which for a substantial
    // minority corresponds to a UniProt *isoform* record (816 of 5,896 resolved
    // members; 119 of the 121 whose AlphaFold model turned out to be the wrong
    // protein). Colouring a library member's structure with canonical_topology
    // therefore offsets the overlay silently, with a plausible helix count.
    //
    // The matching row CANNOT be found here by accession. It is resolved offline by
    // exact sequence and stored as a pointer in library_topology_public, which this
    // joins straight through to topology_public. A member with no pointer row has
    // had no v1 run on its exact sequence and gets NO entry — never the canonical
    // as a stand-in. `tool` is always deeptmhmm_v1: the v1 string is what the
    // structure viewer colours by, and the v2 back-projection is lossy.
    //
    // Additive: older viewers ignore the field. Keyed on gene_symbol because that
    // is what identifies the gene page; the member's own accession travels in
    // `topology_acc` so a caller can still see which record was matched.
    const libTopo = await soft(
      env.DB.prepare(
        `SELECT lt.candidate_id, lt.library, lt.candidate_set, lt.species,
                lt.topology_tool, lt.topology_cohort, lt.topology_version,
                lt.topology_acc, lt.ordered_length_aa, lt.sequence_sha256,
                tp.per_residue_topology, tp.tm_helix_count, tp.beta_strand_count,
                tp.n_terminal_orientation, tp.c_terminal_orientation,
                tp.signal_peptide_length, tp.ecd_length_residues,
                tp.icd_length_residues, tp.predicted_surface_membrane,
                tp.predicted_secreted, tp.tool_version
           FROM library_topology_public lt
           JOIN topology_public tp
             ON tp.cohort = lt.topology_cohort
            AND tp.topology_version = lt.topology_version
            AND tp.uniprot_acc_full = lt.topology_acc
          WHERE lt.gene_symbol = ?
          ORDER BY lt.library ASC, lt.candidate_id ASC`
      )
        .bind(sym)
        .all(),
      "library_topology_public",
    );
    if (libTopo?.results?.length) {
      if (!record.deterministic_features) record.deterministic_features = {};
      record.deterministic_features.library_designed_topology =
        libTopo.results.map((r) => ({
          candidate_id: r.candidate_id,
          // Library TRANCHE (l1/l2) — not a tool version.
          library: r.library,
          candidate_set: r.candidate_set,
          species: r.species,
          tool: r.topology_tool,
          cohort: r.topology_cohort,
          topology_version: r.topology_version,
          // Which topology_public row this came from, so the match is auditable.
          topology_acc: r.topology_acc,
          // sha256 of the ordered protein — the key the match was made on.
          sequence_sha256: r.sequence_sha256,
          ordered_length_aa:
            r.ordered_length_aa == null ? null : Number(r.ordered_length_aa),
          per_residue_topology: r.per_residue_topology || "",
          tm_helix_count: Number(r.tm_helix_count || 0),
          beta_strand_count:
            r.beta_strand_count == null ? null : Number(r.beta_strand_count),
          n_terminal_orientation:
            r.n_terminal_orientation === "extracellular"
              ? "extracellular"
              : "cytoplasmic",
          c_terminal_orientation:
            r.c_terminal_orientation === "extracellular"
              ? "extracellular"
              : "cytoplasmic",
          signal_peptide_length: Number(r.signal_peptide_length || 0),
          ecd_length_residues: Number(r.ecd_length_residues || 0),
          icd_length_residues: Number(r.icd_length_residues || 0),
          predicted_surface_membrane:
            r.predicted_surface_membrane == null
              ? null
              : Boolean(Number(r.predicted_surface_membrane)),
          predicted_secreted:
            r.predicted_secreted == null
              ? null
              : Boolean(Number(r.predicted_secreted)),
          tool_version: r.tool_version || "deeptmhmm-1.0.24",
        }));
    }

    // ----- deterministic_features.library_designed_structure -----
    // Which structure a library member should render, and how to renumber it.
    // The viewer's default -- AFDB's model for the gene's canonical accession -- is the
    // wrong protein for 296 of 2,725 L1 members, and nothing on the page said so.
    //
    // `residue_offset` is NOT decoration. For a `contained` member the ordered protein is
    // a subsequence of the model, so construct residue i is model residue i + offset
    // (offsets here run to 134). A viewer that ignores it draws SLC3A2 101 residues out of
    // frame while looking entirely plausible. `display_first_model_residue` /
    // `display_last_model_residue` are the span the construct actually covers, so the
    // renderer can clip to it rather than silently showing extra protein.
    //
    // Alternates (is_chosen = 0) travel too, with the note saying why they lost, so the
    // page can show "AlphaFold DB models a different proteoform" instead of hiding it.
    const libStruct = await soft(
      env.DB.prepare(
        `SELECT candidate_id, candidate_set, species, source, r2_key, model_url,
                proteoform_match, residue_offset, ordered_length_aa, model_length_aa,
                is_chosen, mean_plddt, note
           FROM library_structure_public
          WHERE gene_symbol = ?
          ORDER BY is_chosen DESC, candidate_id ASC`
      )
        .bind(sym)
        .all(),
      "library_structure_public",
    );
    if (libStruct?.results?.length) {
      if (!record.deterministic_features) record.deterministic_features = {};
      record.deterministic_features.library_designed_structure =
        libStruct.results.map((r) => {
          const offset = Number(r.residue_offset || 0);
          const orderedLen =
            r.ordered_length_aa == null ? null : Number(r.ordered_length_aa);
          return {
            candidate_id: r.candidate_id,
            candidate_set: r.candidate_set,
            species: r.species,
            // 'colabfold' = we folded the ordered sequence; 'alphafold_db' = AFDB's
            // model is genuinely the ordered protein (or contains it).
            source: r.source,
            r2_key: r.r2_key || null,
            model_url: r.model_url || null,
            proteoform_match: r.proteoform_match,
            residue_offset: offset,
            ordered_length_aa: orderedLen,
            model_length_aa:
              r.model_length_aa == null ? null : Number(r.model_length_aa),
            // The model residues the construct covers, 1-based and inclusive. Null when
            // the ordered length is unknown, never guessed.
            display_first_model_residue: orderedLen == null ? null : offset + 1,
            display_last_model_residue:
              orderedLen == null ? null : offset + orderedLen,
            is_chosen: Boolean(Number(r.is_chosen)),
            mean_plddt: r.mean_plddt == null ? null : Number(r.mean_plddt),
            note: r.note || null,
          };
        });
    }

    // ----- gene.ensembl_canonical_protein -----
    // The stable-ID cache carries the canonical ENSP, but the record's gene
    // block only ever shipped ensembl_gene — so the API was weaker than the
    // figure TSVs, which require the canonical protein "when the row
    // references a specific protein isoform". Enrich rather than require a
    // re-annotation, and only when absent so a baked value always wins.
    if (record?.gene && record.gene.ensembl_canonical_protein == null) {
      const giRow = await soft(
        env.DB.prepare(
          `SELECT ensembl_canonical_protein
             FROM gene_identifier_public
            WHERE uniprot_acc = ?
            LIMIT 1`
        ).bind(uniprot).first(),
        "gene_identifier_public",
      );
      if (giRow?.ensembl_canonical_protein) {
        record.gene.ensembl_canonical_protein = giRow.ensembl_canonical_protein;
      }
    }

    // ----- isoform_topologies -----
    // Mirror _fetch_isoform_topologies. Enrich when the field is missing
    // OR (the array is empty AND ``isoform_topologies_checked`` is not
    // True). The latter sentinel is the annotator's "we ran the isoforms
    // cohort and this gene genuinely has no alternative isoforms" signal;
    // we honor it. The Worker does NOT compute %identity to canonical
    // (BLOSUM62 alignment is too heavy for the request hot path); identity
    // fields are emitted as null. Records that need real %identity values
    // get them via re-annotation, not at serve time.
    const existingIsoTopo = record?.deterministic_features?.isoform_topologies;
    const isoTopoChecked = record?.deterministic_features?.isoform_topologies_checked === true;
    const isoTopoNeedsEnrich = !Array.isArray(existingIsoTopo)
      || (existingIsoTopo.length === 0 && !isoTopoChecked);
    if (isoTopoNeedsEnrich && isoformTopoVersion) {
      const isoRows = await soft(
        env.DB.prepare(
          `SELECT uniprot_acc_full, isoform_id, tm_helix_count,
                  n_terminal_orientation, c_terminal_orientation,
                  signal_peptide_length, ecd_length_residues, icd_length_residues,
                  per_residue_topology, sequence, tool_version, retrieved_at
             FROM topology_public
            WHERE uniprot_acc = ? AND cohort = 'human_isoforms'
              AND topology_version = ?
            ORDER BY uniprot_acc_full ASC`
        ).bind(uniprot, isoformTopoVersion).all(),
        "topology_public_isoform",
      );
      // Belt-and-suspenders dedup: even though the query filters by
      // topology_version, a stale topology_release row would let multiple
      // versions slip through and produce duplicate isoform rows (one per
      // version). Also drop any row whose uniprot_acc_full matches the
      // canonical accession — those belong to the human_canonical cohort
      // and shouldn't be inside human_isoforms.
      const rawIsoResults = isoRows?.results ?? [];
      const results = dedupeByKey(
        rawIsoResults.filter((r) => r.uniprot_acc_full && r.uniprot_acc_full !== uniprot),
        (r) => r.uniprot_acc_full,
      );
      if (results.length > 0) {
        if (!record.deterministic_features) record.deterministic_features = {};
        record.deterministic_features.isoform_topologies = results.map((r) => ({
          isoform_id: r.isoform_id || r.uniprot_acc_full,
          uniprot_acc: r.uniprot_acc_full || uniprot,
          tm_helix_count: Number(r.tm_helix_count || 0),
          n_terminal_orientation: r.n_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          c_terminal_orientation: r.c_terminal_orientation === "extracellular" ? "extracellular" : "cytoplasmic",
          signal_peptide_length: Number(r.signal_peptide_length || 0),
          ecd_length_residues: Number(r.ecd_length_residues || 0),
          icd_length_residues: Number(r.icd_length_residues || 0),
          per_residue_topology: r.per_residue_topology || "",
          sequence: r.sequence ?? null,
          tool_version: r.tool_version || "deeptmhmm-1.0.24",
          retrieved_at: r.retrieved_at || new Date().toISOString(),
          // %identity to canonical not computed at serve time (BLOSUM62
          // alignment is too heavy here). Re-annotation fills these in.
          full_length_pct_identity_to_canonical: null,
          ecd_pct_identity_to_canonical: null,
          ecd_pct_similarity_to_canonical: null,
        }));
      }
    }
}
