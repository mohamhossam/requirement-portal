-- The knowledge portal owns the library, the architecture and squad catalogues,
-- their blobs and the event feed (ADR-0099, ADR-0104). The previous migration drops
-- those tables while every one is empty, so one still here holds rows that were
-- never moved. The commands that copied and dropped them are gone, so the upgrade
-- stops here rather than leave the rows stranded: move them with an earlier
-- version first (docs/operations/deployment.md, "Knowledge tables left behind").
DO $$
DECLARE
    left_behind text;
BEGIN
    SELECT string_agg(tablename, ', ' ORDER BY tablename) INTO left_behind
    FROM pg_tables
    WHERE schemaname = current_schema()
      AND tablename IN (
        'library_documents',
        'library_submissions',
        'library_chunks',
        'library_embedding_cache',
        'knowledge_document_blobs',
        'architecture_knowledge_releases',
        'architecture_knowledge_documents',
        'architecture_knowledge_indexes',
        'architecture_knowledge_chunks',
        'architecture_embedding_cache',
        'architecture_knowledge_audit',
        'architecture_catalogue_candidates',
        'architecture_extraction_runs',
        'architecture_sample_requirements',
        'architecture_jobs',
        'organisation_catalogue',
        'organisation_audit',
        'knowledge_events'
      );
    IF left_behind IS NOT NULL THEN
        -- The runner reports only the message, so it carries the way forward too.
        RAISE EXCEPTION 'Knowledge tables still hold rows: %. Copy them to the knowledge '
            'portal and drop them with an earlier requirement-portal version; see '
            'docs/operations/deployment.md, "Knowledge tables left behind".', left_behind;
    END IF;
END
$$;
