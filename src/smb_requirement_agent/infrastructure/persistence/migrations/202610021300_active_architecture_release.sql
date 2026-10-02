-- Requirement work's local copy of which catalogue release is active (ADR-0099).
-- The catalogue reports each activation as an architecture_release_activated
-- event in the activating transaction; requirement work projects it here.
CREATE TABLE active_architecture_release (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    release_id text NOT NULL,
    seq bigint NOT NULL
);

-- Seed from the release active now, at sequence 0, so every later event replaces it.
INSERT INTO active_architecture_release (singleton, release_id, seq)
SELECT true, release_id, 0
FROM architecture_knowledge_releases
WHERE active;
