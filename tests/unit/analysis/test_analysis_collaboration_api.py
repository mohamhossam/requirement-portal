"""Slice 8B collaborative clarification and immutable-round API behavior."""

from collections.abc import Callable, Sequence
from typing import Any

from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    QuestionReviewCandidate,
    RequirementAnalysisCandidate,
    RequirementAnalyzerPort,
    UncertaintyCandidate,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    HumanClarification,
    IntentProposal,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.analysis.infrastructure.llm.fake_requirement_analyzer import (
    FakeRequirementAnalyzer,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS, TEST_NOW
from tests.unit.workflow_helpers import post_analysis, screen_current_knowledge

OWNER = {"X-Fake-Actor-Id": "fake-owner"}
REVIEWER = {"X-Fake-Actor-Id": "fake-reviewer"}
OBSERVER = {"X-Fake-Actor-Id": "fake-observer"}


class FailSecondAnalysis(RequirementAnalyzerPort):
    def __init__(self) -> None:
        self.calls = 0
        self.fake = FakeRequirementAnalyzer()

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        self.calls += 1
        if self.calls > 1:
            raise RequirementAnalysisGenerationError("Provider failed during re-analysis.")
        return self.fake.analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )


class CountingAnalysis(RequirementAnalyzerPort):
    def __init__(self) -> None:
        self.calls = 0
        self.fake = FakeRequirementAnalyzer()

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        self.calls += 1
        return self.fake.analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )


class MutatingSecondAnalysis(CountingAnalysis):
    def __init__(self) -> None:
        super().__init__()
        self.before_second_return: Callable[[], None] | None = None

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        candidate = super().analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )
        if self.calls == 2 and self.before_second_return is not None:
            self.before_second_return()
        return candidate


class ReconciliationAnalysis(CountingAnalysis):
    """Return every v4 reconciliation action on the second analysis call."""

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        candidate = super().analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )
        if self.calls != 2:
            return candidate
        ai_questions = [
            item for item in active_questions if item["source"] is ClarificationSource.AI
        ]
        retained, retired, replaced = ai_questions
        replacement = UncertaintyCandidate(
            kind=ClarificationKind.OPEN_QUESTION,
            subject="Which external service must be available?",
            rationale="The dependency gap remains but needs a decision-focused question.",
        )
        created = UncertaintyCandidate(
            kind=ClarificationKind.AMBIGUITY,
            subject="Who approves launch readiness?",
            rationale="The confirmed context introduces an unclear approval owner.",
        )
        candidate["question_reviews"] = [
            QuestionReviewCandidate(
                question_id=retained["question_id"],
                action=QuestionChangeAction.RETAINED,
                rationale="This gap remains unchanged.",
                replacement=None,
            ),
            QuestionReviewCandidate(
                question_id=retired["question_id"],
                action=QuestionChangeAction.RETIRED,
                rationale="The submitted answer also resolves this gap.",
                replacement=None,
            ),
            QuestionReviewCandidate(
                question_id=replaced["question_id"],
                action=QuestionChangeAction.REPLACED,
                rationale="The dependency must now be expressed as a focused question.",
                replacement=replacement,
            ),
        ]
        candidate["new_uncertainties"] = [created]
        candidate["assumptions"] = []
        candidate["open_questions"] = [
            {"question": retained["subject"], "rationale": retained["rationale"] or "Needed"},
            {"question": replacement["subject"], "rationale": replacement["rationale"] or "Needed"},
        ]
        candidate["ambiguities"] = [
            {"statement": created["subject"], "reason": created["rationale"] or "Needed"}
        ]
        candidate["potential_dependencies"] = []
        return candidate


class HumanEvidenceAnalysis(CountingAnalysis):
    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        candidate = super().analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )
        if clarifications:
            fact = clarifications[-1].answer
            candidate["known_facts"].append(fact)
            candidate["clarification_references"] = {
                "known_fact:" + fact.casefold(): [len(clarifications)]
            }
        return candidate


def test_batch_resolution_retains_human_evidence_in_current_analysis_and_saved_round() -> None:
    from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
        analysis_from_payload,
        analysis_to_payload,
    )

    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=HumanEvidenceAnalysis())
    fact = "DEL serves single-user lines; PABX serves multi-user plans."
    expected = [{"evidence_key": "known_fact:" + fact.casefold(), "clarification_numbers": [1]}]
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, first = _analysed(isolated)
        question = first["questions"][0]
        response = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            headers=OWNER,
            json={
                "answers": [
                    {
                        "question_id": question["id"],
                        "answer": fact,
                        "expected_version": question["version"],
                    }
                ]
            },
        )
        assert response.status_code == 200
        assert response.json()["clarification_evidence"] == expected
        assert response.json()["clarifications"][0]["question_id"] == question["id"]
        assert response.json()["clarifications"][0]["answered_by"]["id"] == "fake-owner"
        assert response.json()["known_facts"][-1]["evidence_references"] == []
        rounds = isolated.get(
            f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER
        ).json()
        assert rounds[0]["analysis"]["clarification_evidence"] == []
        assert rounds[1]["analysis"]["clarification_evidence"] == expected
        value = container.get_requirement_analysis.execute(RequirementId(requirement_id))
        assert analysis_from_payload(analysis_to_payload(value)) == value
        legacy = analysis_to_payload(value)
        del legacy["clarification_evidence"]
        assert analysis_from_payload(legacy).clarification_evidence == ()


class MissingReviewAnalysis(CountingAnalysis):
    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        candidate = super().analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )
        if self.calls == 2:
            candidate["question_reviews"] = candidate["question_reviews"][:-1]
        return candidate


def _analysed(client: TestClient) -> tuple[str, dict[str, Any]]:
    created = client.post(
        "/requirements",
        json={"title": "Collaborative analysis", "description": "Audit every answer"},
        headers=OWNER,
    )
    requirement_id = created.json()["id"]
    response = post_analysis(client, requirement_id, headers=OWNER)
    assert response.status_code == 200
    return requirement_id, response.json()


def test_generated_analysis_has_identity_provenance_and_stable_forced_questions(
    client: TestClient,
) -> None:
    requirement_id, first = _analysed(client)
    first_questions = {item["id"]: item for item in first["questions"]}

    assert first["analysis_id"]
    assert first["round_number"] == 1
    assert first["source_requirement_version"] == 1
    assert first["provenance"]["model"] == "fake-analysis"
    assert first["provenance"]["prompt_version"] == "fake-analysis-v4"
    assert {item["action"] for item in first["question_changes"]} == {"created"}
    assert len(first_questions) == 4
    assert all(item["severity"] == "medium" for item in first_questions.values())
    assert all(item["is_blocker"] for item in first_questions.values())

    question = next(iter(first_questions.values()))
    draft = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/draft",
        json={"answer": "A partial answer", "expected_version": question["version"]},
        headers=OWNER,
    )
    assert draft.status_code == 200
    assert draft.json()["status"] == "in_progress"

    blocked = post_analysis(client, requirement_id, headers=OWNER)
    assert blocked.status_code == 409
    forced = post_analysis(client, requirement_id, force=True, headers=OWNER)
    assert forced.status_code == 200
    assert forced.json()["round_number"] == 2
    assert {item["action"] for item in forced.json()["question_changes"]} == {"retained"}
    retained = {item["id"]: item for item in forced.json()["questions"]}
    assert retained[question["id"]]["draft_answer"] == "A partial answer"

    rounds = client.get(f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER)
    assert [item["analysis"]["round_number"] for item in rounds.json()] == [1, 2]


def test_reviewer_can_save_and_resolve_assigned_answer_into_a_new_round(
    client: TestClient,
) -> None:
    requirement_id, analysis = _analysed(client)
    access = client.get(f"/requirements/{requirement_id}/assignments", headers=OWNER).json()
    assigned = client.put(
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": access["version"]},
        headers=OWNER,
    )
    assert assigned.status_code == 200
    question = next(item for item in analysis["questions"] if item["kind"] == "open_question")
    assignment = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/assignment",
        json={"assignee_id": "fake-reviewer", "expected_version": question["version"]},
        headers=OWNER,
    )
    assert assignment.status_code == 200
    assigned_question = assignment.json()
    assert assigned_question["assignee"]["id"] == "fake-reviewer"
    assert assigned_question["assignment_history"][0]["changed_by"]["id"] == "fake-owner"

    draft = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/draft",
        json={
            "answer": "Customer Operations",
            "expected_version": assigned_question["version"],
        },
        headers=REVIEWER,
    )
    assert draft.status_code == 200
    assert draft.json()["draft_updated_by"]["id"] == "fake-reviewer"

    resolved = client.post(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/resolution",
        json={"answer": None, "expected_version": draft.json()["version"]},
        headers=REVIEWER,
    )
    assert resolved.status_code == 200
    assert resolved.json()["round_number"] == 2
    clarification = resolved.json()["clarifications"][0]
    assert clarification["question_id"] == question["id"]
    assert clarification["answered_by"]["id"] == "fake-reviewer"

    historical = client.get(
        f"/requirements/{requirement_id}/analysis/rounds/{analysis['analysis_id']}",
        headers=OWNER,
    )
    assert historical.status_code == 200
    old_question = next(
        item for item in historical.json()["questions"] if item["id"] == question["id"]
    )
    assert old_question["status"] == "resolved"
    assert old_question["answer"] == "Customer Operations"


def test_owner_resolves_an_answered_subset_in_one_analysis_round() -> None:
    analyzer = CountingAnalysis()
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=analyzer)
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, analysis = _analysed(isolated)
        selected = analysis["questions"][:2]

        resolved = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            json={
                "answers": [
                    {
                        "question_id": item["id"],
                        "answer": f"Confirmed answer {index}",
                        "expected_version": item["version"],
                    }
                    for index, item in enumerate(selected, start=1)
                ]
            },
            headers=OWNER,
        )

        assert resolved.status_code == 200
        assert analyzer.calls == 2
        assert resolved.json()["round_number"] == 2
        assert {item["question_id"] for item in resolved.json()["clarifications"]} == {
            item["id"] for item in selected
        }
        assert {item["id"] for item in resolved.json()["questions"]} == {
            item["id"] for item in analysis["questions"][2:]
        }
        rounds = isolated.get(f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER)
        assert len(rounds.json()) == 2
        activity = isolated.get("/activity", headers=OWNER).json()["items"]
        resolved_events = [item for item in activity if item["action"] == "question_resolved"]
        assert {item["target_id"] for item in resolved_events} == {item["id"] for item in selected}


def test_reanalysis_reconciles_ai_questions_and_protects_human_questions() -> None:
    analyzer = ReconciliationAnalysis()
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=analyzer)
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, first = _analysed(isolated)
        selected, retained, retired, replaced = first["questions"]
        access = isolated.get(f"/requirements/{requirement_id}/assignments", headers=OWNER).json()
        isolated.put(
            f"/requirements/{requirement_id}/reviewers/fake-reviewer",
            json={"expected_version": access["version"]},
            headers=OWNER,
        )
        assigned = isolated.put(
            f"/requirements/{requirement_id}/analysis/questions/{replaced['id']}/assignment",
            json={
                "assignee_id": "fake-reviewer",
                "expected_version": replaced["version"],
            },
            headers=OWNER,
        ).json()
        drafted = isolated.put(
            f"/requirements/{requirement_id}/analysis/questions/{replaced['id']}/draft",
            json={
                "answer": "Unconfirmed dependency note",
                "expected_version": assigned["version"],
            },
            headers=REVIEWER,
        ).json()
        human = isolated.post(
            f"/requirements/{requirement_id}/analysis/questions",
            json={
                "subject": "Should the team preserve this question?",
                "expected_analysis_version": first["version"],
            },
            headers=OWNER,
        ).json()

        response = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            json={
                "answers": [
                    {
                        "question_id": selected["id"],
                        "answer": "This answer resolves several related gaps.",
                        "expected_version": selected["version"],
                    }
                ]
            },
            headers=OWNER,
        )

        assert response.status_code == 200
        assert analyzer.calls == 2
        current = response.json()
        assert current["round_number"] == 2
        assert {item["action"] for item in current["question_changes"]} == {
            "retained",
            "retired",
            "replaced",
            "created",
        }
        active_by_id = {item["id"]: item for item in current["questions"]}
        assert retained["id"] in active_by_id
        assert retired["id"] not in active_by_id
        assert replaced["id"] not in active_by_id
        assert human["id"] in active_by_id
        replacement_change = next(
            item for item in current["question_changes"] if item["action"] == "replaced"
        )
        replacement = active_by_id[replacement_change["replacement_question_id"]]
        assert replacement["replaces_question_id"] == replaced["id"]
        assert replacement["assignee"]["id"] == "fake-reviewer"
        assert replacement["severity"] == replaced["severity"]
        assert replacement["is_blocker"] is replaced["is_blocker"]
        assert replacement["draft_answer"] is None

        rounds = isolated.get(
            f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER
        ).json()
        latest_questions = {item["id"]: item for item in rounds[-1]["questions"]}
        archived = latest_questions[replaced["id"]]
        assert archived["status"] == "superseded"
        assert archived["draft_answer"] == drafted["draft_answer"]
        assert rounds[-1]["analysis"]["question_changes"] == current["question_changes"]
        assert all(item["question_id"] != human["id"] for item in current["question_changes"])

        events = isolated.get("/activity", headers=OWNER).json()["items"]
        superseded = [item for item in events if item["action"] == "question_superseded"]
        assert {item["target_id"] for item in superseded} == {
            retired["id"],
            replaced["id"],
        }


def test_incomplete_reconciliation_rolls_back_every_submitted_answer() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=MissingReviewAnalysis())
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, first = _analysed(isolated)
        selected = first["questions"][0]

        failed = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            json={
                "answers": [
                    {
                        "question_id": selected["id"],
                        "answer": "Confirmed answer",
                        "expected_version": selected["version"],
                    }
                ]
            },
            headers=OWNER,
        )

        assert failed.status_code == 502
        current = isolated.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
        assert current["analysis_id"] == first["analysis_id"]
        assert current["clarifications"] == []
        assert {item["status"] for item in current["questions"]} == {"open"}
        assert (
            len(
                isolated.get(
                    f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER
                ).json()
            )
            == 1
        )


def test_batch_resolution_rejects_duplicates_stale_and_missing_questions(
    client: TestClient,
) -> None:
    requirement_id, analysis = _analysed(client)
    question = analysis["questions"][0]
    path = f"/requirements/{requirement_id}/analysis/question-resolutions"
    answer = {
        "question_id": question["id"],
        "answer": "Confirmed answer",
        "expected_version": question["version"],
    }

    duplicate = client.post(path, json={"answers": [answer, answer]}, headers=OWNER)
    stale = client.post(
        path,
        json={"answers": [{**answer, "expected_version": question["version"] + 1}]},
        headers=OWNER,
    )
    missing = client.post(
        path,
        json={
            "answers": [
                {
                    "question_id": "missing-question",
                    "answer": "Confirmed answer",
                    "expected_version": 1,
                }
            ]
        },
        headers=OWNER,
    )
    blank = client.post(
        path,
        json={"answers": [{**answer, "answer": "   "}]},
        headers=OWNER,
    )

    assert duplicate.status_code == 422
    assert stale.status_code == 409
    assert missing.status_code == 404
    assert blank.status_code == 422
    current = client.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
    assert current["analysis_id"] == analysis["analysis_id"]
    assert current["clarifications"] == []


def test_reviewer_batch_is_atomic_when_one_question_is_not_assigned(
    client: TestClient,
) -> None:
    requirement_id, analysis = _analysed(client)
    access = client.get(f"/requirements/{requirement_id}/assignments", headers=OWNER).json()
    client.put(
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": access["version"]},
        headers=OWNER,
    )
    assigned = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{analysis['questions'][0]['id']}/assignment",
        json={
            "assignee_id": "fake-reviewer",
            "expected_version": analysis["questions"][0]["version"],
        },
        headers=OWNER,
    ).json()
    unassigned = analysis["questions"][1]

    denied = client.post(
        f"/requirements/{requirement_id}/analysis/question-resolutions",
        json={
            "answers": [
                {
                    "question_id": assigned["id"],
                    "answer": "Reviewer answer",
                    "expected_version": assigned["version"],
                },
                {
                    "question_id": unassigned["id"],
                    "answer": "Unauthorized answer",
                    "expected_version": unassigned["version"],
                },
            ]
        },
        headers=REVIEWER,
    )

    assert denied.status_code == 403
    current = client.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
    assert current["analysis_id"] == analysis["analysis_id"]
    assert current["clarifications"] == []


def test_batch_rechecks_every_question_after_analysis_generation() -> None:
    analyzer = MutatingSecondAnalysis()
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=analyzer)
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, analysis = _analysed(isolated)
        selected = analysis["questions"][:2]
        requirement_key = RequirementId(requirement_id)
        changed_id = QuestionId(analysis["questions"][2]["id"])
        changed = container.analysis_audit_repository.get_question(requirement_key, changed_id)
        assert changed is not None
        analyzer.before_second_return = lambda: container.analysis_audit_repository.save_question(
            changed.save_draft(
                "A concurrent draft",
                FAKE_ACTORS[0],
                TEST_NOW,
                changed.version,
            )
        )

        conflict = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            json={
                "answers": [
                    {
                        "question_id": item["id"],
                        "answer": f"Batch answer {index}",
                        "expected_version": item["version"],
                    }
                    for index, item in enumerate(selected, start=1)
                ]
            },
            headers=OWNER,
        )

        assert conflict.status_code == 409
        current = isolated.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
        assert current["analysis_id"] == analysis["analysis_id"]
        assert current["clarifications"] == []
        concurrent = next(item for item in current["questions"] if item["id"] == changed_id.value)
        assert concurrent["draft_answer"] == "A concurrent draft"
        rounds = isolated.get(f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER)
        assert len(rounds.json()) == 1


def test_question_authorization_versioning_and_nonblocking_confirmation(
    client: TestClient,
) -> None:
    requirement_id, analysis = _analysed(client)
    question = analysis["questions"][0]

    forbidden = client.post(
        f"/requirements/{requirement_id}/analysis/questions",
        json={
            "subject": "Observer question",
            "severity": "medium",
            "is_blocker": False,
            "expected_analysis_version": analysis["version"],
        },
        headers=OBSERVER,
    )
    assert forbidden.status_code == 403
    invalid_target = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/assignment",
        json={"assignee_id": "fake-observer", "expected_version": question["version"]},
        headers=OWNER,
    )
    assert invalid_target.status_code == 403

    for current in analysis["questions"]:
        response = client.patch(
            f"/requirements/{requirement_id}/analysis/questions/{current['id']}",
            json={
                "severity": "low",
                "is_blocker": False,
                "expected_version": current["version"],
            },
            headers=OWNER,
        )
        assert response.status_code == 200
        assert response.json()["classification_changed_by"]["id"] == "fake-owner"

    stale = client.patch(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}",
        json={"severity": "high", "is_blocker": True, "expected_version": 1},
        headers=OWNER,
    )
    assert stale.status_code == 409
    for proposal in analysis["business_intent"]["proposals"]:
        decided = client.patch(
            f"/requirements/{requirement_id}/analysis/proposals/{proposal['id']}",
            json={"decision": "accepted", "expected_version": proposal["version"]},
            headers=OWNER,
        )
        assert decided.status_code == 200
    screen_current_knowledge(client, requirement_id)
    current_analysis = client.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
    confirmed = client.post(
        f"/requirements/{requirement_id}/analysis/confirmation",
        json={"expected_version": current_analysis["version"]},
        headers=OWNER,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["human_confirmed"] is True
    confirmed_proposal = confirmed.json()["business_intent"]["proposals"][0]
    immutable = client.patch(
        f"/requirements/{requirement_id}/analysis/proposals/{confirmed_proposal['id']}",
        json={
            "decision": "rejected",
            "expected_version": confirmed_proposal["version"],
        },
        headers=OWNER,
    )
    assert immutable.status_code == 409
    activity = client.get("/activity", headers=OWNER)
    assert activity.status_code == 200
    assert "intent_proposal_decided" in {item["action"] for item in activity.json()["items"]}
    worklist = client.get("/requirements", headers=OWNER).json()["requirements"]
    item = next(entry for entry in worklist if entry["id"] == requirement_id)
    assert item["unresolved_items"] == len(analysis["questions"])
    assert item["workflow_status"] == "ready_for_review"
    assert item["next_action"] == "generate_epic"


def test_human_question_defaults_nonblocking_and_can_be_assigned(client: TestClient) -> None:
    requirement_id, analysis = _analysed(client)
    access = client.get(f"/requirements/{requirement_id}/assignments", headers=OWNER).json()
    client.put(
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": access["version"]},
        headers=OWNER,
    )

    response = client.post(
        f"/requirements/{requirement_id}/analysis/questions",
        json={
            "subject": "Who validates the launch date?",
            "assignee_id": "fake-reviewer",
            "expected_analysis_version": analysis["version"],
        },
        headers=OWNER,
    )

    assert response.status_code == 201
    assert response.json()["source"] == "human"
    assert response.json()["severity"] == "medium"
    assert response.json()["is_blocker"] is False
    assert response.json()["asked_by"]["id"] == "fake-owner"
    assert response.json()["assignee"]["id"] == "fake-reviewer"
    stale = client.post(
        f"/requirements/{requirement_id}/analysis/questions",
        json={
            "subject": "This was composed from an old analysis view",
            "expected_analysis_version": analysis["version"],
        },
        headers=OWNER,
    )
    assert stale.status_code == 409
    blank = client.post(
        f"/requirements/{requirement_id}/analysis/questions",
        json={
            "subject": "   ",
            "expected_analysis_version": analysis["version"] + 1,
        },
        headers=OWNER,
    )
    assert blank.status_code == 422


def test_source_edit_supersedes_questions_without_erasing_audit_history(
    client: TestClient,
) -> None:
    requirement_id, first = _analysed(client)
    original_ids = {item["id"] for item in first["questions"]}

    updated = client.put(
        f"/requirements/{requirement_id}",
        json={
            "title": "Changed collaborative analysis",
            "description": "Changed source text",
            "expected_version": 1,
            "impact_acknowledged": True,
        },
        headers=OWNER,
    )
    assert updated.status_code == 200
    assert client.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).status_code == 404

    history = client.get(f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER)
    assert history.status_code == 200
    assert {item["status"] for item in history.json()[0]["questions"]} == {"superseded"}

    regenerated = post_analysis(client, requirement_id, headers=OWNER)
    assert regenerated.status_code == 200
    assert regenerated.json()["round_number"] == 2
    assert original_ids.isdisjoint({item["id"] for item in regenerated.json()["questions"]})


def test_removing_reviewer_clears_assignment_but_preserves_draft_and_history(
    client: TestClient,
) -> None:
    requirement_id, analysis = _analysed(client)
    access = client.get(f"/requirements/{requirement_id}/assignments", headers=OWNER).json()
    assigned_access = client.put(
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": access["version"]},
        headers=OWNER,
    ).json()
    question = analysis["questions"][0]
    assigned = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/assignment",
        json={"assignee_id": "fake-reviewer", "expected_version": question["version"]},
        headers=OWNER,
    ).json()
    drafted = client.put(
        f"/requirements/{requirement_id}/analysis/questions/{question['id']}/draft",
        json={"answer": "Keep this work", "expected_version": assigned["version"]},
        headers=REVIEWER,
    ).json()

    removed = client.request(
        "DELETE",
        f"/requirements/{requirement_id}/reviewers/fake-reviewer",
        json={"expected_version": assigned_access["version"]},
        headers=OWNER,
    )
    assert removed.status_code == 200
    current = client.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
    retained = next(item for item in current["questions"] if item["id"] == question["id"])
    assert retained["assignee"] is None
    assert retained["draft_answer"] == "Keep this work"
    assert retained["version"] == drafted["version"] + 1
    assert [item["assignee"] for item in retained["assignment_history"]] == [
        assigned["assignee"],
        None,
    ]


def test_provider_failure_leaves_draft_current_analysis_and_rounds_unchanged() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=FailSecondAnalysis())
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, analysis = _analysed(isolated)
        question = analysis["questions"][0]
        draft = isolated.put(
            f"/requirements/{requirement_id}/analysis/questions/{question['id']}/draft",
            json={"answer": "Do not lose me", "expected_version": question["version"]},
            headers=OWNER,
        ).json()

        failed = isolated.post(
            f"/requirements/{requirement_id}/analysis/questions/{question['id']}/resolution",
            json={"answer": None, "expected_version": draft["version"]},
            headers=OWNER,
        )
        assert failed.status_code == 502
        current = isolated.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
        retained = next(item for item in current["questions"] if item["id"] == question["id"])
        assert current["analysis_id"] == analysis["analysis_id"]
        assert retained["draft_answer"] == "Do not lose me"
        assert retained["status"] == "in_progress"
        assert (
            len(
                isolated.get(
                    f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER
                ).json()
            )
            == 1
        )


def test_provider_failure_leaves_every_batch_question_unresolved() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS, analyzer=FailSecondAnalysis())
    with TestClient(create_app(lambda: container)) as isolated:
        requirement_id, analysis = _analysed(isolated)
        selected = analysis["questions"][:2]

        failed = isolated.post(
            f"/requirements/{requirement_id}/analysis/question-resolutions",
            json={
                "answers": [
                    {
                        "question_id": item["id"],
                        "answer": f"Retain answer {index}",
                        "expected_version": item["version"],
                    }
                    for index, item in enumerate(selected, start=1)
                ]
            },
            headers=OWNER,
        )

        assert failed.status_code == 502
        current = isolated.get(f"/requirements/{requirement_id}/analysis", headers=OWNER).json()
        assert current["analysis_id"] == analysis["analysis_id"]
        assert current["clarifications"] == []
        assert {item["status"] for item in current["questions"]} == {"open"}
        rounds = isolated.get(f"/requirements/{requirement_id}/analysis/rounds", headers=OWNER)
        assert len(rounds.json()) == 1
