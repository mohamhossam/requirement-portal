CREATE TABLE activity_projection_cursors (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    requirement_revision integer NOT NULL,
    breakdown_revision integer NOT NULL,
    review_status text,
    first_recorded_at timestamptz NOT NULL
);
DELETE FROM maintenance_markers WHERE name='activity-worklist-v2';
