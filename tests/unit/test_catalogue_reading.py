"""Long documents are read in pieces that fit the configured model, and jobs recover.

The reported failure: a local model with the default 8,192-token window (4,096
reserved for the answer) could not take the 24,000-character batches the first
version sent, so reading a Word document failed outright, and asking again left
the job waiting forever once its attempts ran out.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_kernel.llm.structured_output import (
    OutputTruncatedError,
    StructuredOutputError,
)

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.ports.architecture_jobs import (
    ArchitectureJob,
    ArchitectureJobKind,
    ArchitectureJobStatus,
)
from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueAnswerUnusableError,
    CatalogueCitationError,
    CatalogueExtractionError,
    CatalogueExtractionUnsupportedError,
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
)
from smb_requirement_agent.application.public_errors import describe_public_error
from smb_requirement_agent.domain.architecture.knowledge import KnowledgeConflictError
from smb_requirement_agent.infrastructure.llm.catalogue_extraction import (
    ChangeOutput,
    ExtractionOutput,
    StructuredCatalogueExtractor,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_jobs import (
    InMemoryArchitectureJobs,
)

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)
PARAGRAPH = (
    "The Order Hub service receives partner orders and validates them against the "
    "customer records held in BCRM before provisioning starts. "
) * 5


def _change(**values: Any) -> ChangeOutput:
    base: dict[str, Any] = {
        "kind": "system",
        "system": "Order Hub",
        "name": "Order Hub",
        "name_ar": None,
        "aliases": [],
        "triggers": [],
        "target_system": None,
        "component": None,
        "technology": None,
        "domain": None,
        "parent_domain": None,
        "offering": None,
        "journey": None,
        "text": None,
        "evidence_numbers": [1],
        "quote": "The Order Hub service receives partner orders",
        "basis": "stated",
        "reasoning": None,
        "relationship_kind": None,
    }
    return ChangeOutput(**(base | values))


class _Recording:
    """A structured client that records each prompt and answers from a script."""

    model = "recording"

    def __init__(self, answers: list[Any] | None = None) -> None:
        self.prompts: list[str] = []
        self.answers = answers or []

    def parse(self, *, system_prompt: str, user_prompt: str, **_: Any) -> ExtractionOutput:
        self.prompts.append(system_prompt + user_prompt)
        answer = self.answers.pop(0) if self.answers else ExtractionOutput(changes=[_change()])
        if isinstance(answer, Exception):
            raise answer
        return answer


def _document(paragraphs: int) -> ExtractionRequest:
    return ExtractionRequest(
        "Architecture reference",
        tuple(
            ExtractionSegment(number, f"paragraph {number}", PARAGRAPH)
            for number in range(1, paragraphs + 1)
        ),
        (KnownSystem("bcrm", "BCRM", ("customer records",)),),
    )


def _extractor(
    client: Any, budget: int | None = 4096, output: int | None = None
) -> StructuredCatalogueExtractor:
    return StructuredCatalogueExtractor(
        client, supports_images=True, max_input_tokens=budget, max_output_tokens=output
    )


def test_a_long_document_is_split_so_every_call_fits_the_budget() -> None:
    client = _Recording()

    proposal = _extractor(client).propose(_document(40))

    assert len(client.prompts) >= 3
    assert all(len(prompt) // 4 < 4096 for prompt in client.prompts)
    # Every call's answer is kept, each citing its own passage.
    assert {change.locations for change in proposal.changes} >= {("paragraph 1",)}
    assert proposal.warnings == ()


def test_an_oversized_passage_is_cut_into_parts_that_keep_its_location() -> None:
    client = _Recording()
    huge = ExtractionRequest("Doc", (ExtractionSegment(1, "page 3", PARAGRAPH * 40),), ())

    proposal = _extractor(client).propose(huge)

    assert len(client.prompts) >= 2
    assert proposal.changes[0].locations[0].startswith("page 3 (part 1 of ")


def test_one_unreadable_part_is_a_warning_and_only_total_failure_fails() -> None:
    bad = StructuredOutputError("bad")
    client = _Recording([ExtractionOutput(changes=[_change()]), bad, bad])

    proposal = _extractor(client).propose(_document(40))

    assert len(proposal.changes) >= 1
    assert any("could not be read: the model's answer was unusable" in w for w in proposal.warnings)
    with pytest.raises(CatalogueExtractionError, match="No part of the document"):
        _extractor(_Recording([bad] * 10)).propose(_document(3))


def _failure(kind: str) -> StructuredOutputError:
    error = StructuredOutputError("bad")
    error.__cause__ = ModelTransportError(kind)
    return error


UNCITED = ExtractionOutput(
    changes=[_change(name="Ghost", system="Ghost", quote="A ghost ledger reconciles money")]
)


@pytest.mark.parametrize("first", [StructuredOutputError("bad"), UNCITED])
def test_a_rejected_answer_is_asked_for_again_and_the_second_kept(first: Any) -> None:
    """The reported failure: one bad answer for a one-call document failed it outright."""
    client = _Recording([first, ExtractionOutput(changes=[_change()])])

    proposal = _extractor(client, budget=None).propose(_document(1))

    assert len(client.prompts) == 2
    assert client.prompts[0] == client.prompts[1]
    assert [change.content.name for change in proposal.changes] == ["Order Hub"]
    assert proposal.warnings == ()


def test_a_failure_asking_again_cannot_fix_is_not_retried() -> None:
    client = _Recording([_failure("authentication")] * 2)

    with pytest.raises(CatalogueAnswerUnusableError) as raised:
        _extractor(client, budget=None).propose(_document(1))

    assert len(client.prompts) == 1
    assert describe_public_error(raised.value).code == "model_authentication"


@pytest.mark.parametrize(
    ("answers", "error", "code"),
    [
        ([_failure("invalid_output")] * 2, CatalogueAnswerUnusableError, "model_invalid_output"),
        # A part's reason is its last attempt's.
        ([UNCITED, _failure("timeout")], CatalogueAnswerUnusableError, "model_timeout"),
        ([_failure("timeout"), UNCITED], CatalogueCitationError, "catalogue_extraction_uncited"),
        (
            [StructuredOutputError("bad")] * 2,
            CatalogueAnswerUnusableError,
            "catalogue_extraction_unusable",
        ),
        ([UNCITED, UNCITED], CatalogueCitationError, "catalogue_extraction_uncited"),
    ],
)
def test_total_failure_says_why_no_part_could_be_read(
    answers: list[Any], error: type[Exception], code: str
) -> None:
    with pytest.raises(error, match="No part of the document could be read") as raised:
        _extractor(_Recording(answers), budget=None).propose(_document(1))

    assert describe_public_error(raised.value).code == code


def test_a_configured_profiles_transport_failure_is_asked_for_again() -> None:
    """Profiles raise ModelTransportError itself; it once skipped the retry and failed the run."""
    client = _Recording(
        [ModelTransportError("invalid_output"), ExtractionOutput(changes=[_change()])]
    )

    proposal = _extractor(client, budget=None).propose(_document(1))

    assert len(client.prompts) == 2
    assert [change.content.name for change in proposal.changes] == ["Order Hub"]

    refused = _Recording([ModelTransportError("authentication")] * 2)
    with pytest.raises(CatalogueAnswerUnusableError) as raised:
        _extractor(refused, budget=None).propose(_document(1))
    assert len(refused.prompts) == 1
    assert describe_public_error(raised.value).code == "model_authentication"


def _cut_off() -> StructuredOutputError:
    error = StructuredOutputError("The answer was truncated.")
    error.__cause__ = OutputTruncatedError()
    return error


def _cited(number: int) -> ChangeOutput:
    return _change(evidence_numbers=[number])


def _paragraphs(prompt: str) -> list[str]:
    user = prompt[prompt.index('{"document_title"') :]
    return [item["location"] for item in json.loads(user)["segments"]]


def test_a_cut_off_answer_splits_its_part_and_asks_for_each_half() -> None:
    """The reported failure: one call's answer ran out of tokens and the whole part was lost."""
    client = _Recording(
        [
            _cut_off(),
            ExtractionOutput(changes=[_cited(1)]),
            ExtractionOutput(changes=[_cited(1)]),
        ]
    )

    proposal = _extractor(client, budget=None).propose(_document(2))

    # A cut-off answer is not asked for again whole: it would be cut off again.
    assert [_paragraphs(prompt) for prompt in client.prompts[1:]] == [
        ["paragraph 1"],
        ["paragraph 2"],
    ]
    assert [change.locations for change in proposal.changes] == [
        ("paragraph 1",),
        ("paragraph 2",),
    ]
    assert proposal.warnings == ()


def test_a_full_answer_is_set_aside_and_each_half_read_on_its_own() -> None:
    full = ExtractionOutput(changes=[_cited(1) for _ in range(10)])
    client = _Recording(
        [full, ExtractionOutput(changes=[_cited(1)]), ExtractionOutput(changes=[_cited(1)])]
    )

    # A 1,000-token answer holds the minimum of ten suggestions.
    proposal = _extractor(client, budget=None, output=1000).propose(_document(2))

    assert len(client.prompts) == 3
    # The full answer's ten are not kept alongside its halves' answers.
    assert len(proposal.changes) == 2


def test_splitting_stops_and_says_a_part_may_be_incomplete() -> None:
    always_full = ExtractionOutput(changes=[_cited(1) for _ in range(10)])
    client = _Recording([always_full] * 200)
    proposal = _extractor(client, budget=None, output=1000).propose(_document(2))

    # Two levels of halving reach single passages too short to split again.
    assert len(client.prompts) <= 3 * 1 + 4
    assert proposal.changes
    assert any("may not be read completely" in warning for warning in proposal.warnings)


def test_a_passage_too_dense_for_any_answer_fails_with_the_reason() -> None:
    client = _Recording([_cut_off()] * 10)

    with pytest.raises(CatalogueAnswerUnusableError, match="too long"):
        _extractor(client, budget=None).propose(
            ExtractionRequest("Doc", (ExtractionSegment(1, "line 4", "System: A | B"),), ())
        )
    assert len(client.prompts) == 1


def test_each_call_covers_only_as_much_text_as_its_answer_can_hold() -> None:
    roomy, short = _Recording(), _Recording()

    _extractor(roomy, budget=None).propose(_document(9))
    _extractor(short, budget=None, output=2048).propose(_document(9))

    assert len(roomy.prompts) == 1
    assert len(short.prompts) >= 3
    assert all(len(_paragraphs(prompt)) <= 3 for prompt in short.prompts)


def _sectioned(*sections: tuple[str, int]) -> ExtractionRequest:
    """Paragraphs under headings: one (heading, count) pair per section."""
    segments = [
        ExtractionSegment(0, f"paragraph {heading} {n}", PARAGRAPH, section=("Landscape", heading))
        for heading, count in sections
        for n in range(1, count + 1)
    ]
    return ExtractionRequest(
        "Landscape",
        tuple(replace(item, number=number) for number, item in enumerate(segments, 1)),
        (),
    )


def _sent(prompt: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = json.loads(prompt[prompt.index('{"document_title"') :])[
        "segments"
    ]
    return segments


def test_each_passage_tells_the_model_which_section_it_belongs_to() -> None:
    client = _Recording()

    _extractor(client, budget=None).propose(_sectioned(("Customer", 1)))

    assert _sent(client.prompts[0])[0]["section"] == "Landscape › Customer"
    # A passage under no heading sends no section, so other documents read as before.
    plain = _Recording()
    _extractor(plain, budget=None).propose(_document(1))
    assert "section" not in _sent(plain.prompts[0])[0]


def test_a_call_past_half_full_ends_where_a_new_section_starts() -> None:
    # Six paragraphs fit one 8,192-character call; the second section starts a new one.
    client = _Recording()

    _extractor(client, budget=None, output=8192).propose(
        _sectioned(("Ordering", 6), ("Billing", 3))
    )

    assert [{item["section"] for item in _sent(prompt)} for prompt in client.prompts] == [
        {"Landscape › Ordering"},
        {"Landscape › Billing"},
    ]


def test_a_full_part_is_split_where_its_sections_meet() -> None:
    full = ExtractionOutput(changes=[_cited(1) for _ in range(10)])
    client = _Recording([full])

    _extractor(client, budget=None, output=1000).propose(
        _sectioned(("Ordering", 1), ("Billing", 1))
    )

    assert [[item["section"] for item in _sent(prompt)] for prompt in client.prompts[1:]] == [
        ["Landscape › Ordering"],
        ["Landscape › Billing"],
    ]


def test_paraphrased_quotes_are_backed_by_the_real_sentence_and_inventions_dropped() -> None:
    client = _Recording(
        [
            ExtractionOutput(
                changes=[
                    _change(quote="Order Hub service validates partner orders against BCRM"),
                    _change(name="Ghost", system="Ghost", quote="A ghost ledger reconciles money"),
                ]
            )
        ]
    )

    proposal = _extractor(client, budget=None).propose(_document(1))

    assert len(proposal.changes) == 1
    assert proposal.changes[0].quote.startswith("The Order Hub service receives partner orders")
    assert "1 suggestion(s) were left out" in proposal.warnings[-1]


def test_a_model_too_small_to_read_is_refused_with_how_to_fix_it() -> None:
    with pytest.raises(
        CatalogueExtractionUnsupportedError, match="LOCAL_LLM_CONTEXT_WINDOW_TOKENS"
    ):
        _extractor(_Recording(), budget=900).propose(_document(1))


def test_a_huge_catalogue_is_trimmed_so_the_document_still_fits() -> None:
    known = tuple(
        KnownSystem(f"system-{n}", f"System number {n}", (f"alias {n}", f"other {n}"))
        for n in range(400)
    )
    client = _Recording()

    proposal = _extractor(client).propose(replace(_document(2), known_systems=known))

    assert all(len(prompt) // 4 < 4096 for prompt in client.prompts)
    assert any("catalogue systems were shown to the model" in w for w in proposal.warnings)


def test_reading_stops_when_the_checkpoint_says_the_document_left_the_draft() -> None:
    calls: list[int] = []

    def checkpoint() -> None:
        calls.append(1)
        if len(calls) > 1:
            raise KnowledgeConflictError("This document is no longer part of the draft.")

    client = _Recording()
    with pytest.raises(KnowledgeConflictError):
        _extractor(client).propose(replace(_document(40), checkpoint=checkpoint))
    assert len(client.prompts) == 1


def test_the_reported_local_setup_now_reads_a_long_word_document() -> None:
    """The real local client, with its default 8,192-token window, behind a stub server."""
    seen: list[int] = []

    def server(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(sum(len(message["content"]) for message in body["messages"]) // 4)
        answer = {"changes": [_change().model_dump()]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer)}}]})

    client = LocalStructuredOutputClient(
        base_url="http://model.test/v1/",
        http_client=httpx.Client(transport=httpx.MockTransport(server)),
        model="smb-qwen3-vl:8b",
        timeout_seconds=30,
        reasoning_effort=None,
        context_window_tokens=8192,
        max_output_tokens=4096,
    )

    # Without the budget, one oversized prompt is refused before it reaches the model:
    # the "AI answer could not be used" failure that was reported.
    with pytest.raises(CatalogueExtractionError):
        _extractor(client, budget=None).propose(_document(40))
    assert seen == []

    proposal = _extractor(client, budget=8192 - 4096).propose(_document(40))

    # The first version sent one ~7,000-token prompt, which this client refuses.
    assert len(seen) >= 3
    assert all(tokens < 8192 - 4096 for tokens in seen)
    assert proposal.changes


def test_asking_again_for_an_exhausted_job_starts_it_afresh() -> None:
    jobs = InMemoryArchitectureJobs()
    job = jobs.enqueue(
        ArchitectureJob(
            "j1",
            ArchitectureJobKind.EXTRACTION,
            "draft",
            "doc|m",
            "amina",
            ArchitectureJobStatus.QUEUED,
        )
    )
    moment = NOW
    for _ in range(3):
        # Each attempt stalls past its lease, as a crashed worker would.
        assert jobs.claim(moment) is not None
        moment += timedelta(minutes=10)
    assert jobs.claim(moment) is None
    assert (jobs.get("j1") or job).error_category == "attempts_exhausted"

    again = jobs.enqueue(replace(job, id="j2"))

    assert (again.id, again.status, again.attempts) == ("j1", ArchitectureJobStatus.QUEUED, 0)
    assert jobs.claim(moment) is not None


def test_reading_status_is_listed_per_document_and_retry_runs(client: TestClient) -> None:
    draft = client.post(
        "/architecture-knowledge/releases", json={"name": "Next version"}, headers=OWNER
    ).json()
    uploaded = client.post(
        f"/architecture-knowledge/releases/{draft['id']}/documents",
        data={"title": "Design", "language": "en", "expected_revision": draft["revision"]},
        files={"file": ("design.txt", b"System: Order Hub\n", "text/plain")},
        headers=OWNER,
    ).json()
    base = f"/architecture-knowledge/releases/{draft['id']}"
    version_id = uploaded["documents"][-1]["id"]
    assert client.get(f"{base}/extractions", headers=OWNER).json() == []

    started = client.post(f"{base}/documents/{version_id}/extractions", headers=OWNER).json()
    listed = client.get(f"{base}/extractions", headers=OWNER).json()

    assert listed == [{"document_version_id": version_id, "job": started}]
    assert started["status"] == "succeeded"
    reader = {"X-Fake-Actor-Id": "fake-reviewer"}
    assert client.get(f"{base}/extractions", headers=reader).status_code == 403
