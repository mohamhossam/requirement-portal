-- Knowledge Center B3: a knowledge admin retires a Requirement from the knowledge corpus and
-- reinstates it, and retries or reindexes the corpus in bulk.

-- One row per Requirement that has ever been retired; its state says whether it is retired
-- now. The Requirement itself is untouched: it stays readable and keeps its version.
CREATE TABLE requirement_corpus_membership (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    state text NOT NULL CHECK (state IN ('active', 'retired')),
    reason text NOT NULL,
    actor_id text NOT NULL,
    actor_name text NOT NULL,
    changed_at timestamptz NOT NULL
);
CREATE INDEX requirement_corpus_membership_retired ON requirement_corpus_membership (requirement_id)
    WHERE state = 'retired';

-- Retiring drops the Requirement's passages from the index; reinstating restores them.
CREATE TRIGGER knowledge_membership_changed
    AFTER INSERT OR UPDATE OR DELETE ON requirement_corpus_membership
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();

-- The audit trail of every corpus action: who, when, why, and which Requirements.
CREATE TABLE knowledge_corpus_actions (
    action_id text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('retire', 'reinstate', 'retry', 'reindex')),
    requirement_ids jsonb NOT NULL,
    actor_id text NOT NULL,
    actor_name text NOT NULL,
    reason text,
    acted_at timestamptz NOT NULL
);
CREATE INDEX knowledge_corpus_actions_latest ON knowledge_corpus_actions (acted_at DESC);
