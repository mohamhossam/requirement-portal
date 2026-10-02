-- Derived and rebuildable. Immutable revisions remain authoritative.
CREATE TABLE activity_event_projection (
    event_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    category text NOT NULL,
    action text NOT NULL,
    actor_id text,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX activity_event_time ON activity_event_projection (occurred_at DESC,event_id DESC);
CREATE INDEX activity_event_requirement ON activity_event_projection
    (requirement_id,occurred_at DESC,event_id DESC);
CREATE INDEX activity_event_actor ON activity_event_projection (actor_id,occurred_at DESC);
CREATE INDEX activity_event_action ON activity_event_projection (action,occurred_at DESC);
CREATE TABLE current_blocker_projection (
    blocker_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    opened_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX current_blocker_age ON current_blocker_projection (opened_at,blocker_id);
