CREATE TABLE activity_input_cursors (
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    source_kind text NOT NULL,
    source_id text NOT NULL,
    source_version text NOT NULL,
    PRIMARY KEY (requirement_id, source_kind, source_id)
);
DELETE FROM maintenance_markers WHERE name = 'activity-worklist-v2';
