-- The reference library publishes each document's citable state as events, and
-- requirement work keeps a local copy to check citations against (ADR-0099).
-- Requirement transactions lock that copy where they used to lock
-- library_documents.

-- Written in the same transaction as the change each event reports.
CREATE TABLE knowledge_events (
    seq bigserial PRIMARY KEY,
    kind text NOT NULL,
    subject_id text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- One row per library document: its citable state, from the newest event applied.
CREATE TABLE reference_publication_state (
    document_id text PRIMARY KEY,
    seq bigint NOT NULL,
    payload jsonb NOT NULL
);

-- How far each consumer has read the outbox.
CREATE TABLE knowledge_event_cursors (
    consumer text PRIMARY KEY,
    seq bigint NOT NULL
);

-- Seed the copy from the library as it stands, at sequence 0, so every later
-- event replaces it. This builds the same state as LibraryDocument.citable_state():
-- the live, unwithdrawn publication; every block label of its version; and the
-- first included passage text per block of its revision, in passage order.
INSERT INTO reference_publication_state (document_id, seq, payload)
SELECT
    d.id,
    0,
    jsonb_build_object(
        'document_id', d.id,
        'owner_id', d.payload->'owner'->'id'->>'value',
        'title', d.payload->>'title',
        'version', d.version,
        'published', (
            SELECT jsonb_build_object(
                'publication_id', p->>'id',
                'fingerprint', p->>'fingerprint',
                'version_id', p->>'version_id',
                'version_number', (v->>'number')::integer,
                'revision_id', p->>'revision_id',
                'block_labels', COALESCE(
                    (
                        SELECT jsonb_agg(jsonb_build_array(b->>'id', b->>'label') ORDER BY bo)
                        FROM jsonb_array_elements(v->'blocks') WITH ORDINALITY AS blocks(b, bo)
                    ),
                    '[]'::jsonb
                ),
                'passages', COALESCE(
                    (
                        SELECT jsonb_agg(jsonb_build_array(first.block_id, first.text)
                                         ORDER BY first.position)
                        FROM (
                            SELECT
                                ps->>'block_id' AS block_id,
                                (array_agg(ps->>'text' ORDER BY po))[1] AS text,
                                min(po) AS position
                            FROM jsonb_array_elements(rev.r->'passages')
                                WITH ORDINALITY AS passages(ps, po)
                            WHERE (ps->>'included')::boolean
                            GROUP BY ps->>'block_id'
                        ) AS first
                    ),
                    '[]'::jsonb
                )
            )
            FROM jsonb_array_elements(d.payload->'publications') AS p
            JOIN jsonb_array_elements(d.payload->'versions') AS v
                ON v->>'id' = p->>'version_id'
            LEFT JOIN LATERAL (
                SELECT r
                FROM jsonb_array_elements(v->'revisions') AS r
                WHERE r->>'id' = p->>'revision_id'
                LIMIT 1
            ) AS rev ON true
            WHERE p->>'id' = d.payload->>'published_id'
              AND p->>'withdrawn_at' IS NULL
            LIMIT 1
        )
    )
FROM library_documents d;
