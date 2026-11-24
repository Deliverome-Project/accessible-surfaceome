-- Additive migration for per-member N-after-SP SignalP 6 vs DeepTMHMM v1
-- pre/post-tag metrics and SP concern classification on l1_member_annotation_public.
--
-- Applied to the PUBLIC mirror (surfaceome_public). Purely additive nullable columns
-- so existing loads and older viewers keep working unchanged.

ALTER TABLE l1_member_annotation_public ADD COLUMN sp_concern TEXT CHECK (sp_concern IS NULL OR sp_concern IN ('clean', 'concerning'));
ALTER TABLE l1_member_annotation_public ADD COLUMN sp_metrics_json TEXT;
