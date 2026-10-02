"""Opt-in nonempty PostgreSQL backup/restore fixture. Never targets application databases.

Run seed, take pg_dump, restore into a NEW database, then run verify there with the
seed manifest. Providers/scanning are synthetic; this does not qualify deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from pydantic import TypeAdapter

from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.document_library import CHUNKING_POLICY
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.domain.analysis.value_objects import IntentProposalStatus
from smb_requirement_agent.domain.document.library import ReviewedPassage
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.infrastructure.config.options import (
    LLMProvider,
    PersistenceProvider,
)
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.documents.library_worker import ClamAvDocumentScanner
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition.operations import (
    build_projection_rebuild,
)
from smb_requirement_agent.interfaces.api.container import Container, build_container

DATABASE_PREFIX = "codex_qualification_test_"


def require_test_database(database_url: str) -> str:
    name = str(conninfo_to_dict(database_url).get("dbname", ""))
    if not name.startswith(DATABASE_PREFIX) or name == DATABASE_PREFIX:
        raise ValueError(f"Qualification requires a disposable database named {DATABASE_PREFIX}*.")
    return name


@contextmanager
def fixture_container(database_url: str) -> Iterator[Container]:
    require_test_database(database_url)
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=database_url,
    )
    # Test-only substitution at the same seam as the existing PostgreSQL browser fixture.
    with patch.object(ClamAvDocumentScanner, "scan", return_value=True):
        container = build_container(settings)
        try:
            yield container
        finally:
            container.close_resources()


@dataclass(frozen=True)
class TableDigest:
    rows: int
    sha256: str


@dataclass(frozen=True)
class RecoveryManifest:
    source_database: str
    document_id: str
    version_id: str
    original_sha256: str
    tables: dict[str, TableDigest]


def table_digests(database_url: str) -> dict[str, TableDigest]:
    """Hash every public table without exporting document bodies or credentials."""
    require_test_database(database_url)
    result: dict[str, TableDigest] = {}
    with psycopg.connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall()
        for (name,) in tables:
            digest = hashlib.sha256()
            count = 0
            query = sql.SQL("SELECT to_jsonb(t)::text FROM public.{} t ORDER BY 1").format(
                sql.Identifier(name)
            )
            with connection.cursor(name="qualification_digest") as cursor:
                cursor.execute(query)
                for (row,) in cursor:
                    digest.update(row.encode("utf-8") + b"\n")
                    count += 1
            result[name] = TableDigest(count, digest.hexdigest())
    return result


def check_restored_behavior(database_url: str, manifest: RecoveryManifest) -> None:
    with fixture_container(database_url) as container:
        if not container.readiness_check():
            raise RuntimeError("Restored schema/projection readiness failed.")
        _, content = container.document_library.original(
            manifest.document_id, manifest.version_id, FAKE_ACTORS[0]
        )
        if hashlib.sha256(content).hexdigest() != manifest.original_sha256:
            raise RuntimeError("Original file checksum changed after recovery.")
        try:
            container.document_library.original(
                manifest.document_id, manifest.version_id, FAKE_ACTORS[1]
            )
        except AuthorizationDeniedError:
            pass
        else:
            raise RuntimeError("Restored original file leaked to a non-owner.")
        results = container.reference_knowledge.search("XGPON coverage")
        if not results or any(c.document_id != manifest.document_id for c in results):
            raise RuntimeError(
                "Restored search lost the active source or exposed a private source."
            )
        if any("PRIVATE" in c.original_text or "PRIVATE" in c.context_text for c in results):
            raise RuntimeError("An excluded passage leaked through search.")
        dependencies = container.source_impact.page(
            FAKE_ACTORS[0], document_id=manifest.document_id
        ).items
        if not dependencies:
            raise RuntimeError("Restored source dependencies are missing.")


def seed(database_url: str) -> RecoveryManifest:
    name = require_test_database(database_url)
    with psycopg.connect(database_url) as connection:
        actual = connection.execute("SELECT current_database()").fetchone()
        if actual is None or actual[0] != name:
            raise RuntimeError("Connected database does not match the qualification target.")
        if connection.execute(
            "SELECT 1 FROM pg_tables WHERE schemaname='public' LIMIT 1"
        ).fetchone():
            raise RuntimeError(
                "Seed requires a new empty database; it never truncates existing data."
            )
    run_migrations(database_url)
    build_projection_rebuild(database_url)()
    original = b"XGPON coverage is required for high-speed orders.\nPRIVATE internal pricing."
    with fixture_container(database_url) as container:
        library = container.document_library
        owner = FAKE_ACTORS[0]
        uploaded = library.submit(
            "Recovery policy",
            UploadDocumentInput("recovery.txt", "text/plain", original),
            "recovery-published",
            owner,
        )
        if not library.process_next():
            raise RuntimeError("Synthetic ingestion did not complete.")
        document = library.get(uploaded.id, owner)
        version = document.versions[0]
        passages = tuple(
            ReviewedPassage(
                block.id,
                block.text or "",
                "PRIVATE" not in (block.text or ""),
                "Private source excluded" if "PRIVATE" in (block.text or "") else "",
            )
            for block in version.blocks
        )
        if not any(not p.included for p in passages):
            raise RuntimeError("Fixture must contain an independently excluded passage.")
        reviewed = library.review(
            document.id, version.id, document.version, owner, passages, "Synthetic recovery review"
        )
        revision = reviewed.versions[0].revisions[-1]
        library.approve(
            document.id,
            version.id,
            revision.id,
            revision.fingerprint(version.id, CHUNKING_POLICY),
            reviewed.version,
            owner,
        )
        if not container.reference_knowledge.index_next():
            raise RuntimeError("Synthetic publication did not index.")
        requirement = container.create_requirement.execute(
            CreateRequirementInput("XGPON recovery", "Order high-speed bundles through BCRM."),
            owner,
        )
        analysis = container.analyze_requirement.execute(owner, requirement.id)
        proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
        container.analysis_collaboration.decide_intent_proposal(
            requirement.id,
            proposal.id,
            IntentProposalStatus.ACCEPTED,
            proposal.version,
            owner,
            rationale="Synthetic recovery acceptance",
        )
        library.submit(
            "PRIVATE unpublished policy",
            UploadDocumentInput("private.txt", "text/plain", b"PRIVATE XGPON draft"),
            "recovery-private",
            FAKE_ACTORS[1],
        )
        if not library.process_next():
            raise RuntimeError("Private fixture ingestion did not complete.")
    build_projection_rebuild(database_url)()
    manifest = RecoveryManifest(
        name,
        document.id,
        version.id,
        hashlib.sha256(original).hexdigest(),
        table_digests(database_url),
    )
    check_restored_behavior(database_url, manifest)
    # Building the graph refreshes actor profiles. Capture the backup baseline only
    # after all fixture/readback work has closed its connections.
    return replace(manifest, tables=table_digests(database_url))


def verify(database_url: str, manifest: RecoveryManifest) -> dict[str, object]:
    if require_test_database(database_url) == manifest.source_database:
        raise ValueError("Restore verification requires a different database from the seed.")
    actual = table_digests(database_url)
    if actual != manifest.tables:
        changed = sorted(
            name
            for name in actual.keys() | manifest.tables.keys()
            if actual.get(name) != manifest.tables.get(name)
        )
        raise RuntimeError(f"Restored table counts/content differ: {', '.join(changed)}")
    check_restored_behavior(database_url, manifest)
    run_migrations(database_url)
    rebuilt = build_projection_rebuild(database_url)()
    check_restored_behavior(database_url, manifest)
    second = build_projection_rebuild(database_url)()
    check_restored_behavior(database_url, manifest)
    if rebuilt != second or not rebuilt:
        raise RuntimeError("Nonempty projection maintenance was not repeatable.")
    after = table_digests(database_url)
    for name in ("document_blobs", "library_documents", "analysis_rounds", "breakdown_revisions"):
        if not manifest.tables[name].rows or after[name] != manifest.tables[name]:
            raise RuntimeError(f"Maintenance altered or lost authoritative recovery data: {name}")
    return {
        "status": "passed",
        "scope": "synthetic PostgreSQL restore, not production recovery qualification",
        "tables_verified": len(actual),
        "rows_verified": sum(table.rows for table in actual.values()),
        "requirements_rebuilt_twice": rebuilt,
        "original_checksum_verified": True,
        "publication_and_history_digests_verified": True,
        "private_original_and_excluded_passage_guards_verified": True,
        "source_dependency_and_search_reads_verified": True,
        "authoritative_history_unchanged_after_maintenance": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seed", "verify"))
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "seed":
        manifest = seed(args.database_url)
        args.manifest.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
        print(json.dumps({"status": "seeded", "tables": len(manifest.tables)}))
    else:
        manifest = TypeAdapter(RecoveryManifest).validate_json(args.manifest.read_bytes())
        print(json.dumps(verify(args.database_url, manifest), indent=2))


if __name__ == "__main__":
    main()
