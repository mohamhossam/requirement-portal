"""The breakdown review rules (ADR-0017, ADR-0021, ADR-0103 §4).

`BreakdownReviewPolicy` turns review evidence into flags, risks and recommendations;
`ApprovalPolicy` decides which open items block final approval. Both are deterministic;
`tests/characterisation/golden/review_policy_build.json` pins the review policy's output.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from smb_requirement_agent.analysis.domain.value_objects import ClarificationKind
from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.story.quality import (
    InvestAssessment,
    spidr_recommendations,
)
from smb_requirement_agent.governance.domain.review.entities import (
    BreakdownReview,
    Dependency,
    DependencyEvidenceKind,
    DependencyId,
    Flag,
    FlagCategory,
    FlagId,
    FlagSeverity,
    FlagStatus,
    Recommendation,
    RecommendationId,
    ResolutionPolicy,
    ReviewSource,
    ReviewSourceKind,
    Risk,
    RiskId,
)
from smb_requirement_agent.governance.domain.review.evidence import (
    ReviewEvidence,
    evidence_fingerprint,
)

# Bumped whenever the rules below change, so saved reviews are rebuilt.
REVIEW_RULESET_VERSION = "breakdown-review-v3"


class BreakdownReviewPolicy:
    """Map existing evidence into a versioned set of governance concerns."""

    def build(
        self,
        evidence: ReviewEvidence,
        assessments: tuple[InvestAssessment, ...],
        generated_at: datetime,
    ) -> BreakdownReview:
        dependencies: list[Dependency] = []
        risks: list[Risk] = []
        flags: list[Flag] = []
        recommendations: list[Recommendation] = []
        for proposal_id in evidence.stale_reference_proposal_ids:
            flags.append(
                _flag(
                    "withdrawn-reference",
                    proposal_id,
                    FlagCategory.STALENESS,
                    FlagSeverity.BLOCKING,
                    "Reference evidence changed",
                    "A cited publication was withdrawn or replaced. "
                    "Review source impact and revise the affected content or record why "
                    "its historical evidence still applies.",
                    ReviewSource(ReviewSourceKind.ANALYSIS, proposal_id, "Reference applicability"),
                    ResolutionPolicy.SOURCE_ACTION,
                )
            )
        for question in evidence.questions:
            source = ReviewSource(
                ReviewSourceKind.ANALYSIS,
                question.id.value,
                question.subject,
            )
            category = {
                ClarificationKind.OPEN_QUESTION: FlagCategory.OPEN_QUESTION,
                ClarificationKind.ASSUMPTION: FlagCategory.ASSUMPTION,
                ClarificationKind.AMBIGUITY: FlagCategory.AMBIGUITY,
                ClarificationKind.POTENTIAL_DEPENDENCY: FlagCategory.DEPENDENCY,
            }[question.kind]
            flags.append(
                _flag(
                    "clarification-question",
                    question.id.value,
                    category,
                    (FlagSeverity.BLOCKING if question.is_blocker else FlagSeverity.WARNING),
                    "Clarification question",
                    (
                        f"{question.subject} — {question.rationale}"
                        if question.rationale
                        else question.subject
                    ),
                    source,
                    (
                        ResolutionPolicy.CLARIFICATION
                        if question.kind is ClarificationKind.OPEN_QUESTION
                        else ResolutionPolicy.SOURCE_ACTION
                    ),
                )
            )
            if question.kind is ClarificationKind.POTENTIAL_DEPENDENCY:
                dependencies.append(
                    Dependency(
                        DependencyId(_stable_id("dependency-potential", question.id.value)),
                        question.subject,
                        source,
                        DependencyEvidenceKind.POTENTIAL,
                    )
                )

        if evidence.epic is not None and evidence.epic.is_stale:
            self._add_staleness(evidence.epic.id.value, "Epic", ReviewSourceKind.EPIC, risks, flags)

        stories_by_feature = {
            feature.id.value: tuple(
                story for story in evidence.stories if story.feature_id == feature.id
            )
            for feature in evidence.features
        }
        for feature in evidence.features:
            source = ReviewSource(
                ReviewSourceKind.FEATURE,
                feature.id.value,
                feature.name.value,
            )
            if feature.is_stale:
                self._add_staleness(
                    feature.id.value,
                    feature.name.value,
                    ReviewSourceKind.FEATURE,
                    risks,
                    flags,
                )
            self._add_architecture(feature.architecture, source, dependencies, flags)
            if feature.architecture is None:
                recommendations.append(
                    _recommendation(
                        "map-architecture",
                        feature.id.value,
                        "Map architecture",
                        "Map this Feature before governance review so system impact is visible.",
                        source,
                    )
                )
            elif feature.architecture.cross_system:
                description = (
                    f"{feature.name.value} spans {len(feature.architecture.systems)} systems and "
                    "may require cross-team coordination."
                )
                risks.append(
                    Risk(
                        RiskId(_stable_id("risk-cross-system", feature.id.value, description)),
                        FlagSeverity.WARNING,
                        description,
                        source,
                    )
                )
                flags.append(
                    _flag(
                        "cross-system",
                        description,
                        FlagCategory.ARCHITECTURE,
                        FlagSeverity.WARNING,
                        "Cross-system Feature",
                        description,
                        source,
                        ResolutionPolicy.DECISION,
                    )
                )
                recommendations.append(
                    _recommendation(
                        "split-by-component",
                        feature.id.value,
                        "Review a component-based split",
                        "A Feature spanning multiple systems is a strong candidate for a "
                        "component boundary split.",
                        source,
                    )
                )

            for story in stories_by_feature[feature.id.value]:
                story_source = ReviewSource(
                    ReviewSourceKind.STORY,
                    story.id.value,
                    story.voice,
                )
                if story.is_stale:
                    self._add_staleness(
                        story.id.value,
                        story.voice,
                        ReviewSourceKind.STORY,
                        risks,
                        flags,
                    )
                self._add_architecture(story.architecture, story_source, dependencies, flags)
                if story.architecture is None:
                    recommendations.append(
                        _recommendation(
                            "map-architecture",
                            story.id.value,
                            "Map architecture",
                            "Map this Story before governance review so system impact is visible.",
                            story_source,
                        )
                    )

        assessment_by_story = {item.story_id.value: item for item in assessments}
        for story in evidence.stories:
            assessment = assessment_by_story.get(story.id.value)
            if assessment is None:
                flags.append(
                    _flag(
                        "quality-unevaluated",
                        story.id.value,
                        FlagCategory.QUALITY,
                        FlagSeverity.BLOCKING,
                        "Story quality not evaluated",
                        "Run quality assessment for the current Story set before approval.",
                        ReviewSource(ReviewSourceKind.STORY, story.id.value, story.voice),
                        ResolutionPolicy.SOURCE_ACTION,
                    )
                )
                continue
            if assessment.failure_count == 0:
                continue
            source = ReviewSource(ReviewSourceKind.STORY, story.id.value, story.voice)
            severity = (
                FlagSeverity.BLOCKING if assessment.failure_count >= 2 else FlagSeverity.WARNING
            )
            failed = ", ".join(
                item.criterion.value for item in assessment.findings if not item.passed
            )
            description = (
                f"Story fails {assessment.failure_count} INVEST "
                f"criterion{'s' if assessment.failure_count != 1 else ''}: {failed}."
            )
            risks.append(
                Risk(
                    RiskId(_stable_id("risk-quality", story.id.value, description)),
                    severity,
                    description,
                    source,
                )
            )
            flags.append(
                _flag(
                    "story-quality",
                    description,
                    FlagCategory.QUALITY,
                    severity,
                    "Story quality needs attention",
                    description,
                    source,
                    ResolutionPolicy.DECISION,
                )
            )
            for suggestion in spidr_recommendations(assessment):
                recommendations.append(
                    _recommendation(
                        f"spidr-{suggestion.pattern.value}",
                        story.id.value,
                        f"Consider a {suggestion.pattern.value} split",
                        suggestion.reason,
                        source,
                    )
                )

        return BreakdownReview(
            requirement_id=evidence.requirement.id,
            generated_at=generated_at,
            ruleset_version=REVIEW_RULESET_VERSION,
            evidence_fingerprint=evidence_fingerprint(evidence),
            dependencies=tuple(dependencies),
            risks=tuple(risks),
            flags=tuple(flags),
            recommendations=tuple(recommendations),
            quality_assessments=assessments,
        )

    @staticmethod
    def _add_staleness(
        item_id: str,
        label: str,
        kind: ReviewSourceKind,
        risks: list[Risk],
        flags: list[Flag],
    ) -> None:
        source = ReviewSource(kind, item_id, label)
        description = f"{label} is stale and must be reconciled with its source."
        risks.append(
            Risk(
                RiskId(_stable_id("risk-stale", item_id, description)),
                FlagSeverity.BLOCKING,
                description,
                source,
            )
        )
        flags.append(
            _flag(
                "stale",
                description,
                FlagCategory.STALENESS,
                FlagSeverity.BLOCKING,
                "Stale generated content",
                description,
                source,
                ResolutionPolicy.SOURCE_ACTION,
            )
        )

    @staticmethod
    def _add_architecture(
        impact: ArchitectureImpact | None,
        source: ReviewSource,
        dependencies: list[Dependency],
        flags: list[Flag],
    ) -> None:
        if impact is None:
            flags.append(
                _flag(
                    "architecture-unmapped",
                    source.item_id,
                    FlagCategory.ARCHITECTURE,
                    FlagSeverity.WARNING,
                    "Architecture mapping required",
                    "No architecture mapping has been recorded for this item.",
                    source,
                    ResolutionPolicy.SOURCE_ACTION,
                )
            )
            return
        names = {item.id: item.name for item in impact.systems}
        for item in impact.dependencies:
            description = (
                f"{names[item.source_system_id]} → {names[item.target_system_id]}: "
                f"{item.description}"
            )
            dependencies.append(
                Dependency(
                    DependencyId(_stable_id("dependency-catalogued", source.item_id, description)),
                    description,
                    source,
                    DependencyEvidenceKind.CATALOGUED,
                )
            )
            flags.append(
                _flag(
                    "architecture-dependency",
                    description,
                    FlagCategory.DEPENDENCY,
                    FlagSeverity.WARNING,
                    "Architecture dependency",
                    description,
                    source,
                    ResolutionPolicy.DECISION,
                )
            )


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return digest


def _flag(
    code: str,
    evidence: str,
    category: FlagCategory,
    severity: FlagSeverity,
    title: str,
    detail: str,
    source: ReviewSource,
    resolution_policy: ResolutionPolicy,
) -> Flag:
    return Flag(
        FlagId(_stable_id("flag", code, source.kind.value, source.item_id, evidence)),
        category,
        severity,
        title,
        detail,
        source,
        resolution_policy,
    )


def _recommendation(
    code: str,
    evidence: str,
    action: str,
    rationale: str,
    source: ReviewSource,
) -> Recommendation:
    return Recommendation(
        RecommendationId(_stable_id("recommendation", code, source.item_id, evidence)),
        action,
        rationale,
        source,
    )


@dataclass(frozen=True)
class ApprovalPolicy:
    """The confirmed strict policy: every open blocker prevents final approval."""

    name: str = "strict-all-blockers-v1"

    def blocking_reasons(
        self, review: BreakdownReview, *, active_blocking_questions: int
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        review_blockers = sum(
            item.status is FlagStatus.OPEN and item.severity is FlagSeverity.BLOCKING
            for item in review.flags
        )
        if review_blockers:
            reasons.append(f"{review_blockers} blocking review flag(s) remain open.")
        if active_blocking_questions:
            reasons.append(
                f"{active_blocking_questions} blocking clarification question(s) remain open."
            )
        return tuple(reasons)
