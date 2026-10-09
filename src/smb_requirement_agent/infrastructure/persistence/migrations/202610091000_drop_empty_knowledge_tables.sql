-- The knowledge service owns the library, the architecture and squad catalogues,
-- their blobs and the event feed (ADR-0099). Earlier migrations here still create
-- those tables, so this one removes them again: a fresh database ends with none.
--
-- All or nothing, and only when nothing is lost: if any of them holds a row, every
-- one stays for `knowledge-import` and the guarded `drop-knowledge-tables` command,
-- which checks rows against the knowledge database first. Tables already gone are
-- skipped. Children before parents (the reverse of MOVED_TABLES), and no CASCADE,
-- so an unexpected dependent fails the migration instead of being dropped with it.
DO $$
DECLARE
    moved text[] := ARRAY[
        'knowledge_events',
        'organisation_audit',
        'organisation_catalogue',
        'architecture_jobs',
        'architecture_sample_requirements',
        'architecture_extraction_runs',
        'architecture_catalogue_candidates',
        'architecture_knowledge_audit',
        'architecture_embedding_cache',
        'architecture_knowledge_chunks',
        'architecture_knowledge_indexes',
        'architecture_knowledge_documents',
        'architecture_knowledge_releases',
        'knowledge_document_blobs',
        'library_embedding_cache',
        'library_chunks',
        'library_submissions',
        'library_documents'
    ];
    present text[];
    moved_table text;
    holds_rows boolean;
BEGIN
    -- Pinned to this connection's own schema, never found further along the path.
    SELECT coalesce(array_agg(t ORDER BY ordinality), '{}') INTO present
    FROM unnest(moved) WITH ORDINALITY AS m(t, ordinality)
    WHERE EXISTS (
        SELECT 1 FROM pg_tables WHERE schemaname = current_schema() AND tablename = m.t
    );
    FOREACH moved_table IN ARRAY present LOOP
        EXECUTE format('LOCK TABLE %I.%I IN ACCESS EXCLUSIVE MODE', current_schema(), moved_table);
    END LOOP;
    FOREACH moved_table IN ARRAY present LOOP
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I)', current_schema(), moved_table)
            INTO holds_rows;
        IF holds_rows THEN
            RETURN;
        END IF;
    END LOOP;
    FOREACH moved_table IN ARRAY present LOOP
        EXECUTE format('DROP TABLE %I.%I', current_schema(), moved_table);
    END LOOP;
END
$$;
