"""Build a draft catalogue from documents: AI proposes, a maintainer decides.

Extraction reads one document of a draft, asks the configured model for
catalogue changes with citations, and stores them as undecided suggestions.
Nothing reaches the draft until a maintainer accepts a suggestion; accepting
merges it into the draft under the draft's revision check.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.catalogue_candidates import (
    CatalogueCandidateRepositoryPort,
    ExtractionRun,
)
from smb_requirement_agent.application.ports.catalogue_extractor import (
    CatalogueExtractionUnsupportedError,
    CatalogueExtractorPort,
    ExtractionRequest,
    ExtractionSegment,
    KnownSystem,
    ProposedChange,
)
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.document_extractor import DocumentExtractorPort
from smb_requirement_agent.application.ports.document_storage import DocumentStoragePort
from smb_requirement_agent.application.ports.identity import Actor, require_maintainer
from smb_requirement_agent.application.ports.located_document_extractor import (
    LocatedDocumentExtractorPort,
)
from smb_requirement_agent.application.ports.system_matcher import (
    MatchableSystem,
    MatchQuery,
    MatchSuggestion,
    SystemMatcherPort,
    SystemMatchingError,
)
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    KnowledgeNotFoundError,
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.candidates import (
    CandidateBasis,
    CandidateCitation,
    CandidateContent,
    CandidateDecisionConflictError,
    CandidateDependencyError,
    CandidateKind,
    CandidateMatch,
    CandidateNotFoundError,
    CandidateStatus,
    CatalogueCandidate,
    MatchRole,
    PossibleMatch,
    apply_candidate,
    classify,
    find_system,
    needs_one_by_one,
    open_matches,
)
from smb_requirement_agent.domain.architecture.journeys import (
    Journey,
    merge_journeys,
    same_journey,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
    RelationshipKind,
)
from smb_requirement_agent.domain.architecture.products import (
    ProductOffering,
    find_offering,
    find_offering_component,
    find_order_type,
    merge_offerings,
    same_offering,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId

IMAGE_TYPES = frozenset({"image/png", "image/jpeg"})
MAX_SEGMENTS = 1200
MAX_MATCHES_PER_NAME = 3
# Accepted in this order, so what a suggestion refers to is in the draft first.
_ORDER = (
    CandidateKind.LANDSCAPE_DOMAIN,
    CandidateKind.SYSTEM,
    CandidateKind.PLACEMENT,
    CandidateKind.COMPONENT,
    CandidateKind.CAPABILITY,
    CandidateKind.CONSTRAINT,
    CandidateKind.RELATIONSHIP,
    # Last: an offering names systems that must be in the draft first,
    CandidateKind.PRODUCT,
    # and a journey names systems and the offering it fulfils.
    CandidateKind.JOURNEY,
)

CommitFence = Callable[[], None]


@dataclass(frozen=True)
class CandidateView:
    candidate: CatalogueCandidate
    match: CandidateMatch
    # The possible matches still to decide against the draft as it is now.
    open_matches: tuple[PossibleMatch, ...] = ()
    # The draft systems its references resolve to now, by name; None when not in the draft.
    system_name: str | None = None
    target_name: str | None = None


def _view(candidate: CatalogueCandidate, release: ArchitectureKnowledge) -> CandidateView:
    source = find_system(release, candidate.content.system_id)
    target = find_system(release, candidate.content.target_system_id or "")
    return CandidateView(
        candidate,
        classify(candidate.content, release),
        open_matches(candidate, release),
        source.name if source else None,
        target.name if target else None,
    )


@dataclass(frozen=True)
class CandidateOverview:
    release: ArchitectureKnowledge
    candidates: tuple[CandidateView, ...]
    runs: tuple[ExtractionRun, ...]


@dataclass
class _Proposal:
    """Identical proposals from one document, merged; a stated one outweighs an inference."""

    citations: list[CandidateCitation]
    quote: str
    source_name: str
    target_name: str
    basis: CandidateBasis
    rationale: str | None
    # What proposed it, when not the reading's model (the table reader, ADR-0093).
    reader: tuple[str, str] | None = None


def _references(
    content: CandidateContent, proposal: _Proposal, release: ArchitectureKnowledge
) -> tuple[tuple[MatchRole, str], ...]:
    """The system names in a proposal that no draft system answers to, as written."""
    if content.kind in {
        CandidateKind.LANDSCAPE_DOMAIN,
        CandidateKind.PRODUCT,
        CandidateKind.JOURNEY,
    }:
        return ()
    if content.kind is CandidateKind.SYSTEM:
        unknown = classify(content, release) is CandidateMatch.NEW
        return ((MatchRole.SYSTEM, content.name),) if unknown else ()
    found: list[tuple[MatchRole, str]] = []
    if find_system(release, content.system_id) is None:
        found.append((MatchRole.SYSTEM, proposal.source_name or content.system_id))
    target = content.target_system_id
    if target is not None and find_system(release, target) is None:
        found.append((MatchRole.TARGET, proposal.target_name or target))
    return tuple(found)


def _canonical(
    changes: tuple[ProposedChange, ...], release: ArchitectureKnowledge
) -> tuple[ProposedChange, ...]:
    """Every proposal naming its systems by the id they will have once suggested systems exist.

    A document read in many calls names one system several ways: "CBCM / CRMGW"
    in its own row and "CRM GW" in another system's integrations. Against the
    draft with the suggested systems added, each name resolves to one id, so the
    same dependency is suggested once and never as a system linked to itself.
    """
    provisional = release
    for change in changes:
        if change.content.kind is CandidateKind.SYSTEM:
            try:
                provisional = apply_candidate(change.content, provisional)
            except (InvalidKnowledgeError, CandidateDependencyError):
                continue

    def resolved(reference: str) -> str:
        found = find_system(provisional, reference)
        return found.id if found is not None else reference

    # The draft's offerings and those suggested beside it, which a journey may name.
    offerings = (
        *release.products,
        *(item.content.product for item in changes if item.content.product is not None),
    )

    result: list[ProposedChange] = []
    for change in changes:
        content = change.content
        if content.kind is CandidateKind.LANDSCAPE_DOMAIN:
            # Its subject is a domain, not a system.
            result.append(change)
            continue
        if content.kind is CandidateKind.PRODUCT and content.product is not None:
            offering = content.product
            parts = tuple(
                replace(
                    part,
                    responsibilities=tuple(
                        replace(duty, system_id=resolved(duty.system_id))
                        for duty in part.responsibilities
                    ),
                )
                for part in offering.components
            )
            result.append(
                replace(
                    change, content=replace(content, product=replace(offering, components=parts))
                )
            )
            continue
        if content.kind is CandidateKind.JOURNEY and content.journey is not None:
            journey = _canonical_journey(content.journey, resolved, offerings)
            result.append(replace(change, content=replace(content, journey=journey)))
            continue
        target = content.target_system_id
        result.append(
            replace(
                change,
                content=replace(
                    content,
                    system_id=resolved(content.system_id),
                    target_system_id=resolved(target) if target else target,
                ),
            )
        )
    return tuple(result)


def _canonical_journey(
    journey: Journey,
    resolved: Callable[[str], str],
    offerings: tuple[ProductOffering, ...],
) -> Journey:
    """A journey naming its systems, offering, order type and components by the ids they
    will have; what is not found stays as written, for the review to show."""
    offering = find_offering(offerings, journey.product_id or "")
    order = find_order_type(offering, journey.order_type_code or "") if offering else None

    def component(reference: str) -> str:
        found = find_offering_component(offering, reference) if offering else None
        return found.id if found is not None else reference

    return replace(
        journey,
        product_id=offering.id if offering is not None else journey.product_id,
        order_type_code=order.code if order is not None else journey.order_type_code,
        activities=tuple(
            replace(
                item,
                performing_system_id=(
                    resolved(item.performing_system_id) if item.performing_system_id else None
                ),
                supporting_system_ids=tuple(
                    dict.fromkeys(resolved(name) for name in item.supporting_system_ids)
                ),
                component_ids=tuple(dict.fromkeys(component(name) for name in item.component_ids)),
            )
            for item in journey.activities
        ),
    )


def _one_journey_each(changes: tuple[ProposedChange, ...]) -> tuple[ProposedChange, ...]:
    """Every reading of one journey as one suggestion (ADR-0096).

    A journey section read in several calls, or by the table reader and the
    model, gives one journey in parts; they merge as offerings do.
    """
    result: list[ProposedChange] = []
    journeys: list[Journey | None] = []
    for change in changes:
        journey = change.content.journey
        index = next(
            (
                number
                for number, kept in enumerate(journeys)
                if journey is not None and kept is not None and same_journey(kept, journey)
            ),
            None,
        )
        first_journey = journeys[index] if index is not None else None
        if index is None or journey is None or first_journey is None:
            result.append(change)
            journeys.append(journey)
            continue
        first = result[index]
        merged = merge_journeys(first_journey, journey)
        journeys[index] = merged
        result[index] = replace(
            first,
            content=replace(first.content, journey=merged),
            locations=tuple(dict.fromkeys((*first.locations, *change.locations))),
            basis=(
                CandidateBasis.STATED
                if CandidateBasis.STATED in {first.basis, change.basis}
                else first.basis
            ),
        )
    return tuple(result)


def _one_offering_each(changes: tuple[ProposedChange, ...]) -> tuple[ProposedChange, ...]:
    """Every reading of one product offering as one suggestion (ADR-0095).

    A product section read in several calls, or by the table reader and the
    model, gives one offering in parts; they merge, the first reading's facts
    winning, with every part's citations.
    """
    result: list[ProposedChange] = []
    # Each kept change's offering, beside it, so a later reading can find and merge into it.
    offerings: list[ProductOffering | None] = []
    for change in changes:
        offering = change.content.product
        index = next(
            (
                number
                for number, kept in enumerate(offerings)
                if offering is not None and kept is not None and same_offering(kept, offering)
            ),
            None,
        )
        first_offering = offerings[index] if index is not None else None
        if index is None or offering is None or first_offering is None:
            result.append(change)
            offerings.append(offering)
            continue
        first = result[index]
        merged = merge_offerings(first_offering, offering)
        offerings[index] = merged
        result[index] = replace(
            first,
            content=replace(first.content, product=merged),
            locations=tuple(dict.fromkeys((*first.locations, *change.locations))),
            basis=(
                CandidateBasis.STATED
                if CandidateBasis.STATED in {first.basis, change.basis}
                else first.basis
            ),
        )
    return tuple(result)


def _one_way(
    proposed: dict[CandidateContent, _Proposal],
) -> tuple[dict[CandidateContent, _Proposal], int]:
    """A dependency listed from both ends as one suggestion, and how many were merged.

    An integrations column lists BCRM under CBCM and CBCM under BCRM. When
    neither says how they depend, the second is the same link read from its
    other end; connected systems are found both ways (ADR-0087). A typed
    dependency keeps its direction and is never merged.
    """
    kept: dict[CandidateContent, _Proposal] = {}
    seen: dict[tuple[str, str], CandidateContent] = {}
    merged = 0
    for content, item in proposed.items():
        if (
            content.kind is CandidateKind.RELATIONSHIP
            and content.relationship_kind is RelationshipKind.UNSPECIFIED
        ):
            source = content.system_id.casefold()
            target = (content.target_system_id or "").casefold()
            first = seen.get((target, source))
            if first is not None:
                kept[first].citations.extend(item.citations)
                if item.basis is CandidateBasis.STATED:
                    kept[first].basis, kept[first].rationale = CandidateBasis.STATED, None
                merged += 1
                continue
            seen.setdefault((source, target), content)
        kept[content] = item
    return kept, merged


def _self_dependency(content: CandidateContent) -> bool:
    """A dependency whose source and target are the same system."""
    return (
        content.kind is CandidateKind.RELATIONSHIP
        and content.system_id.casefold() == (content.target_system_id or "").casefold()
    )


def _linked(content: CandidateContent, release: ArchitectureKnowledge) -> bool:
    """The draft already has some dependency between these two systems."""
    source = find_system(release, content.system_id)
    target = find_system(release, content.target_system_id or "")
    return (
        source is not None
        and target is not None
        and any(
            item.source_system_id == source.id and item.target_system_id == target.id
            for item in release.relationships
        )
    )


def _draft(knowledge: ManageArchitectureKnowledge, release_id: str) -> ArchitectureKnowledge:
    release = knowledge.get(release_id)
    if release.status is not KnowledgeReleaseStatus.DRAFT:
        raise KnowledgeConflictError("Suggestions apply to drafts only.")
    return release


class ProposeCatalogueChanges:
    def __init__(
        self,
        knowledge: ManageArchitectureKnowledge,
        storage: DocumentStoragePort,
        located: LocatedDocumentExtractorPort,
        documents: DocumentExtractorPort,
        extractor: CatalogueExtractorPort,
        matcher: SystemMatcherPort,
        candidates: CatalogueCandidateRepositoryPort,
        clock: ClockPort,
    ) -> None:
        self._knowledge = knowledge
        self._storage = storage
        self._located = located
        self._documents = documents
        self._extractor = extractor
        self._matcher = matcher
        self._candidates = candidates
        self._clock = clock

    @property
    def profile(self) -> str:
        return f"{self._extractor.model}:{self._extractor.prompt_version}"

    def document(self, release_id: str, version_id: str, actor: Actor) -> KnowledgeDocumentVersion:
        """The draft document to read, refused up front if the model cannot read it."""
        require_maintainer(actor)
        release = _draft(self._knowledge, release_id)
        version = next((item for item in release.documents if item.id == version_id), None)
        if version is None:
            raise KnowledgeNotFoundError("This document is not part of the draft.")
        if version.mime_type in IMAGE_TYPES and not self._extractor.supports_images:
            raise CatalogueExtractionUnsupportedError(
                "The configured model cannot read images; upload the content as Word, PDF or Excel."
            )
        return version

    def execute(self, release_id: str, version_id: str, fence: CommitFence) -> ExtractionRun:
        release = _draft(self._knowledge, release_id)
        version = next((item for item in release.documents if item.id == version_id), None)
        if version is None:
            raise KnowledgeNotFoundError("This document is no longer part of the draft.")
        stored = self._storage.get(DocumentVersionId(version.storage_key))
        warnings: list[str] = []
        if version.mime_type in IMAGE_TYPES:
            image = self._documents.extract_asset(version.mime_type, stored, "image")
            segments: tuple[ExtractionSegment, ...] = (
                ExtractionSegment(1, "image", image_mime_type=version.mime_type, image=image),
            )
        else:
            located = self._located.extract(version.mime_type, stored)
            if len(located) > MAX_SEGMENTS:
                warnings.append(
                    f"Only the first {MAX_SEGMENTS} of {len(located)} passages were read."
                )
            segments = tuple(
                ExtractionSegment(
                    number,
                    item.location,
                    item.text,
                    section=item.heading_path,
                    cells=item.cells,
                )
                for number, item in enumerate(located[:MAX_SEGMENTS], start=1)
            )
        known = tuple(
            KnownSystem(
                item.id, item.name, item.aliases, tuple(part.name for part in item.components)
            )
            for item in release.systems
        )

        def still_in_draft() -> None:
            """Stop between calls once the document left the draft, freeing the worker."""
            current = self._knowledge.get(release_id)
            if current.status is not KnowledgeReleaseStatus.DRAFT or all(
                item.id != version_id for item in current.documents
            ):
                raise KnowledgeConflictError("This document is no longer part of the draft.")

        proposal = self._extractor.propose(
            ExtractionRequest(version.title, segments, known, still_in_draft)
        )
        model, prompt_version = proposal.model, proposal.prompt_version
        warnings.extend(proposal.warnings)
        proposed: dict[CandidateContent, _Proposal] = {}
        kinds: dict[CandidateContent, list[tuple[bool, RelationshipKind | None]]] = {}
        self_linked = 0
        canonical = _canonical(proposal.changes, release)
        for change in _one_journey_each(_one_offering_each(canonical)):
            if _self_dependency(change.content):
                # A table row naming one system twice is not a dependency, and
                # accepting it would fail; it is left out rather than offered.
                self_linked += 1
                continue
            citations = [CandidateCitation(location, change.quote) for location in change.locations]
            key = _identity(change.content)
            kinds.setdefault(key, []).append(
                (change.basis is CandidateBasis.STATED, change.content.relationship_kind)
            )
            current = proposed.get(key)
            if current is None:
                proposed[key] = _Proposal(
                    citations,
                    change.quote,
                    change.source_name,
                    change.target_name,
                    change.basis,
                    change.rationale,
                    change.reader,
                )
                continue
            current.citations.extend(citations)
            if change.basis is CandidateBasis.STATED:
                current.basis, current.rationale = CandidateBasis.STATED, None
        proposed, both_ways = _one_way(
            {_settled(key, kinds[key]): item for key, item in proposed.items()}
        )
        skipped = linked = 0
        kept: dict[CandidateContent, _Proposal] = {}
        for content, item in proposed.items():
            if classify(content, release) is CandidateMatch.ALREADY_PRESENT:
                skipped += 1
            elif item.basis is CandidateBasis.INFERRED and _linked(content, release):
                linked += 1
            else:
                kept[content] = item
        matches, matched = self._matches(kept, release, warnings)
        now = self._clock.now()
        candidates = [
            CatalogueCandidate(
                uuid4().hex,
                release.id,
                version.id,
                content,
                tuple(dict.fromkeys(item.citations)),
                *(item.reader or (model, prompt_version)),
                now,
                basis=item.basis,
                rationale=item.rationale,
                possible_matches=tuple(
                    PossibleMatch(role, written, match.system_id, match.reason)
                    for role, written in _references(content, item, release)
                    for match in matches.get(written.casefold(), ())
                ),
            )
            for content, item in kept.items()
        ]
        if self_linked:
            warnings.append(
                f"{self_linked} dependency suggestion(s) were left out because they linked a "
                "system to itself."
            )
        if both_ways:
            warnings.append(
                f"{both_ways} dependency suggestion(s) listed from both systems were merged "
                "into one."
            )
        if skipped:
            warnings.append(f"{skipped} suggestion(s) already in the draft were left out.")
        if linked:
            warnings.append(
                f"{linked} inferred dependency suggestion(s) were left out because the draft "
                "already links those systems."
            )
        if not proposed:
            warnings.append("No catalogue content was found in this document.")
        run = ExtractionRun(
            uuid4().hex,
            release.id,
            version.id,
            model,
            prompt_version,
            len(candidates),
            tuple(dict.fromkeys(warnings)),
            now,
            self._matcher.model if matched else None,
            self._matcher.prompt_version if matched else None,
        )
        fence()
        self._candidates.replace_proposals(run, tuple(candidates))
        return run

    def _matches(
        self,
        proposals: dict[CandidateContent, _Proposal],
        release: ArchitectureKnowledge,
        warnings: list[str],
    ) -> tuple[dict[str, tuple[MatchSuggestion, ...]], bool]:
        """Existing systems that unmatched names may mean, by name; and whether a model ran."""
        queries: dict[str, MatchQuery] = {}
        for content, item in proposals.items():
            for _, written in _references(content, item, release):
                queries.setdefault(written.casefold(), MatchQuery(written, item.quote))
        if not queries or not release.systems:
            return {}, False
        systems = tuple(
            MatchableSystem(
                system.id,
                system.name,
                system.name_ar,
                system.aliases,
                tuple(capability.name for capability in system.capabilities),
            )
            for system in release.systems
        )
        known = {system.id for system in release.systems}
        try:
            result = self._matcher.match(tuple(queries.values()), systems)
        except SystemMatchingError:
            warnings.append(
                "Similar existing systems could not be checked; names the catalogue does not "
                "know yet are suggested as new systems."
            )
            return {}, True
        warnings.extend(result.warnings)
        found: dict[str, list[MatchSuggestion]] = {}
        for suggestion in result.suggestions:
            options = found.setdefault(suggestion.written_as.casefold(), [])
            if (
                suggestion.system_id in known
                and len(options) < MAX_MATCHES_PER_NAME
                and all(option.system_id != suggestion.system_id for option in options)
            ):
                options.append(suggestion)
        return {name: tuple(options) for name, options in found.items() if options}, True


class DecideCatalogueCandidate:
    def __init__(
        self,
        knowledge: ManageArchitectureKnowledge,
        repository: ArchitectureKnowledgeRepositoryPort,
        candidates: CatalogueCandidateRepositoryPort,
    ) -> None:
        self._knowledge = knowledge
        self._repository = repository
        self._candidates = candidates

    def overview(self, release_id: str, actor: Actor) -> CandidateOverview:
        require_maintainer(actor)
        release = self._knowledge.get(release_id)
        return CandidateOverview(
            release,
            tuple(_view(item, release) for item in self._candidates.list(release_id)),
            self._candidates.runs(release_id),
        )

    def _candidate(self, release_id: str, candidate_id: str) -> CatalogueCandidate:
        candidate = self._candidates.get(candidate_id)
        if candidate is None or candidate.release_id != release_id:
            raise CandidateNotFoundError("This suggestion was not found for the draft.")
        return candidate

    def decide(
        self,
        release_id: str,
        candidate_id: str,
        expected_revision: int,
        accept: bool,
        actor: Actor,
        at: datetime,
        content: CandidateContent | None = None,
    ) -> ArchitectureKnowledge:
        require_maintainer(actor)
        release = _draft(self._knowledge, release_id)
        if release.revision != expected_revision:
            raise KnowledgeConflictError("The draft changed; reload before deciding.")
        decided = self._candidate(release_id, candidate_id).decide(accept, actor.id, at, content)
        if not accept:
            self._candidates.save_decision(decided)
            return release
        merged = apply_candidate(decided.content, release)
        updated = release.updated(
            systems=merged.systems,
            relationships=merged.relationships,
            landscape_domains=merged.landscape_domains,
            products=merged.products,
            journeys=merged.journeys,
        )
        self._save(updated, expected_revision, actor, (decided,))
        return updated

    def accept_all(
        self, release_id: str, expected_revision: int, actor: Actor, at: datetime
    ) -> tuple[ArchitectureKnowledge, int]:
        """Accept every undecided suggestion that can apply; returns how many were left.

        Inferred dependencies and suggestions that may name an existing system
        are left for a one-by-one decision.
        """
        require_maintainer(actor)
        release = _draft(self._knowledge, release_id)
        if release.revision != expected_revision:
            raise KnowledgeConflictError("The draft changed; reload before deciding.")
        pending = sorted(
            (
                item
                for item in self._candidates.list(release_id)
                if item.status is CandidateStatus.PROPOSED
            ),
            # A domain before the sub-domains inside it.
            key=lambda item: (
                _ORDER.index(item.content.kind),
                item.content.parent_domain_id is not None,
            ),
        )
        merged = release
        accepted: list[CatalogueCandidate] = []
        for candidate in pending:
            if needs_one_by_one(candidate, merged):
                continue
            try:
                merged = apply_candidate(candidate.content, merged)
            except (CandidateDependencyError, InvalidKnowledgeError):
                # Left undecided for a one-by-one look; the rest still apply.
                continue
            accepted.append(candidate.decide(True, actor.id, at))
        if not accepted:
            return release, len(pending)
        updated = release.updated(
            systems=merged.systems,
            relationships=merged.relationships,
            landscape_domains=merged.landscape_domains,
            products=merged.products,
            journeys=merged.journeys,
        )
        self._save(updated, expected_revision, actor, tuple(accepted))
        return updated, len(pending) - len(accepted)

    def reject_many(
        self,
        release_id: str,
        expected_revision: int,
        candidate_ids: tuple[str, ...],
        actor: Actor,
        at: datetime,
    ) -> int:
        """Reject the listed suggestions still waiting; returns how many were rejected.

        Suggestions already decided, by this person or someone else meanwhile,
        are left as they are rather than failing the whole request.
        """
        require_maintainer(actor)
        release = _draft(self._knowledge, release_id)
        if release.revision != expected_revision:
            raise KnowledgeConflictError("The draft changed; reload before deciding.")
        wanted = set(candidate_ids)
        rejected = 0
        for candidate in self._candidates.list(release_id):
            if candidate.id not in wanted or candidate.status is not CandidateStatus.PROPOSED:
                continue
            try:
                self._candidates.save_decision(candidate.decide(False, actor.id, at))
            except CandidateDecisionConflictError:
                continue
            rejected += 1
        return rejected

    def _save(
        self,
        updated: ArchitectureKnowledge,
        expected_revision: int,
        actor: Actor,
        decided: tuple[CatalogueCandidate, ...],
    ) -> None:
        """Mark decisions first, then save the draft; undo the marks if the draft moved on."""
        saved: list[str] = []
        try:
            for item in decided:
                self._candidates.save_decision(item)
                saved.append(item.id)
            self._repository.save(updated, expected_revision, actor.id, "accept_suggestion")
        except (CandidateDecisionConflictError, KnowledgeConflictError, PersistenceError):
            for candidate_id in saved:
                self._candidates.reopen(candidate_id)
            raise


def _identity(content: CandidateContent) -> CandidateContent:
    """What makes two proposals the same suggestion: a dependency's kind is not part of it."""
    if content.kind is CandidateKind.RELATIONSHIP:
        return replace(content, relationship_kind=None)
    return content


def _settled(
    content: CandidateContent, kinds: list[tuple[bool, RelationshipKind | None]]
) -> CandidateContent:
    """The kind of a merged dependency: a stated kind first, then any other one.

    Proposals that disagree leave the kind unspecified rather than pick one.
    """
    if content.kind is not CandidateKind.RELATIONSHIP:
        return content
    for stated_only in (True, False):
        found = {
            kind
            for stated, kind in kinds
            if (stated or not stated_only)
            and kind is not None
            and kind is not RelationshipKind.UNSPECIFIED
        }
        if found:
            only = found.pop() if len(found) == 1 else RelationshipKind.UNSPECIFIED
            return replace(content, relationship_kind=only)
    return replace(content, relationship_kind=RelationshipKind.UNSPECIFIED)
