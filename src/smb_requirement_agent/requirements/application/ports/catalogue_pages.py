"""Paged reads of drafts and documents (production hardening PR 13).

Each read filters, sorts and pages where the rows are stored, so a page costs
the same however many drafts and documents exist. Draft ownership decides
visibility the way `RequirementAccessService.can_access_draft` does: a draft and
its documents belong to its owner alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.requirements.domain.requirement.entities import RequirementDraft
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class DraftSort(StrEnum):
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"


@dataclass(frozen=True)
class DraftPageQuery:
    """One owner's drafts, or with `owner_id` None the drafts nobody owns (legacy)."""

    owner_id: ActorId | None
    q: str | None
    sort: DraftSort
    offset: int
    limit: int


@dataclass(frozen=True)
class DraftPage:
    drafts: tuple[RequirementDraft, ...]
    total: int


class DocumentFilter(StrEnum):
    """As the documents page groups them: blocking analysis first, never also counted below."""

    ALL = "all"
    ATTENTION = "attention"
    INCLUDED = "included"
    EXCLUDED = "excluded"


class DocumentSort(StrEnum):
    """By the current version; a document blocking analysis comes first whatever the sort."""

    ADDED_DESC = "added_desc"
    ADDED_ASC = "added_asc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"


@dataclass(frozen=True)
class DocumentOwner:
    """The Requirement or draft a document is attached to; its title, if it still exists."""

    kind: Literal["requirement", "draft"]
    id: RequirementId
    title: str | None


@dataclass(frozen=True)
class ListedDocument:
    document: SourceDocument
    owner: DocumentOwner


@dataclass(frozen=True)
class DocumentCounts:
    attention: int
    included: int
    excluded: int


@dataclass(frozen=True)
class DocumentPageQuery:
    """The documents `viewer_id` may open: every Requirement's, and their own drafts'."""

    viewer_id: ActorId
    q: str | None
    filter: DocumentFilter
    owner_id: RequirementId | None
    sort: DocumentSort
    offset: int
    limit: int


@dataclass(frozen=True)
class DocumentPage:
    """One page, with the counts and owners of everything the viewer may open, unfiltered."""

    documents: tuple[ListedDocument, ...]
    total: int
    counts: DocumentCounts
    owners: tuple[DocumentOwner, ...]


class CataloguePagesPort(Protocol):
    def drafts(self, query: DraftPageQuery) -> DraftPage: ...

    def documents(self, query: DocumentPageQuery) -> DocumentPage: ...

    def owner_of(self, document: SourceDocument) -> DocumentOwner: ...
