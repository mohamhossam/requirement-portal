"""Requirement-knowledge screening and grounded-answer behavior."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

import pytest

from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSeverity,
    IntentProposalStatus,
    KnownFact,
    QuestionId,
)
from smb_requirement_agent.application.errors import KnowledgeGenerationError
from smb_requirement_agent.application.ports.requirement_knowledge import (
    AnswerSuggestionCandidate,
    KnowledgeReview,
    KnowledgeScreenEnsureOutcome,
    RelationshipCandidate,
)
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
    ScreenRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    RequirementWorklistQuery,
)
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestionSource,
    KnowledgeChunk,
    KnowledgeFindingStatus,
    KnowledgeMatch,
    KnowledgeRelationshipKind,
    KnowledgeSourceKind,
)
from smb_requirement_agent.domain.knowledge.errors import (
    InvalidKnowledgeError,
    KnowledgeFindingConflictError,
)
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
    FakeKnowledgeEmbedding,
)
from smb_requirement_agent.infrastructure.persistence.requirement_knowledge_repository import (
    InMemoryRequirementKnowledgeStore,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.jobs.domain.entities import AiJobFailure
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.errors import (
    DuplicateRequirementStateError,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.access_service import access_service_for
from tests.unit.workflow_helpers import drain_requirement_index


def _create(
    container: Container,
    title: str,
    description: str,
    *,
    actor_index: int = 0,
) -> Requirement:
    return container.create_requirement.execute(
        CreateRequirementInput(title=title, description=description),
        FAKE_ACTORS[actor_index],
    )


def _screen(container: Container, requirement_id: RequirementId) -> KnowledgeReview:
    fingerprint = container.get_knowledge_review.execute(requirement_id).current_fingerprint
    access = container.access_repository.get_requirement(requirement_id)
    assert access is not None and access.owner is not None
    actor = container.actor_directory.get(access.owner.actor.id)
    assert actor is not None
    drain_requirement_index(container)
    return container.screen_requirement_knowledge.execute(actor, requirement_id, fingerprint)


def test_creation_schedules_one_idempotent_automatic_screen(container: Container) -> None:
    requirement = _create(container, "Fibre ordering", "Customers order fibre online.")

    container.knowledge_scheduler.schedule(requirement.id)

    jobs = [
        record.job
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation.value == "screen_requirement_knowledge"
    ]
    assert len(jobs) == 1
    assert jobs[0].origin.value == "automatic"


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled", "succeeded"])
def test_terminal_attempt_requires_manual_retry_for_the_same_screen(
    container: Container,
    terminal_status: str,
) -> None:
    requirement = _create(container, "Fibre ordering", "Customers order fibre online.")
    first = next(
        record.job
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation.value == "screen_requirement_knowledge"
    )
    running = first.claim(container.clock.now())
    if terminal_status == "failed":
        terminal = running.fail(
            AiJobFailure("provider_failed", "Provider unavailable.", True, "test-correlation-id"),
            container.clock.now(),
        )
    elif terminal_status == "cancelled":
        terminal = running.cancel(container.clock.now())
    else:
        terminal = running.succeed((), container.clock.now())
    container.ai_job_repository.save(running)
    container.ai_job_repository.save(terminal)

    result = container.knowledge_scheduler.ensure(requirement.id)

    jobs = [
        record.job
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation.value == "screen_requirement_knowledge"
    ]
    assert len(jobs) == 1
    assert result.outcome is KnowledgeScreenEnsureOutcome.MANUAL_RETRY_REQUIRED
    assert result.job_id == first.id


def test_current_screen_is_not_rescheduled(container: Container) -> None:
    requirement = _create(container, "Current", "This Requirement has a current screen.")
    _screen(container, requirement.id)

    result = container.knowledge_scheduler.ensure(requirement.id)

    assert result.outcome is KnowledgeScreenEnsureOutcome.CURRENT
    assert result.job_id is None


def test_analysis_and_intent_decisions_schedule_new_fingerprinted_screens(
    container: Container,
) -> None:
    requirement = _create(container, "Launch", "Launch a business broadband bundle.")
    workspace = container.analyze_requirement.execute_workspace(FAKE_ACTORS[0], requirement.id)
    proposal = workspace.analysis.intent_proposals[0]
    container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        proposal.id,
        IntentProposalStatus.ACCEPTED,
        proposal.version,
        FAKE_ACTORS[0],
    )

    jobs = [
        record.job
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation.value == "screen_requirement_knowledge"
    ]
    assert len(jobs) == 3
    assert len({job.command_fingerprint for job in jobs}) == 3


def test_analysis_and_human_questions_schedule_idempotent_automatic_suggestions(
    container: Container,
) -> None:
    requirement = _create(container, "Launch", "Launch a business broadband bundle.")
    workspace = container.analyze_requirement.execute_workspace(FAKE_ACTORS[0], requirement.id)

    suggestion_jobs = [
        record.job
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
        if record.job.operation.value == "suggest_clarification_answers"
    ]
    assert len(suggestion_jobs) == len(workspace.questions)
    assert all(job.origin.value == "automatic" for job in suggestion_jobs)

    container.answer_suggestion_scheduler.schedule(requirement.id, workspace.questions)
    assert len(
        [
            record
            for record in container.ai_job_repository.list_for_requirement(requirement.id)
            if record.job.operation.value == "suggest_clarification_answers"
        ]
    ) == len(workspace.questions)

    for record in container.ai_job_repository.list_for_requirement(requirement.id):
        if record.job.operation.value == "suggest_clarification_answers":
            running = record.job.claim(container.clock.now())
            container.ai_job_repository.save(running)
            container.ai_job_repository.save(running.succeed((), container.clock.now()))
    reanalyzed = container.analyze_requirement.execute_workspace(
        FAKE_ACTORS[0], requirement.id, force=True
    )
    assert {item.id for item in reanalyzed.questions} == {item.id for item in workspace.questions}
    assert (
        len(
            [
                record
                for record in container.ai_job_repository.list_for_requirement(requirement.id)
                if record.job.operation.value == "suggest_clarification_answers"
            ]
        )
        == len(workspace.questions) * 2
    )

    first = reanalyzed.questions[0]
    assert reanalyzed.analysis.id is not None
    replacement = first.replacement(
        QuestionId("replacement-question"),
        reanalyzed.analysis.id,
        ClarificationKind.OPEN_QUESTION,
        "Which team approves launch readiness?",
        "The previous wording was ambiguous.",
    )
    container.answer_suggestion_scheduler.schedule(requirement.id, (replacement,))
    assert any(
        record.command.arguments.get("question_id") == replacement.id.value
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
    )

    question = container.analysis_collaboration.ask(
        requirement.id,
        subject="Who approves launch readiness?",
        rationale="The accountable owner is not stated.",
        assignee_id=None,
        severity=ClarificationSeverity.MEDIUM,
        is_blocker=False,
        expected_analysis_version=reanalyzed.analysis.version,
        actor=FAKE_ACTORS[0],
    )
    assert any(
        record.command.arguments.get("question_id") == question.id.value
        and record.job.origin.value == "automatic"
        for record in container.ai_job_repository.list_for_requirement(requirement.id)
    )


def test_current_analysis_suggestion_evidence_excludes_uncertainty(
    container: Container,
) -> None:
    requirement = _create(container, "Launch", "Launch a business broadband bundle.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    chunks = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    ).current_analysis_chunks(requirement)

    assert chunks
    assert {item.field for item in chunks} <= {"known_fact", "business_rule", "constraint"}
    assert {item.source_kind for item in chunks} == {KnowledgeSourceKind.CURRENT_ANALYSIS}


def test_hybrid_index_fuses_lexical_and_semantic_ranks(container: Container) -> None:
    canonical = _create(
        container,
        "XGPON ordering",
        "Customers order XGPON bundles through BCRM.",
    )
    unrelated = _create(container, "Invoices", "Finance archives monthly invoices.")
    subject = _create(container, "Channel", "Order XGPON bundles through BCRM.")
    corpus = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )
    embeddings = FakeKnowledgeEmbedding()
    corpus.sync_index(container.knowledge_index, embeddings)
    query = corpus.subject_text(subject.id)
    matches = container.knowledge_index.search(query, embeddings.embed((query,))[0], subject.id, 20)

    assert matches[0].chunk.requirement_id == canonical.id
    assert matches[0].lexical_rank is not None
    assert matches[0].semantic_rank is not None
    assert any(item.chunk.requirement_id == unrelated.id for item in matches)


def test_trusted_corpus_excludes_unconfirmed_ai_content(container: Container) -> None:
    requirement = _create(container, "Bundle", "Offer the bundle through the digital channel.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    candidate_chunks = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    ).chunks(requirement)

    assert {item.source_kind for item in candidate_chunks} == {KnowledgeSourceKind.SOURCE}


def test_duplicate_screen_is_advisory_until_owner_closes_requirement(
    container: Container,
) -> None:
    canonical = _create(
        container,
        "XGPON bundles",
        "Business customers order XGPON bundles through BCRM and CPP channels.",
    )
    candidate = _create(
        container,
        "XGPON bundles",
        "Business customers order XGPON bundles through BCRM and CPP channels.",
    )

    review = _screen(container, candidate.id)

    assert review.ready is False
    finding = next(item for item in review.findings if item.related_requirement_id == canonical.id)
    assert finding.kind is KnowledgeRelationshipKind.POSSIBLE_DUPLICATE
    updated = container.decide_knowledge_finding.execute(
        candidate.id,
        finding.id,
        "duplicate",
        finding.version,
        FAKE_ACTORS[0],
    )
    assert updated.status is KnowledgeFindingStatus.DUPLICATE
    closed = container.requirement_repository.get(candidate.id)
    assert closed is not None
    assert closed.status is RequirementStatus.DUPLICATE
    assert closed.duplicate_of_requirement_id == canonical.id
    worklist = container.list_requirement_worklist.execute(RequirementWorklistQuery(limit=100))
    duplicate_item = next(
        item for item in worklist.requirements if item.snapshot.requirement.id == candidate.id
    )
    assert duplicate_item.workflow_status.value == "duplicate"
    with pytest.raises(DuplicateRequirementStateError):
        container.analyze_requirement.execute(FAKE_ACTORS[0], candidate.id)


def test_distinct_decision_requires_rationale_and_clears_current_finding(
    container: Container,
) -> None:
    _create(container, "Mobile bundle", "Customers order the mobile bundle online.")
    candidate = _create(container, "Mobile bundle", "Customers order the mobile bundle online.")
    finding = _screen(container, candidate.id).findings[0]

    with pytest.raises(InvalidKnowledgeError, match="must not be blank"):
        container.decide_knowledge_finding.execute(
            candidate.id, finding.id, "distinct", finding.version, FAKE_ACTORS[0], "  "
        )
    decided = container.decide_knowledge_finding.execute(
        candidate.id,
        finding.id,
        "distinct",
        finding.version,
        FAKE_ACTORS[0],
        "This requirement is limited to a separate customer segment.",
    )

    assert decided.status is KnowledgeFindingStatus.DISTINCT
    assert container.get_knowledge_review.execute(candidate.id).ready is True
    assert any(
        event.action.value == "requirement_marked_distinct" and event.requirement_id == candidate.id
        for event in container.activity_reader.list_events()
    )


def test_contradiction_requires_both_current_owners_and_resolution_is_immutable(
    container: Container,
) -> None:
    canonical = _create(
        container,
        "Paper billing",
        "Business customers can request paper billing through BCRM.",
        actor_index=0,
    )
    candidate = _create(
        container,
        "Paper billing",
        "Business customers cannot request paper billing through BCRM.",
        actor_index=1,
    )
    finding = next(
        item
        for item in _screen(container, candidate.id).findings
        if item.related_requirement_id == canonical.id
    )
    assert finding.kind is KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION
    _screen(container, canonical.id)
    assert len(container.knowledge_repository.list_related_findings(candidate.id)) == 1

    proposed = container.decide_knowledge_finding.execute(
        candidate.id,
        finding.id,
        "propose_resolution",
        finding.version,
        FAKE_ACTORS[1],
        "Paper billing is allowed only for migrated contracts.",
    )
    first = container.decide_knowledge_finding.execute(
        canonical.id,
        finding.id,
        "accept_resolution",
        proposed.version,
        FAKE_ACTORS[0],
    )
    assert first.status is KnowledgeFindingStatus.RESOLUTION_PENDING
    container.requirement_access.transfer_requirement(
        canonical.id,
        FAKE_ACTORS[0],
        ActorId("fake-observer"),
        container.access_repository.get_requirement(canonical.id).version,  # type: ignore[union-attr]
    )
    after_transfer = container.decide_knowledge_finding.execute(
        candidate.id,
        finding.id,
        "accept_resolution",
        first.version,
        FAKE_ACTORS[1],
    )
    assert after_transfer.status is KnowledgeFindingStatus.RESOLUTION_PENDING
    assert ActorId("fake-owner") not in after_transfer.resolution_approvals
    resolved = container.decide_knowledge_finding.execute(
        canonical.id,
        finding.id,
        "accept_resolution",
        after_transfer.version,
        FAKE_ACTORS[2],
    )
    assert resolved.status is KnowledgeFindingStatus.RESOLVED
    with pytest.raises(KnowledgeFindingConflictError):
        resolved.propose_resolution(
            FAKE_ACTORS[0], "Change it again", container.clock.now(), resolved.version
        )


def test_linked_source_change_makes_a_finding_stale_and_schedules_both_sides(
    container: Container,
) -> None:
    canonical = _create(container, "Eligibility", "Only registered businesses are eligible.")
    candidate = _create(container, "Eligibility", "Only registered businesses are eligible.")
    review = _screen(container, candidate.id)
    assert review.current

    changed = canonical.update(
        RequirementTitle("Eligibility"),
        RequirementDescription("Only incorporated businesses are eligible."),
        updated_at=container.clock.now(),
    )
    container.requirement_repository.save(changed)
    container.knowledge_scheduler.schedule(canonical.id)

    assert container.get_knowledge_review.execute(candidate.id).current is False
    affected = {
        record.job.requirement_id
        for requirement_id in (canonical.id, candidate.id)
        for record in container.ai_job_repository.list_for_requirement(requirement_id)
        if record.job.operation.value == "screen_requirement_knowledge"
    }
    assert affected == {canonical.id, candidate.id}
    candidate_job = next(
        record
        for record in container.ai_job_repository.list_for_requirement(candidate.id)
        if record.command.arguments.get("trigger_requirement_id") == canonical.id.value
    )
    assert candidate_job.command.arguments["trigger_requirement_version"] == changed.version.value


def test_suggestions_are_grounded_and_record_optional_human_influence(
    container: Container,
) -> None:
    _create(
        container,
        "Supported channels",
        "BCRM and CPP are the supported ordering channels for XGPON bundles.",
    )
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]

    drain_requirement_index(container)
    result = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )

    assert 1 <= len(result.suggestions) <= 3
    assert all(item.evidence for item in result.suggestions)
    assert {item.source_for(subject.id) for item in result.suggestions} == {
        AnswerSuggestionSource.CURRENT_ANALYSIS,
        AnswerSuggestionSource.TRUSTED_KNOWLEDGE,
        AnswerSuggestionSource.COMBINED,
    }
    selected = result.suggestions[0]
    assert selected.evidence[0].fingerprint
    workspace = container.analysis_collaboration.resolve(
        subject.id,
        question.id,
        f"{selected.answer} with an owner clarification.",
        question.version,
        FAKE_ACTORS[0],
        source_suggestion_id=selected.id.value,
    )
    assert any(
        item.source_suggestion_id == selected.id.value for item in workspace.analysis.clarifications
    )
    corpus = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )
    assert not any(
        c.source_kind is KnowledgeSourceKind.CLARIFICATION for c in corpus.chunks(subject)
    )
    assert any(
        c.source_kind is KnowledgeSourceKind.CLARIFICATION
        for c in corpus.chunks(subject, screening_subject=True)
    )


def test_manual_suggestion_generation_requires_requirement_membership(
    container: Container,
) -> None:
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]

    with pytest.raises(AuthorizationDeniedError):
        container.suggest_clarification_answers.execute(
            subject.id, question.id, question.version, FAKE_ACTORS[2]
        )

    with pytest.raises(AuthorizationDeniedError, match="bound worker attempt"):
        container.suggest_clarification_answers.execute_automatic(
            subject.id, question.id, question.version
        )
    drain_requirement_index(container)
    authorized = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )
    assert authorized.suggestions


def test_suggestions_hide_when_cited_knowledge_changes(container: Container) -> None:
    evidence_requirement = _create(
        container,
        "Supported channels",
        "BCRM and CPP are the supported ordering channels for XGPON bundles.",
    )
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]
    drain_requirement_index(container)
    result = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )
    assert result.suggestions

    changed = evidence_requirement.update(
        RequirementTitle("Supported channels"),
        RequirementDescription("DCRM is now the only supported ordering channel."),
        updated_at=container.clock.now(),
    )
    container.requirement_repository.save(changed)
    assert container.suggest_clarification_answers.get_current(subject.id, question.id) is None


def test_suggestions_hide_when_cited_current_analysis_changes(container: Container) -> None:
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]
    drain_requirement_index(container)
    result = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )
    assert any(
        item.source_for(subject.id) is AnswerSuggestionSource.CURRENT_ANALYSIS
        for item in result.suggestions
    )

    analysis = container.analysis_repository.get_by_requirement_id(subject.id)
    assert analysis is not None
    container.analysis_repository.save(
        replace(
            analysis,
            known_facts=(KnownFact("The analysis evidence changed."),),
            version=analysis.version + 1,
        )
    )

    assert container.suggest_clarification_answers.get_current(subject.id, question.id) is None


def test_no_supported_answer_is_a_successful_empty_suggestion_set(
    container: Container,
) -> None:
    subject = _create(container, "Standalone", "A requirement with no trusted peers.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]

    class EmptySuggester:
        model = "empty"
        prompt_version = "empty-v1"

        def suggest(
            self,
            requirement: Requirement,
            question: object,
            current_analysis: object,
            matches: object,
            references: object = (),
        ) -> tuple[AnswerSuggestionCandidate, ...]:
            del requirement, question, current_analysis, matches
            return ()

    use_case = SuggestClarificationAnswers(
        container.requirement_repository,
        container.analysis_audit_repository,
        container.access_repository,
        RequirementKnowledgeCorpus(
            container.requirement_repository,
            container.analysis_repository,
            container.analysis_audit_repository,
            container.access_repository,
            container.knowledge_repository,
            container.document_repository,
        ),
        container.knowledge_index,
        container.knowledge_repository,
        FakeKnowledgeEmbedding(),
        EmptySuggester(),
        container.clock,
        container.transaction_manager,
        references=container.current_references,
        authorization=access_service_for(
            container.requirement_repository, container.access_repository
        ),
    )

    drain_requirement_index(container)
    result = use_case.execute(subject.id, question.id, question.version, FAKE_ACTORS[0])

    assert result.suggestions == ()
    assert use_case.get_current(subject.id, question.id) == result

    analysis = container.analysis_repository.get_by_requirement_id(subject.id)
    assert analysis is not None
    container.analysis_repository.save(
        replace(
            analysis,
            known_facts=(KnownFact("Changed after the empty result."),),
            version=analysis.version + 1,
        )
    )
    assert use_case.get_current(subject.id, question.id) is None


@pytest.mark.parametrize(
    ("answer", "rationale", "citation_mode", "message"),
    [
        ("Use BCRM.", "Supported.", "unknown", "outside the supplied"),
        ("Use BCRM.", "Supported.", "missing", "outside the supplied"),
        ("Use BCRM.", "Supported.", "mixed", "outside the supplied"),
        ("Use BCRM.", "Supported.", "blank", "outside the supplied"),
        ("   ", "Supported.", "valid", "blank or duplicate"),
    ],
)
def test_invalid_suggestion_output_does_not_overwrite_the_prior_valid_set(
    container: Container,
    answer: str,
    rationale: str,
    citation_mode: str,
    message: str,
) -> None:
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]
    drain_requirement_index(container)
    prior = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )

    class InvalidSuggester:
        model = "invalid"
        prompt_version = "invalid-v2"

        def suggest(
            self,
            requirement: Requirement,
            question: object,
            current_analysis: tuple[KnowledgeChunk, ...],
            matches: tuple[KnowledgeMatch, ...],
            references: object = (),
        ) -> tuple[AnswerSuggestionCandidate, ...]:
            del requirement, question, matches
            supplied = current_analysis[0]
            supplied_id = supplied.id.value
            citations = {
                "unknown": ("not-supplied",),
                "missing": (),
                "mixed": (supplied_id, "not-supplied"),
                "blank": ("   ",),
                "valid": (supplied_id,),
            }[citation_mode]
            return (AnswerSuggestionCandidate(answer, rationale, citations),)

    use_case = SuggestClarificationAnswers(
        container.requirement_repository,
        container.analysis_audit_repository,
        container.access_repository,
        RequirementKnowledgeCorpus(
            container.requirement_repository,
            container.analysis_repository,
            container.analysis_audit_repository,
            container.access_repository,
            container.knowledge_repository,
            container.document_repository,
        ),
        container.knowledge_index,
        container.knowledge_repository,
        FakeKnowledgeEmbedding(),
        InvalidSuggester(),
        container.clock,
        container.transaction_manager,
        references=container.current_references,
        authorization=access_service_for(
            container.requirement_repository, container.access_repository
        ),
    )

    with pytest.raises(KnowledgeGenerationError, match=message):
        use_case.execute(subject.id, question.id, question.version, FAKE_ACTORS[0])

    assert (
        container.knowledge_repository.latest_suggestion_set(subject.id, question.id.value) == prior
    )


def test_stale_provider_citation_fails_without_overwriting_prior_suggestions(
    container: Container,
) -> None:
    subject = _create(container, "Confirm channels", "Prepare the XGPON bundle launch.")
    container.analyze_requirement.execute(FAKE_ACTORS[0], subject.id)
    question = container.analysis_audit_repository.list_questions(subject.id)[0]
    drain_requirement_index(container)
    prior = container.suggest_clarification_answers.execute(
        subject.id, question.id, question.version, FAKE_ACTORS[0]
    )
    stale_id = next(
        evidence.chunk_id.value
        for suggestion in prior.suggestions
        for evidence in suggestion.evidence
        if evidence.requirement_id == subject.id
    )
    analysis = container.analysis_repository.get_by_requirement_id(subject.id)
    assert analysis is not None
    container.analysis_repository.save(
        replace(
            analysis,
            known_facts=(KnownFact("Changed evidence."),),
            version=analysis.version + 1,
        )
    )

    class StaleCitationSuggester:
        model = "stale"
        prompt_version = "stale-v2"

        def suggest(
            self,
            requirement: Requirement,
            question: object,
            current_analysis: tuple[KnowledgeChunk, ...],
            matches: tuple[KnowledgeMatch, ...],
            references: object = (),
        ) -> tuple[AnswerSuggestionCandidate, ...]:
            del requirement, question, current_analysis, matches
            return (AnswerSuggestionCandidate("Use BCRM.", "Supported.", (stale_id,)),)

    use_case = SuggestClarificationAnswers(
        container.requirement_repository,
        container.analysis_audit_repository,
        container.access_repository,
        RequirementKnowledgeCorpus(
            container.requirement_repository,
            container.analysis_repository,
            container.analysis_audit_repository,
            container.access_repository,
            container.knowledge_repository,
            container.document_repository,
        ),
        container.knowledge_index,
        container.knowledge_repository,
        FakeKnowledgeEmbedding(),
        StaleCitationSuggester(),
        container.clock,
        container.transaction_manager,
        references=container.current_references,
        authorization=access_service_for(
            container.requirement_repository, container.access_repository
        ),
    )

    drain_requirement_index(container)
    with pytest.raises(KnowledgeGenerationError, match="outside the supplied"):
        use_case.execute(subject.id, question.id, question.version, FAKE_ACTORS[0])

    assert (
        container.knowledge_repository.latest_suggestion_set(subject.id, question.id.value) == prior
    )


def test_unknown_classifier_citation_and_wrong_embedding_dimension_fail_atomically(
    container: Container,
) -> None:
    _create(container, "Canonical", "Customers order through BCRM.")
    subject = _create(container, "Candidate", "Customers order through BCRM.")
    corpus = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )

    class InvalidClassifier:
        model = "invalid"
        prompt_version = "invalid-v1"

        def classify(
            self,
            requirement: Requirement,
            subject_text: str,
            matches: tuple[KnowledgeMatch, ...],
            references: object = (),
        ) -> tuple[RelationshipCandidate, ...]:
            del requirement, subject_text, matches
            return (
                RelationshipCandidate(
                    subject.id,
                    KnowledgeRelationshipKind.POSSIBLE_DUPLICATE,
                    "Unsupported citation",
                    ("not-supplied",),
                ),
            )

    use_case = ScreenRequirementKnowledge(
        container.requirement_repository,
        corpus,
        container.knowledge_index,
        container.knowledge_repository,
        FakeKnowledgeEmbedding(),
        InvalidClassifier(),
        container.clock,
        container.transaction_manager,
        authorization=access_service_for(
            container.requirement_repository, container.access_repository
        ),
    )
    drain_requirement_index(container)
    with pytest.raises(KnowledgeGenerationError, match="outside the supplied"):
        use_case.execute(FAKE_ACTORS[0], subject.id, corpus.fingerprint(subject.id))
    assert container.knowledge_repository.current_screen(subject.id) is None

    store = InMemoryRequirementKnowledgeStore(RLock())
    chunk = corpus.chunks(subject)[0]
    with pytest.raises(KnowledgeGenerationError, match="768"):
        store.replace(subject.id, "fingerprint", (chunk,), ((0.0,),))
