-- Approved backlogs on their way to the knowledge service (ADR-0101 Amendment 2).
--
-- A breakdown's final approval writes one row in its own transaction; a worker leases
-- due rows, renders the approved revision's export once into payload, and delivers it
-- to the knowledge service's change-request inbox until it answers. One row per
-- approval, so a replayed approval queues nothing new.
CREATE TABLE approved_backlog_handoffs (
    approval_id text PRIMARY KEY,
    requirement_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'delivered', 'skipped', 'failed')),
    next_attempt_at timestamptz NOT NULL,
    lease_until timestamptz,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX approved_backlog_handoffs_due
    ON approved_backlog_handoffs(next_attempt_at, approval_id)
    WHERE status = 'pending';
CREATE INDEX approved_backlog_handoffs_requirement
    ON approved_backlog_handoffs(requirement_id);
