"""Idempotent maintenance command for importing legacy filesystem document bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import psycopg

from smb_requirement_agent.infrastructure.config.options import PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.requirements.application.errors import DocumentStorageError


def _references(value: object) -> list[tuple[str, str, int | None]]:
    found: list[tuple[str, str, int | None]] = []
    if isinstance(value, dict):
        raw_id = value.get("version_id")
        if raw_id is None and all(
            key in value for key in ("id", "filename", "mime_type", "size_bytes")
        ):
            raw_id = value.get("id")
        checksum = value.get("checksum_sha256")
        if isinstance(raw_id, str) and isinstance(checksum, str):
            size = value.get("size_bytes")
            found.append((raw_id, checksum, int(size) if isinstance(size, int) else None))
        for child in value.values():
            found.extend(_references(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_references(child))
    return found


def backfill(database_url: str, source_root: str) -> int:
    root = Path(source_root).resolve()
    imported = 0
    with psycopg.connect(database_url) as connection:
        manifest: dict[str, tuple[str, int | None]] = {}
        current_rows = connection.execute("SELECT payload FROM source_documents").fetchall()
        revision_rows = connection.execute(
            "SELECT payload FROM requirement_revisions UNION ALL "
            "SELECT payload FROM breakdown_revisions"
        ).fetchall()
        for row in (*current_rows, *revision_rows):
            payload = cast(dict[str, Any], row[0])
            for version_id, checksum, size in _references(payload):
                prior = manifest.get(version_id)
                if prior is not None and (
                    prior[0] != checksum
                    or (prior[1] is not None and size is not None and prior[1] != size)
                ):
                    raise DocumentStorageError(
                        f"Document version {version_id!r} has conflicting historical metadata."
                    )
                manifest[version_id] = (checksum, prior[1] if prior is not None else size)

        for version_id, (expected_checksum, recorded_size) in sorted(manifest.items()):
            target = (root / f"{version_id}.blob").resolve()
            if target.parent != root or not target.is_file():
                raise DocumentStorageError(
                    f"Legacy document bytes for version {version_id!r} are missing."
                )
            content = target.read_bytes()
            actual_checksum = hashlib.sha256(content).hexdigest()
            expected_size = recorded_size if recorded_size is not None else len(content)
            if len(content) != expected_size or actual_checksum != expected_checksum:
                raise DocumentStorageError(
                    f"Legacy document version {version_id!r} failed checksum or size verification."
                )
            connection.execute(
                """
                INSERT INTO document_blobs
                    (document_version_id,checksum_sha256,size_bytes,content)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (document_version_id) DO NOTHING
                """,
                (version_id, actual_checksum, expected_size, content),
            )
            stored = connection.execute(
                """
                SELECT checksum_sha256,size_bytes,content FROM document_blobs
                WHERE document_version_id=%s
                """,
                (version_id,),
            ).fetchone()
            stored_content = bytes(stored[2]) if stored is not None else b""
            if (
                stored is None
                or str(stored[0]) != expected_checksum
                or int(stored[1]) != expected_size
                or len(stored_content) != expected_size
                or hashlib.sha256(stored_content).hexdigest() != expected_checksum
            ):
                raise DocumentStorageError(
                    f"PostgreSQL document version {version_id!r} does not match the manifest."
                )
            marker = connection.execute(
                """
                INSERT INTO document_blob_imports
                    (document_version_id,source_checksum_sha256)
                VALUES (%s,%s) ON CONFLICT (document_version_id) DO NOTHING
                RETURNING document_version_id
                """,
                (version_id, expected_checksum),
            ).fetchone()
            imported += int(marker is not None)
    return imported


def main() -> None:
    settings = Settings.from_env()
    if (
        settings.persistence_provider is not PersistenceProvider.POSTGRES
        or settings.database_url is None
    ):
        raise DocumentStorageError(
            "Blob backfill requires PostgreSQL persistence and DATABASE_URL."
        )
    count = backfill(settings.database_url, settings.document_storage_path)
    print(f"Imported {count} legacy document blob(s).")


if __name__ == "__main__":
    main()
