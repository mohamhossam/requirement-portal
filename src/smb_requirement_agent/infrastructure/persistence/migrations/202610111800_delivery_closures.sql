-- Closed and removed Epics on their way to the knowledge service (ontology plan Phase 7).
--
-- The work-item tracker's service hook writes one row per event on a published Epic that
-- was closed or removed; a worker leases due rows, renders what the Epic delivered once,
-- and delivers it until the service answers. A replayed event queues nothing new.
CREATE TABLE delivery_closures (
    closure_id text PRIMARY KEY,
    requirement_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'delivered', 'skipped', 'failed')),
    next_attempt_at timestamptz NOT NULL,
    lease_until timestamptz,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX delivery_closures_due
    ON delivery_closures(next_attempt_at, closure_id)
    WHERE status = 'pending';
CREATE INDEX delivery_closures_requirement
    ON delivery_closures(requirement_id);

-- A tracker event names a work item, not a Requirement: find the publication whose
-- mappings hold it.
CREATE INDEX backlog_publications_mappings
    ON backlog_publications USING gin ((payload -> 'mappings') jsonb_path_ops);
