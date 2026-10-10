"""Paged drafts and documents for the offline store, by the same rules as PostgreSQL."""

from __future__ import annotations

from collections.abc import Callable

from smb_requirement_agent.requirements.application.ports.catalogue_pages import (
    DocumentCounts,
    DocumentFilter,
    DocumentOwner,
    DocumentPage,
    DocumentPageQuery,
    DocumentSort,
    DraftPage,
    DraftPageQuery,
    DraftSort,
    ListedDocument,
)
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.shared_kernel.actors import ActorId
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _matches(value: str | None, needle: str) -> bool:
    return needle in (value or "").lower()


def _in_group(listed: ListedDocument, wanted: DocumentFilter) -> bool:
    attention = listed.document.requires_attention
    included = listed.document.included_version_id is not None
    return {
        DocumentFilter.ALL: True,
        DocumentFilter.ATTENTION: attention,
        DocumentFilter.INCLUDED: not attention and included,
        DocumentFilter.EXCLUDED: not attention and not included,
    }[wanted]


class InMemoryCataloguePages:
    def __init__(
        self,
        drafts: RequirementDraftRepositoryPort,
        requirements: RequirementRepositoryPort,
        documents: DocumentRepositoryPort,
        draft_owner: Callable[[RequirementId], ActorId | None],
    ) -> None:
        self._drafts = drafts
        self._requirements = requirements
        self._documents = documents
        self._draft_owner = draft_owner

    def drafts(self, query: DraftPageQuery) -> DraftPage:
        needle = (query.q or "").strip().lower()
        selected = [
            draft
            for draft in self._drafts.list_all()
            if self._draft_owner(draft.id) == query.owner_id
            and (not needle or _matches(draft.title, needle))
        ]
        if query.sort in (DraftSort.TITLE_ASC, DraftSort.TITLE_DESC):
            selected.sort(key=lambda draft: draft.id.value)
            selected.sort(
                key=lambda draft: (draft.title or "").lower(),
                reverse=query.sort is DraftSort.TITLE_DESC,
            )
        else:
            selected.sort(key=lambda draft: draft.id.value)
            selected.sort(
                key=lambda draft: draft.updated_at,
                reverse=query.sort is DraftSort.UPDATED_DESC,
            )
        return DraftPage(tuple(selected[query.offset : query.offset + query.limit]), len(selected))

    def documents(self, query: DocumentPageQuery) -> DocumentPage:
        visible = [
            ListedDocument(document, self.owner_of(document))
            for document in self._documents.list_all()
            if document.draft_id is None or self._draft_owner(document.draft_id) == query.viewer_id
        ]
        needle = (query.q or "").strip().lower()
        selected = [
            listed
            for listed in visible
            if _in_group(listed, query.filter)
            and (query.owner_id is None or listed.owner.id == query.owner_id)
            and (
                not needle
                or _matches(listed.document.current_version.filename, needle)
                or _matches(listed.owner.title, needle)
            )
        ]
        selected.sort(key=lambda listed: listed.document.id.value)
        if query.sort in (DocumentSort.NAME_ASC, DocumentSort.NAME_DESC):
            selected.sort(
                key=lambda listed: listed.document.current_version.filename.lower(),
                reverse=query.sort is DocumentSort.NAME_DESC,
            )
        else:
            selected.sort(
                key=lambda listed: listed.document.current_version.created_at,
                reverse=query.sort is DocumentSort.ADDED_DESC,
            )
        # A document blocking analysis comes first, whatever the sort.
        selected.sort(key=lambda listed: not listed.document.requires_attention)
        owners = {(owner.kind, owner.id.value): owner for owner in (item.owner for item in visible)}
        return DocumentPage(
            documents=tuple(selected[query.offset : query.offset + query.limit]),
            total=len(selected),
            counts=DocumentCounts(
                *(
                    sum(_in_group(item, group) for item in visible)
                    for group in (
                        DocumentFilter.ATTENTION,
                        DocumentFilter.INCLUDED,
                        DocumentFilter.EXCLUDED,
                    )
                )
            ),
            owners=tuple(
                sorted(owners.values(), key=lambda owner: ((owner.title or ""), owner.id.value))
            ),
        )

    def owner_of(self, document: SourceDocument) -> DocumentOwner:
        if document.requirement_id is not None:
            requirement = self._requirements.get(document.requirement_id)
            return DocumentOwner(
                "requirement",
                document.requirement_id,
                requirement.title.value if requirement else None,
            )
        draft_id = RequirementId(str(document.draft_id.value if document.draft_id else ""))
        draft = self._drafts.get(draft_id)
        return DocumentOwner("draft", draft_id, draft.title if draft else None)
