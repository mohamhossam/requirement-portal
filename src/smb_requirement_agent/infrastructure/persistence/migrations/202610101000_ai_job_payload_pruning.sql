-- The retention command clears the stored inputs (`command`) of succeeded and cancelled
-- jobs past AI_JOB_PAYLOAD_RETENTION_DAYS, and marks when (ADR-0079 amendment). Rows are
-- kept, so the activity feed is unchanged; a pruned job can no longer be retried.
-- Additive only: existing jobs keep NULL, which means "inputs kept".
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS payload_pruned_at timestamptz;

-- The retention command's batches: finished jobs not yet pruned, oldest first.
CREATE INDEX IF NOT EXISTS ai_jobs_prunable_idx
    ON ai_jobs (completed_at)
    WHERE payload_pruned_at IS NULL AND status IN ('succeeded', 'cancelled');
