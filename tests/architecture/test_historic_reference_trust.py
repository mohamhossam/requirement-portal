"""The historic corpus is reference knowledge only (Knowledge Center E2, ADR-0102).

Nothing that screens, suggests, answers or searches for live requirement work may read
it, and the live corpus's kinds never gain historic values. Prior art reaches a reader
only through its own read, labelled historic.
"""

from __future__ import annotations

import inspect
import typing

from smb_requirement_agent.application.ports import historic_corpus, prior_art
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    GetKnowledgeReview,
    RequirementKnowledgeCorpus,
    ScreenRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
)
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeRelationshipKind,
    KnowledgeSourceKind,
)

HISTORIC_MODULES = (historic_corpus.__name__, prior_art.__name__)


def _constructor_types(cls: type) -> set[str]:
    hints = typing.get_type_hints(vars(cls)["__init__"])
    modules: set[str] = set()
    for annotation in hints.values():
        for candidate in (annotation, *typing.get_args(annotation)):
            module = getattr(candidate, "__module__", "")
            modules.add(module)
    return modules


def test_live_knowledge_work_never_reads_the_historic_corpus() -> None:
    for live in (
        ScreenRequirementKnowledge,
        SuggestClarificationAnswers,
        RequirementKnowledgeCorpus,
        UnifiedKnowledgeSearch,
        GetKnowledgeReview,
    ):
        assert inspect.isclass(live)
        assert not _constructor_types(live) & set(HISTORIC_MODULES), live.__name__


def test_the_live_corpus_kinds_gain_no_historic_values() -> None:
    assert not any("historic" in kind.value for kind in KnowledgeSourceKind)
    assert "similar_past_requirement" not in {kind.value for kind in KnowledgeRelationshipKind}
