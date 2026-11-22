-- L1 review page: record how each review row was authenticated.
--
-- Applied to the PRIVATE surfaceome_agents database (FEEDBACK_DB), after
-- l1_review_v1.sql. Writes no longer need the shared L1_REVIEW_TOKEN: a reviewer
-- types a name and passes Cloudflare Turnstile (rate-limited per IP). The token
-- still works as an alternative. auth_method says which path a row came in on:
--   'turnstile'  name + Turnstile (the name is self-reported, not verified)
--   'token'      header X-L1-Review-Token matched the L1_REVIEW_TOKEN secret
--   NULL         written before this migration (token-only era) or by a Worker
--                that ran before the column existed
--
-- ALTER TABLE ADD COLUMN is not idempotent in SQLite: apply once. A second run
-- fails with "duplicate column name" and changes nothing.
--
-- Requested by Becca Carlson, 2026-11-22 ("yes let's do name and turnstile").
-- Implemented by Claude Code session l1-review-ui.

ALTER TABLE l1_review ADD COLUMN auth_method TEXT;
ALTER TABLE l1_alt_tag ADD COLUMN auth_method TEXT;
