CREATE TABLE IF NOT EXISTS ai_jobs (
    job_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    operation text NOT NULL,
    status text NOT NULL,
    created_by jsonb NOT NULL,
    command jsonb NOT NULL,
    command_fingerprint text NOT NULL,
    idempotency_key text NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    started_at timestamptz,
    completed_at timestamptz,
    cancel_requested_at timestamptz,
    retry_of_job_id text REFERENCES ai_jobs(job_id) ON DELETE SET NULL,
    failure jsonb,
    result_resources jsonb NOT NULL DEFAULT '[]'::jsonb,
    worker_id text,
    leased_until timestamptz,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ai_jobs_actor_idempotency_idx
    ON ai_jobs ((created_by->>'id'), idempotency_key);
CREATE INDEX IF NOT EXISTS ai_jobs_requirement_created_idx
    ON ai_jobs (requirement_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_jobs_claim_idx
    ON ai_jobs (status, created_at)
    WHERE status IN ('queued', 'running', 'cancellation_requested');
CREATE UNIQUE INDEX IF NOT EXISTS ai_jobs_active_command_idx
    ON ai_jobs (requirement_id, command_fingerprint)
    WHERE status IN ('queued', 'running', 'cancellation_requested');

CREATE TABLE IF NOT EXISTS ai_job_idempotency_keys (
    actor_id text NOT NULL,
    idempotency_key text NOT NULL,
    job_id text NOT NULL REFERENCES ai_jobs(job_id) ON DELETE CASCADE,
    command_fingerprint text NOT NULL,
    PRIMARY KEY (actor_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS actor_notifications (
    notification_id text PRIMARY KEY,
    recipient_id text NOT NULL,
    job_id text NOT NULL REFERENCES ai_jobs(job_id) ON DELETE CASCADE,
    kind text NOT NULL,
    message text NOT NULL,
    resource_path text,
    created_at timestamptz NOT NULL,
    read_at timestamptz
);

CREATE INDEX IF NOT EXISTS actor_notifications_recipient_idx
    ON actor_notifications (recipient_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_preferences (
    actor_id text PRIMARY KEY,
    browser_enabled boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feature_quality_snapshots (
    feature_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
