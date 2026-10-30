-- AI size suggestions for a Feature's Stories (ADR-0121).
--
-- One row per Feature holds the latest sizing pass and the fingerprint of the Story content
-- it read, like feature_quality_snapshots. A size the team confirms lives on the Story
-- itself; this table is never part of a revision.
CREATE TABLE IF NOT EXISTS feature_estimate_suggestions (
    feature_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
