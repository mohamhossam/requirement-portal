-- Coordinated release only: old queued commands cannot be upgraded by inventing consent.
UPDATE ai_jobs SET status='cancelled', completed_at=now(), updated_at=now(),
    version=version+1, worker_id=NULL, attempt_token=NULL, leased_until=NULL
WHERE status IN ('queued','running','cancellation_requested')
    AND command->>'context_token' LIKE 'generation-context-v1:%';
UPDATE requirement_ai_job_leases AS lease SET job_id=NULL, worker_id=NULL,
    attempt_token=NULL, leased_until=NULL, updated_at=now()
WHERE EXISTS (SELECT 1 FROM ai_jobs AS job WHERE job.job_id=lease.job_id AND job.status='cancelled');
