"""Every operation that calls an AI provider counts against the caller's rate limit.

A provider-calling route without the limit is an unmetered path to provider
spend. The expected set is explicit, so adding such a route is a visible
decision in this file, as with the public probes in test_route_authentication.

"Calls a provider" includes scheduling automatic work that will: a created
Requirement queues a knowledge screen, which embeds and classifies. So the
routes that trigger automatic jobs are limited too, and a reachability check
over the dependency graph finds any new route that can reach a provider port
or a job scheduler without the limit.
"""

import importlib
import inspect
import pkgutil
import typing
from collections.abc import Iterator

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

import smb_requirement_agent as root_package
from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceAnalysisPort,
    ReferenceProposerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalyzerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    RequirementEvidenceAnalyzerPort,
)
from smb_requirement_agent.breakdown.application.ports.epic_generator import EpicGeneratorPort
from smb_requirement_agent.breakdown.application.ports.feature_generator import FeatureGeneratorPort
from smb_requirement_agent.breakdown.application.ports.story_generator import StoryGeneratorPort
from smb_requirement_agent.breakdown.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.dependencies import limit_provider_calls
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.api.schemas.generation import GenerationRequest
from smb_requirement_agent.knowledge.application.ports.prior_art import (
    PriorArtJudgePort,
    PriorArtSchedulerPort,
)
from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    AnswerSuggestionSchedulerPort,
    ClarificationAnswerSuggesterPort,
    KnowledgeEmbeddingPort,
    KnowledgeScreenSchedulerPort,
    RequirementRelationshipClassifierPort,
)
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ArchitectureKnowledgePort,
)
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceKnowledgePort,
    ReferenceSearchPort,
)

PROVIDER_OPERATIONS = {
    ("POST", "/requirements/{requirement_id}/ai-jobs"),
    ("POST", "/requirements/{requirement_id}/ai-jobs/{job_id}/retry"),
    ("POST", "/requirements/{requirement_id}/analysis"),
    ("POST", "/requirements/{requirement_id}/analysis/clarifications"),
    ("POST", "/requirements/{requirement_id}/epic"),
    ("POST", "/requirements/{requirement_id}/features"),
    ("POST", "/requirements/{requirement_id}/features/{feature_id}/stories"),
    ("POST", "/requirements/{requirement_id}/features/{feature_id}/stories/regeneration"),
    (
        "POST",
        "/requirements/{requirement_id}/features/{feature_id}/stories/{story_id}/regeneration",
    ),
    ("POST", "/requirements/{requirement_id}/features/{feature_id}/stories/change-proposals"),
    ("GET", "/requirements/{requirement_id}/features/{feature_id}/stories/quality"),
    ("GET", "/requirements/{requirement_id}/features/{feature_id}/stories/{story_id}/quality"),
    (
        "GET",
        "/requirements/{requirement_id}/features/{feature_id}/stories/{story_id}/quality/split-recommendations",
    ),
    ("POST", "/requirements/{requirement_id}/breakdown-review"),
    ("POST", "/requirements/{requirement_id}/architecture-mapping"),
    ("POST", "/requirements/{requirement_id}/architecture-mapping/jobs"),
    ("POST", "/requirements/{requirement_id}/architecture-mapping/jobs/{job_id}/retry"),
    ("POST", "/requirements/{requirement_id}/knowledge-index/retry"),
    ("POST", "/knowledge/search/unified"),
}

# Routes that call no provider themselves but queue automatic work that does:
# a knowledge screen (embedding and relationship classification) or answer
# suggestions. Clarification resolution also re-analyses synchronously.
AUTOMATIC_TRIGGERS = {
    ("POST", "/requirements"),
    ("POST", "/requirements/drafts/{draft_id}/promote"),
    ("PUT", "/requirements/{requirement_id}"),
    ("POST", "/requirements/{requirement_id}/knowledge-screen/ensure"),
    ("POST", "/requirements/{requirement_id}/knowledge-findings/{finding_id}/decisions"),
    ("PATCH", "/requirements/{requirement_id}/analysis/proposals/{proposal_id}"),
    ("POST", "/requirements/{requirement_id}/analysis/questions"),
    ("POST", "/requirements/{requirement_id}/analysis/question-resolutions"),
    ("POST", "/requirements/{requirement_id}/analysis/questions/{question_id}/resolution"),
    ("POST", "/requirements/{requirement_id}/breakdown-review/open-questions/{flag_id}/resolution"),
}

# Ports whose calls reach an AI provider, and ports that queue work that will.
# The knowledge service's matching and library search run models on requirement
# work's behalf (ADR-0099), so calling them is provider spend too.
PROVIDER_PORTS: set[type] = {
    ArchitectureKnowledgePort,
    ClarificationAnswerSuggesterPort,
    EpicGeneratorPort,
    FeatureGeneratorPort,
    KnowledgeEmbeddingPort,
    ReferenceAnalysisPort,
    ReferenceKnowledgePort,
    ReferenceProposerPort,
    ReferenceSearchPort,
    RequirementAnalyzerPort,
    RequirementEvidenceAnalyzerPort,
    RequirementRelationshipClassifierPort,
    PriorArtJudgePort,
    StoryGeneratorPort,
    StoryQualityEvaluatorPort,
}
SCHEDULER_PORTS: set[type] = {
    AnswerSuggestionSchedulerPort,
    KnowledgeScreenSchedulerPort,
    PriorArtSchedulerPort,
}

# The reachability check works per class, not per method, so a route whose
# use case holds a provider port it does not call on that path is listed here
# with the reason. Anything new must be limited or explained.
NOT_PROVIDER_CALLING = {
    (
        "GET",
        "/requirements/{requirement_id}/architecture-mapping/jobs/{job_id}",
    ): "reads mapping job status",
    (
        "POST",
        "/requirements/{requirement_id}/architecture-mapping/jobs/{job_id}/cancel",
    ): "cancels a queued mapping job",
    ("GET", "/requirements/{requirement_id}/knowledge-index"): "reads index progress",
    (
        "GET",
        "/requirements/{requirement_id}/analysis/questions/{question_id}/answer-suggestions",
    ): "reads stored suggestions",
    ("GET", "/requirements/{requirement_id}/analysis"): "reads the analysis workspace",
    ("GET", "/requirements/{requirement_id}/analysis/rounds"): "reads analysis rounds",
    ("GET", "/requirements/{requirement_id}/analysis/rounds/{analysis_id}"): "reads a round",
    (
        "POST",
        "/requirements/{requirement_id}/analysis/confirmation",
    ): "confirms the current analysis",
    (
        "PATCH",
        "/requirements/{requirement_id}/analysis/questions/{question_id}",
    ): "classifies a question",
    (
        "PUT",
        "/requirements/{requirement_id}/analysis/questions/{question_id}/assignment",
    ): "assigns a question",
    (
        "PUT",
        "/requirements/{requirement_id}/analysis/questions/{question_id}/draft",
    ): "saves a draft answer",
    (
        "GET",
        "/requirements/{requirement_id}/features/{feature_id}/stories/change-proposals",
    ): "lists stored proposals",
    (
        "POST",
        "/requirements/{requirement_id}/features/{feature_id}/stories/change-proposals/{proposal_id}/application",
    ): "applies an already generated proposal",
    (
        "DELETE",
        "/requirements/{requirement_id}/features/{feature_id}/stories/change-proposals/{proposal_id}",
    ): "discards a stored proposal",
}


def _uses(dependant: Dependant, call: object) -> bool:
    return dependant.call is call or any(_uses(child, call) for child in dependant.dependencies)


def _takes_generation_request(dependant: Dependant) -> bool:
    return any(param.field_info.annotation is GenerationRequest for param in dependant.body_params)


def _operations() -> list[tuple[str, str, bool, bool]]:
    operations = []
    for context in iter_route_contexts(create_app().routes):
        if not isinstance(context.original_route, APIRoute):
            continue
        limited = _uses(context.dependant, limit_provider_calls)
        generation = _takes_generation_request(context.dependant)
        for method in sorted(context.methods or ()):
            operations.append((method, str(context.path), limited, generation))
    return operations


def test_exactly_the_provider_calling_operations_are_rate_limited() -> None:
    limited = {(method, path) for method, path, is_limited, _ in _operations() if is_limited}
    expected = PROVIDER_OPERATIONS | AUTOMATIC_TRIGGERS

    assert limited == expected, (
        f"Rate-limited but not listed: {sorted(limited - expected)}; "
        f"listed but not rate-limited: {sorted(expected - limited)}"
    )


def test_every_model_backed_mutation_is_rate_limited() -> None:
    unlimited = [
        (method, path)
        for method, path, is_limited, generation in _operations()
        if generation and not is_limited
    ]

    assert unlimited == []


def _application_namespace() -> dict[str, object]:
    """Every application class by name, to resolve TYPE_CHECKING-only annotations.

    Application code lives in `application/` and in each context's `application/` layer
    (ADR-0103), so every module under an `application` package is walked.
    """
    namespace: dict[str, object] = {}
    for module_info in pkgutil.walk_packages(root_package.__path__, f"{root_package.__name__}."):
        if "application" not in module_info.name.split("."):
            continue
        module = importlib.import_module(module_info.name)
        for name, value in vars(module).items():
            if inspect.isclass(value):
                namespace.setdefault(name, value)
    return namespace


_NAMESPACE = _application_namespace()


def _types(annotation: object) -> Iterator[object]:
    arguments = typing.get_args(annotation)
    if not arguments:
        yield annotation
    for argument in arguments:
        yield from _types(argument)


def _reaches_provider(cls: object, seen: set[type]) -> bool:
    if not isinstance(cls, type) or cls in seen:
        return False
    if cls in PROVIDER_PORTS or cls in SCHEDULER_PORTS:
        return True
    if not cls.__module__.startswith("smb_requirement_agent.") or cls is Container:
        return False
    seen.add(cls)
    constructor = next(vars(item)["__init__"] for item in cls.__mro__ if "__init__" in vars(item))
    hints = typing.get_type_hints(constructor, localns=_NAMESPACE)
    return any(
        _reaches_provider(candidate, seen)
        for name, annotation in hints.items()
        if name != "return"
        for candidate in _types(annotation)
    )


def _dependency_types(dependant: Dependant) -> Iterator[object]:
    for child in dependant.dependencies:
        if child.call is not None:
            yield from _types(typing.get_type_hints(child.call).get("return"))
        yield from _dependency_types(child)


def test_every_route_that_can_reach_provider_work_is_limited_or_explained() -> None:
    reaching: set[tuple[str, str]] = set()
    limited: set[tuple[str, str]] = set()
    for context in iter_route_contexts(create_app().routes):
        if not isinstance(context.original_route, APIRoute):
            continue
        reaches = any(
            _reaches_provider(item, set()) for item in _dependency_types(context.dependant)
        )
        for method in context.methods or ():
            if reaches:
                reaching.add((method, str(context.path)))
            if _uses(context.dependant, limit_provider_calls):
                limited.add((method, str(context.path)))

    unexplained = reaching - limited - set(NOT_PROVIDER_CALLING)
    assert not unexplained, f"Reaches provider work without the rate limit: {sorted(unexplained)}"
    stale = set(NOT_PROVIDER_CALLING) - (reaching - limited)
    assert not stale, f"Explained but no longer reaching unlimited provider work: {sorted(stale)}"
