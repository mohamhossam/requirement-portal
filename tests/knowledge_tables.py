"""The knowledge tables requirement work's earlier migrations created (ADR-0099, ADR-0104).

The knowledge portal owns the library, the architecture and squad catalogues, their
blobs and the event feed. Earlier migrations here still create those tables; the last
two remove them again and refuse a database still holding them. Tests that replay an
earlier system's schema leave those two out.
"""

from __future__ import annotations

# Parents before children.
KNOWLEDGE_TABLES: tuple[str, ...] = (
    "library_documents",
    "library_submissions",
    "library_chunks",
    "library_embedding_cache",
    "knowledge_document_blobs",
    "architecture_knowledge_releases",
    "architecture_knowledge_documents",
    "architecture_knowledge_indexes",
    "architecture_knowledge_chunks",
    "architecture_embedding_cache",
    "architecture_knowledge_audit",
    "architecture_catalogue_candidates",
    "architecture_extraction_runs",
    "architecture_sample_requirements",
    "architecture_jobs",
    "organisation_catalogue",
    "organisation_audit",
    "knowledge_events",
)

# Drops the tables while every one is empty.
DROP_EMPTY_MIGRATION = "202610091000_drop_empty_knowledge_tables.sql"
# Stops the upgrade while any table is left, so none outlives the tools that moved them.
REQUIRE_GONE_MIGRATION = "202610091200_require_knowledge_tables_gone.sql"
KNOWLEDGE_TABLE_DROPS = frozenset({DROP_EMPTY_MIGRATION, REQUIRE_GONE_MIGRATION})
