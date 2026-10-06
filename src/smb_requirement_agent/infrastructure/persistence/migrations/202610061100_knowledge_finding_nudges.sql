-- Knowledge Center B2: a knowledge admin nudges the owners of a finding.
-- A nudge notifies without an AI job, so a notification's job is now optional.
ALTER TABLE actor_notifications ALTER COLUMN job_id DROP NOT NULL;

-- The nudge record is the audit trail: who asked, when, and whom it reached. It also
-- holds the cooldown: a finding is nudged at most once a week.
CREATE TABLE knowledge_finding_nudges (
    nudge_id text PRIMARY KEY,
    finding_id text NOT NULL REFERENCES requirement_knowledge_findings(finding_id) ON DELETE CASCADE,
    actor_id text NOT NULL,
    actor_name text NOT NULL,
    nudged_at timestamptz NOT NULL,
    recipients jsonb NOT NULL
);
CREATE INDEX knowledge_finding_nudges_latest ON knowledge_finding_nudges (finding_id, nudged_at DESC);
