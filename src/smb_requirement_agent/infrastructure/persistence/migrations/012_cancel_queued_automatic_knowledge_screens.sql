UPDATE ai_jobs
SET status = 'cancelled',
    cancel_requested_at = COALESCE(cancel_requested_at, now()),
    completed_at = COALESCE(completed_at, now()),
    updated_at = now(),
    worker_id = NULL,
    leased_until = NULL
WHERE operation = 'screen_requirement_knowledge'
  AND origin = 'automatic'
  AND status = 'queued';
