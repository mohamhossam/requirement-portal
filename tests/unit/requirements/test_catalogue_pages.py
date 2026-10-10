"""Paged drafts and documents against the in-memory store (production hardening PR 13)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.catalogue_scenarios import (
    documents_page_with_owners_counts_and_privacy,
    drafts_page_by_owner_search_and_title,
)


def test_drafts_page_by_owner_search_and_title(client: TestClient) -> None:
    drafts_page_by_owner_search_and_title(client)


def test_documents_page_with_owners_counts_and_privacy(client: TestClient) -> None:
    documents_page_with_owners_counts_and_privacy(client)
