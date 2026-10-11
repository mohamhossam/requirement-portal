-- Decided product verdicts on their way to the knowledge service (ontology plan Phase 5).
--
-- Accepting, overriding or marking unknown a suggested product impact writes one row in
-- the decision's own transaction, already rendered as the precedent the knowledge service
-- keeps; a worker leases due rows and delivers them until the service answers. One row per
-- analysis version, so a replayed decision queues nothing new.
CREATE TABLE precedent_handoffs (
    handoff_id text PRIMARY KEY,
    requirement_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'delivered', 'skipped', 'failed')),
    next_attempt_at timestamptz NOT NULL,
    lease_until timestamptz,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX precedent_handoffs_due
    ON precedent_handoffs(next_attempt_at, handoff_id)
    WHERE status = 'pending';
CREATE INDEX precedent_handoffs_requirement
    ON precedent_handoffs(requirement_id);
