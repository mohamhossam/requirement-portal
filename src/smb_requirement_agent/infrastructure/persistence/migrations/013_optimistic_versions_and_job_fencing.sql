-- Maintenance-window migration: old binaries and workers must be stopped first.

-- Materialise optimistic versions in current-state payloads without touching
-- immutable revision snapshots. Legacy mappers already interpret an absent
-- value as version 1; writing it here makes PostgreSQL CAS predicates explicit.
UPDATE epics SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE requirement_analyses
SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE features SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE stories SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE story_change_proposals
SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE source_documents
SET payload=jsonb_set(payload, '{version_number}', '1'::jsonb, true)
WHERE NOT payload ? 'version_number';
UPDATE requirement_access
SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';
UPDATE breakdown_reviews
SET payload=jsonb_set(payload, '{version}', '1'::jsonb, true)
WHERE NOT payload ? 'version';

ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS attempt_token text;
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1;

ALTER TABLE ai_jobs DROP CONSTRAINT IF EXISTS ai_jobs_version_positive;
ALTER TABLE ai_jobs ADD CONSTRAINT ai_jobs_version_positive CHECK (version >= 1);

CREATE TABLE IF NOT EXISTS requirement_ai_job_leases (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    job_id text REFERENCES ai_jobs(job_id) ON DELETE SET NULL,
    worker_id text,
    attempt_token text,
    leased_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (job_id IS NULL AND worker_id IS NULL AND attempt_token IS NULL AND leased_until IS NULL)
        OR
        (job_id IS NOT NULL AND worker_id IS NOT NULL AND attempt_token IS NOT NULL AND leased_until IS NOT NULL)
    )
);

INSERT INTO requirement_ai_job_leases (requirement_id)
SELECT requirement_id FROM requirements
ON CONFLICT (requirement_id) DO NOTHING;

-- Commands accepted by an older release lack mandatory concurrency context.
UPDATE ai_jobs SET
    status='cancelled',
    cancel_requested_at=COALESCE(cancel_requested_at, now()),
    completed_at=COALESCE(completed_at, now()),
    updated_at=now(),
    failure=jsonb_build_object(
        'code', 'upgrade_retry_required',
        'message', 'Retry this action after refreshing the Requirement.',
        'retryable', true
    ),
    worker_id=NULL,
    leased_until=NULL,
    attempt_token=NULL,
    version=version+1
WHERE status IN ('queued', 'running', 'cancellation_requested');

CREATE TABLE IF NOT EXISTS feature_set_versions (
    epic_id text PRIMARY KEY REFERENCES epics(epic_id) ON DELETE CASCADE,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1)
);

INSERT INTO feature_set_versions (epic_id)
SELECT epic_id FROM epics
ON CONFLICT (epic_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS story_set_versions (
    feature_id text PRIMARY KEY REFERENCES features(feature_id) ON DELETE CASCADE,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1)
);

INSERT INTO story_set_versions (feature_id)
SELECT feature_id FROM features
ON CONFLICT (feature_id) DO NOTHING;
