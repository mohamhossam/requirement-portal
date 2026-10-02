-- Derived vectors/checkpoints only. Source change numbers remain authoritative.
CREATE TABLE requirement_index_progress (
    identity text NOT NULL,
    source_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    token text,
    lease_until timestamptz,
    PRIMARY KEY(identity,source_id)
);
