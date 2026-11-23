-- Additive migration for L1 review staleness detection: records the canonical
-- signature of the reviewed tag site(s) (site_id, insert_after_residue, leader,
-- cassette) alongside sequence_sha256 so reviews are automatically marked out
-- of date if either the protein sequence or the tag location changes.
--
-- Applied to the PRIVATE surfaceome_agents database (FEEDBACK_DB).

ALTER TABLE l1_review ADD COLUMN site_signature TEXT;
ALTER TABLE l1_alt_tag ADD COLUMN site_signature TEXT;
