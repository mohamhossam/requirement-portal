"""Isolated browser-test entry point; never used by the application launcher.

Uses PostgreSQL with deterministic providers and a synthetic scanner. A database
whose name contains 'test' is mandatory. This is not malware qualification.
"""

from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import patch

from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict
from smb_kernel.documents.scanner import ClamAvDocumentScanner, OfflineDocumentScanner

from smb_requirement_agent.infrastructure.config.options import LLMProvider, PersistenceProvider
from smb_requirement_agent.infrastructure.config.settings import PersistenceSettings, Settings
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.interfaces.api.composition.operations import build_projection_rebuild
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app as application


def create_app() -> FastAPI:
    url = PersistenceSettings.from_env().database_url
    if not url or "test" not in str(conninfo_to_dict(url).get("dbname", "")):
        raise RuntimeError(
            "Lineage browser tests require a named test database and fake providers."
        )
    settings = Settings(
        llm_provider=LLMProvider.FAKE,
        persistence_provider=PersistenceProvider.POSTGRES,
        database_url=url,
    )
    run_migrations(url)
    build_projection_rebuild(url)()

    def factory() -> Container:
        stack = ExitStack()
        try:
            scanner = OfflineDocumentScanner()
            stack.enter_context(
                patch.object(
                    ClamAvDocumentScanner, "scan", lambda _self, content: scanner.scan(content)
                )
            )
            container = build_container(settings)
            stack.callback(container.close_resources)
            return replace(container, close_resources=stack.pop_all().close)
        except BaseException:
            stack.close()
            raise

    return application(factory)
