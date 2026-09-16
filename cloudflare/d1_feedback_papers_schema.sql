
-- Private paper metadata; PDF bytes live in the private FEEDBACK_PAPERS R2 bucket.
CREATE TABLE IF NOT EXISTS feedback_paper (
    id TEXT PRIMARY KEY,
    feedback_id TEXT NOT NULL REFERENCES feedback(id),
    object_key TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
    rights_acknowledgment TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_paper_submission ON feedback_paper(feedback_id);
