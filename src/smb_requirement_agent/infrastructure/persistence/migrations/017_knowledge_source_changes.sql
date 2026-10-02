CREATE TABLE knowledge_source_changes (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    change_number bigint NOT NULL DEFAULT 1,
    dirty boolean NOT NULL DEFAULT true
);
CREATE INDEX knowledge_source_changes_pending ON knowledge_source_changes (requirement_id)
    WHERE dirty;
INSERT INTO knowledge_source_changes (requirement_id) SELECT requirement_id FROM requirements;

CREATE FUNCTION mark_knowledge_source_changed() RETURNS trigger AS $$
DECLARE source_id text;
BEGIN
    source_id := COALESCE(NEW.requirement_id, OLD.requirement_id);
    IF EXISTS (SELECT 1 FROM requirements WHERE requirement_id=source_id) THEN
        INSERT INTO knowledge_source_changes (requirement_id) VALUES (source_id)
        ON CONFLICT (requirement_id) DO UPDATE
        SET change_number=knowledge_source_changes.change_number+1, dirty=true;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_requirement_changed AFTER INSERT OR UPDATE ON requirements
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();
CREATE TRIGGER knowledge_analysis_changed AFTER INSERT OR UPDATE OR DELETE ON requirement_analyses
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();
CREATE TRIGGER knowledge_access_changed AFTER INSERT OR UPDATE OR DELETE ON requirement_access
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();
CREATE TRIGGER knowledge_question_changed AFTER INSERT OR UPDATE OR DELETE ON analysis_questions
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();

CREATE FUNCTION mark_knowledge_decision_sources_changed() RETURNS trigger AS $$
BEGIN
    INSERT INTO knowledge_source_changes (requirement_id)
    VALUES (NEW.subject_requirement_id), (NEW.related_requirement_id)
    ON CONFLICT (requirement_id) DO UPDATE
    SET change_number=knowledge_source_changes.change_number+1, dirty=true;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_decision_changed AFTER UPDATE ON requirement_knowledge_findings
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_decision_sources_changed();
