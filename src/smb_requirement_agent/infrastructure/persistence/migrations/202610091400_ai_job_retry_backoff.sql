-- A job that met a transient provider or platform outage returns to the queue and is
-- not claimed again before next_attempt_at (ADR-0020 amendment, retry with backoff).
-- Additive only: existing jobs keep NULL, which means "claimable now".
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;

-- The claim query asks, per Requirement, whether a queued job is still waiting.
CREATE INDEX IF NOT EXISTS ai_jobs_waiting_retry_idx
    ON ai_jobs (requirement_id, next_attempt_at)
    WHERE status = 'queued' AND next_attempt_at IS NOT NULL;
