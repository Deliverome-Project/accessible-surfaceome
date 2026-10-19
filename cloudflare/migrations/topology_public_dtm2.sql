-- topology_public — DeepTMHMM2 (v2) columns.
--
-- Additive only. Every statement here is an ADD COLUMN, so existing rows keep
-- their values and gain NULLs. No v1 row is rewritten by this migration, and
-- none can be: topology_public is keyed on
-- (topology_version, cohort, uniprot_acc_full) and v2 lands under its own
-- topology_version ('topo_2026_09_28_dtm2'), a disjoint namespace from the five
-- versions already present (topo_2026_05_16, topo_2026_05_25,
-- topo_2026_09_rescue, topo_test_optA_full).
--
-- Apply with:
--   npx --yes wrangler d1 execute surfaceome_public --remote \
--       --file=cloudflare/migrations/topology_public_dtm2.sql
--
-- SQLite has no ADD COLUMN IF NOT EXISTS. Re-running this file errors with
-- "duplicate column name" on the first column and changes nothing — that is the
-- intended idempotency behaviour, not a failure to investigate.
--
--
-- WHY NEW COLUMNS RATHER THAN REUSED ONES
--
-- v2 is a different model with a different output vocabulary, not a refresh of
-- v1. Three of its outputs have no v1 counterpart at all (membrane type,
-- reentrant loops, interfacial helices) and two contradict the v1 column
-- contract if written into it:
--
--   * per_residue_topology is documented as the alphabet {S,O,M,I,B}. v2 emits
--     {S,M,B,R,F,>} plus *membrane-specific* side characters — a eukaryotic
--     plasma-membrane protein gets E (cytoplasmic) / e (extracellular), an ER
--     protein H/h, a Golgi protein L/l. Writing that string into the v1 column
--     would silently break every consumer that counts 'O'.
--   * deeptmhmm_label has a five-value vocabulary {TM,SP,SP+TM,BETA,GLOB}. v2
--     distinguishes ten structural types.
--
-- So: every v1 column keeps its v1 meaning for v2 rows, filled by the documented
-- projection below; everything v2 adds goes in a dtm2_-prefixed column. The
-- prefix is the point — a reader cannot mistake dtm2_membrane_type for
-- something v1 produced, and a query that forgets to filter on topology_version
-- gets NULLs rather than a plausible wrong answer.


-- --------------------------------------------------------------------------
-- Structural type — seven values, a strict refinement of v1's five.
--
-- There is deliberately no second "type code" column. The model's internal
-- vocabulary lists ten codes including M+R / M+F / M+R+F, but those exist only
-- as CRF training labels: infer_structural_type() in
-- deeptmhmm2_predictor.utils.postprocessing can only ever return one of seven,
-- and the display strings are in bijection with them. A code column would be
-- pure redundancy, and would imply a reentrant/interfacial distinction that the
-- type never actually carries. That signal exists only in the topology string,
-- which is why dtm2_reentrant_count and dtm2_interfacial_count below are not
-- conveniences — they are the only place it is recorded.
-- --------------------------------------------------------------------------
ALTER TABLE topology_public ADD COLUMN dtm2_structural_type TEXT;
    -- Globular | Globular + SP | Alpha TM | Alpha TM + SP | Beta Barrel
    --   | Alpha TM + TP | Globular + TP

-- --------------------------------------------------------------------------
-- Per-residue topology, full v2 alphabet.
--
-- Alphabet: S signal peptide, > transit peptide, M alpha TM helix, B beta
-- strand, R reentrant loop, F interfacial helix, plus two side characters whose
-- identity depends on dtm2_main_membrane_type_idx (see MEMBRANE_TOPOLOGY_MAP in
-- deeptmhmm2_predictor.constants).
--
-- This string is NOT self-describing: 'E' means cytoplasmic for a plasma-
-- membrane protein and nothing at all for a Golgi one, and indices 16/17
-- (chloroplast/mitochondrial outer membrane) invert the usual case sense, so
-- "uppercase = inside" is wrong. Decode it through
-- accessible_surfaceome.sources.deeptmhmm2, never by hand.
--
-- Non-TM proteins (type code I, S, T) have no membrane type, and the model
-- emits plain I/O for them regardless.
-- --------------------------------------------------------------------------
ALTER TABLE topology_public ADD COLUMN dtm2_topology_string TEXT;
ALTER TABLE topology_public ADD COLUMN dtm2_v1_alphabet_lossy INTEGER;
    -- 1 iff projecting to per_residue_topology discarded information, i.e. the
    -- v2 string contained R, F or >. See the projection table in
    -- sources/deeptmhmm2.py. Summary counts are always computed from
    -- dtm2_topology_string, never from the projection, so a lossy projection
    -- cannot inflate tm_helix_count.

-- --------------------------------------------------------------------------
-- Membrane type. Multi-label: the model scores 17 supported compartments
-- against per-type empirical thresholds and any number can pass, so the
-- "answer" is a set. dtm2_main_membrane_type is the highest-probability member
-- of that set, and is what decodes the side characters above.
-- --------------------------------------------------------------------------
ALTER TABLE topology_public ADD COLUMN dtm2_main_membrane_type TEXT;
    -- e.g. 'Eukaryotic plasma membrane'. NULL for non-TM proteins.
ALTER TABLE topology_public ADD COLUMN dtm2_main_membrane_type_idx INTEGER;
    -- The model's own index. Stored because it, not the display name, is the
    -- key into MEMBRANE_TOPOLOGY_MAP that makes dtm2_topology_string readable.
ALTER TABLE topology_public ADD COLUMN dtm2_membrane_types TEXT;
    -- JSON array of every type over threshold, highest probability first.
    -- '[]' for non-TM proteins. A JSON array rather than a delimited string
    -- because two type names contain commas-adjacent punctuation and one
    -- ('Bacterial Gram-negative inner membrane') contains a hyphen; json_each()
    -- makes membership queries exact.
ALTER TABLE topology_public ADD COLUMN dtm2_membrane_type_probs TEXT;
    -- JSON object {type_name: probability} over all 17 supported types, 2 dp.
    -- Stored in full, not just the winner: the thresholds are empirical and
    -- published as such, so keeping the raw scores means a future re-threshold
    -- is a SQL query rather than a 12.5M-residue rerun.

-- --------------------------------------------------------------------------
-- Plasma-membrane call — the column this whole exercise exists to produce.
--
-- Deliberately NOT folded into predicted_surface_membrane. That column is
-- defined as "deeptmhmm_label in {TM, SP+TM}" and keeps that definition for v2
-- rows, so a v1-vs-v2 comparison on identical rules is one join. v2's real
-- improvement is that it answers *which membrane* rather than inferring the
-- plasma membrane from the presence of a TM helix, and that answer belongs in
-- its own column where the difference between the two is measurable.
-- --------------------------------------------------------------------------
ALTER TABLE topology_public ADD COLUMN dtm2_plasma_membrane INTEGER;
    -- 1 iff 'Eukaryotic plasma membrane' (model index 3) is over its threshold.
ALTER TABLE topology_public ADD COLUMN dtm2_plasma_membrane_prob REAL;
    -- Its raw probability, kept even when the call is 0. The published
    -- threshold for this type is 0.172 — low enough that the margin matters
    -- when triaging, and the call alone throws that away.

-- --------------------------------------------------------------------------
-- Features v1 could not represent, and the only record of them anywhere in the
-- schema (see the structural-type note above). Counts are segment counts,
-- matching how tm_helix_count and beta_strand_count are defined for v1 rows.
-- --------------------------------------------------------------------------
ALTER TABLE topology_public ADD COLUMN dtm2_reentrant_count INTEGER;
ALTER TABLE topology_public ADD COLUMN dtm2_interfacial_count INTEGER;
ALTER TABLE topology_public ADD COLUMN dtm2_transit_peptide_length INTEGER;
    -- Residue count of '>'. Kept out of signal_peptide_length on purpose: a
    -- mitochondrial/plastid transit peptide is not a secretory signal peptide,
    -- and merging them would corrupt the v1 column for every v2 row.

-- --------------------------------------------------------------------------
-- Not stored, on purpose: the per-segment region list (the `segments` field of
-- predictions.json and the TMRs.gff3 rows). It is an exact, deterministic
-- run-length encoding of dtm2_topology_string given
-- dtm2_main_membrane_type_idx, so storing it would add roughly 30 MB of
-- derivable JSON. sources/deeptmhmm2.segments() reconstructs it. This follows
-- the rule the table already states for v1: store the string and the sequence,
-- derive the features.
-- --------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_topology_public_dtm2_pm
    ON topology_public (topology_version, dtm2_plasma_membrane);
CREATE INDEX IF NOT EXISTS idx_topology_public_dtm2_memtype
    ON topology_public (topology_version, dtm2_main_membrane_type);
