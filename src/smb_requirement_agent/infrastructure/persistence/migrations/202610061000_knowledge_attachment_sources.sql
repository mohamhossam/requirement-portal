-- A Requirement's included attachments are part of its knowledge source (Knowledge Center B1).
-- Inclusion, the included version, hidden worksheets and removal all live in the row, so a
-- change to any of them marks the Requirement for re-indexing. A draft's documents have no
-- Requirement yet; promotion sets requirement_id, which marks it then.
CREATE TRIGGER knowledge_attachment_changed AFTER INSERT OR UPDATE OR DELETE ON source_documents
    FOR EACH ROW EXECUTE FUNCTION mark_knowledge_source_changed();
-- Requirements that already have included attachments are indexed again once.
UPDATE knowledge_source_changes c
SET change_number=c.change_number+1, dirty=true
WHERE EXISTS (
    SELECT 1 FROM source_documents d
    WHERE d.requirement_id=c.requirement_id
      AND d.payload->>'included_version_id' IS NOT NULL
      AND (d.payload->>'removed')::boolean = false
);
