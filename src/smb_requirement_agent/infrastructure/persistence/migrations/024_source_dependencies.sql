-- A rebuildable reverse index. Original snapshots and impact decisions remain immutable.
-- Require the explicit maintenance backfill before existing installations serve traffic.
DELETE FROM maintenance_markers WHERE name = 'activity-worklist-v2';
CREATE TABLE source_dependencies (
    id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    document_id text NOT NULL,
    target_kind text NOT NULL,
    current boolean NOT NULL,
    active boolean NOT NULL,
    search_text text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX ix_source_dependencies_document ON source_dependencies(document_id,current DESC,requirement_id,target_kind,id);
CREATE INDEX ix_source_dependencies_requirement ON source_dependencies(requirement_id) WHERE active;
CREATE TABLE source_impact_decisions (
    dependency_id text NOT NULL REFERENCES source_dependencies(id),
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    PRIMARY KEY (dependency_id,version)
);
