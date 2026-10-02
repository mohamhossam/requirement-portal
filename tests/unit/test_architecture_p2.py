"""Shared sample requirements, the in-use/draft comparison and the embedding cache."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.application.ports.architecture_rag import EvidenceChunk
from smb_requirement_agent.domain.architecture.knowledge import (
    InvalidKnowledgeError,
    KnowledgeConflictError,
)
from smb_requirement_agent.domain.architecture.samples import (
    MAX_SAMPLE_CHARACTERS,
    SampleRequirement,
    SampleRequirementSet,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import InMemoryEvidenceIndex
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.persistence.in_memory_sample_requirements import (
    InMemorySampleRequirements,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
READER = {"X-Fake-Actor-Id": "fake-reviewer"}
SAMPLES = "/architecture-knowledge/sample-requirements"
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_the_sample_list_has_limits() -> None:
    with pytest.raises(InvalidKnowledgeError, match="blank"):
        SampleRequirement("s1", "   ")
    with pytest.raises(InvalidKnowledgeError, match="2,000"):
        SampleRequirement("s1", "x" * (MAX_SAMPLE_CHARACTERS + 1))
    with pytest.raises(InvalidKnowledgeError, match="at most 20"):
        SampleRequirementSet(items=tuple(SampleRequirement(f"s{n}", "text") for n in range(21)))
    with pytest.raises(InvalidKnowledgeError, match="unique"):
        SampleRequirementSet(items=(SampleRequirement("s", "a"), SampleRequirement("s", "b")))
    with pytest.raises(InvalidKnowledgeError, match="revision"):
        SampleRequirementSet(revision=-1)


def test_a_stale_save_is_refused() -> None:
    repository = InMemorySampleRequirements()
    first = repository.load().replaced((SampleRequirement("s", "a"),), "amina", NOW)
    repository.save(first, 0)

    with pytest.raises(KnowledgeConflictError, match="reload"):
        repository.save(first.replaced((), "ravi", NOW), 0)
    assert repository.load() == first


def test_maintainers_keep_one_shared_sample_list(client: TestClient) -> None:
    assert client.get(SAMPLES, headers=OWNER).json()["items"] == []

    saved = client.put(
        SAMPLES,
        json={
            "expected_revision": 0,
            "items": [{"text": "Customers upload a product catalogue"}, {"text": " Bill orders "}],
        },
        headers=OWNER,
    )

    body = saved.json()
    assert saved.status_code == 200
    assert body["revision"] == 1
    assert [item["text"] for item in body["items"]] == [
        "Customers upload a product catalogue",
        "Bill orders",
    ]
    assert all(item["id"] for item in body["items"])
    assert body["updated_by"] == "fake-owner"
    kept = client.put(
        SAMPLES, json={"expected_revision": 1, "items": body["items"][:1]}, headers=OWNER
    ).json()
    assert kept["items"] == body["items"][:1]
    assert (
        client.put(SAMPLES, json={"expected_revision": 1, "items": []}, headers=OWNER).status_code
        == 409
    )
    too_many = [{"text": f"sample {n}"} for n in range(21)]
    assert (
        client.put(
            SAMPLES, json={"expected_revision": 2, "items": too_many}, headers=OWNER
        ).status_code
        == 422
    )
    assert client.get(SAMPLES, headers=READER).status_code == 403


def test_a_built_draft_is_compared_with_the_version_in_use(client: TestClient) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    changed = client.put(
        f"{base}/systems/order-hub",
        json={
            "expected_revision": draft["revision"],
            "system": {"id": "order-hub", "name": "Order Hub", "aliases": ["partner orders"]},
        },
        headers=OWNER,
    ).json()
    query = {"query": "Order Hub validates partner orders against BCRM"}
    assert client.post(f"{base}/compare-impact", json=query, headers=OWNER).status_code == 409

    client.post(f"{base}/build", json={"expected_revision": changed["revision"]}, headers=OWNER)
    compared = client.post(f"{base}/compare-impact", json=query, headers=OWNER)

    body = compared.json()
    assert compared.status_code == 200
    in_use = {item["id"] for item in body["in_use"]["systems"]}
    this_version = {item["id"]: item["name"] for item in body["this_version"]["systems"]}
    assert "bcrm" in in_use and "order-hub" not in in_use
    assert this_version["order-hub"] == "Order Hub"
    assert body["this_version"]["release_id"] == draft["id"]
    assert client.post(f"{base}/compare-impact", json=query, headers=READER).status_code == 403
    blank = client.post(f"{base}/compare-impact", json={"query": "  "}, headers=OWNER)
    assert blank.status_code == 422


class _Counting(FakeEmbeddings):
    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.embedded.extend(texts)
        return super().embed(texts)


def test_a_rebuild_embeds_only_passages_that_changed() -> None:
    embeddings = _Counting()
    index = InMemoryEvidenceIndex(embeddings, FakeWordTokenizer())
    chunks = tuple(EvidenceChunk(f"c{n}", "Doc", f"line {n}", f"passage {n}") for n in range(5))
    index.store("draft", "first", (*chunks, chunks[0]))
    assert embeddings.embedded == [f"passage {n}" for n in range(5)]

    index.store("draft", "second", (*chunks[:4], EvidenceChunk("c9", "Doc", "line 9", "new")))

    assert embeddings.embedded[5:] == ["new"]
    assert [chunk.id for chunk in index.retrieve("second", "passage 3", 2)][0] == "c3"
