-- Mapping a Requirement's backlog is requirement work with its own queue (ADR-0099).
--
-- Mapping jobs lived in the catalogue's architecture_jobs queue. They move here
-- with their id, input key, status, attempts and lease, so a queued or running
-- mapping is picked up by the requirement mapping worker after the upgrade.
CREATE TABLE requirement_mapping_jobs (
    job_id text PRIMARY KEY,
    kind text NOT NULL CHECK (kind = 'mapping'),
    subject_id text NOT NULL,
    fingerprint text NOT NULL,
    actor_id text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    lease_until timestamptz,
    error_category text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, subject_id, fingerprint)
);

INSERT INTO requirement_mapping_jobs
    (job_id, kind, subject_id, fingerprint, actor_id, status, attempts, lease_until,
     error_category, created_at, updated_at)
SELECT job_id, kind, subject_id, fingerprint, actor_id, status, attempts, lease_until,
       error_category, created_at, updated_at
FROM architecture_jobs
WHERE kind = 'mapping';

DELETE FROM architecture_jobs WHERE kind = 'mapping';
