"""Curate value streams, products, squads and people, independent of HTTP and storage."""

from __future__ import annotations

from dataclasses import replace

from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.identity import (
    Actor,
    require_maintainer,
    require_reader,
)
from smb_requirement_agent.application.ports.organisation_repository import (
    OrganisationRepositoryPort,
)
from smb_requirement_agent.domain.organisation.catalogue import (
    InvalidOrganisationError,
    OrganisationAuditEvent,
    OrganisationCatalogue,
    Person,
    Product,
    Squad,
    SystemOwnership,
    ValueStream,
)

_AUDIT_LIMIT = 200


class ManageOrganisationCatalogue:
    def __init__(
        self,
        repository: OrganisationRepositoryPort,
        architecture: ArchitectureKnowledgeRepositoryPort,
    ) -> None:
        self._repository = repository
        self._architecture = architecture

    def view(self, actor: Actor) -> OrganisationCatalogue:
        """Readers see who does what; contact details are for maintainers only."""
        require_reader(actor)
        catalogue = self._repository.load()
        if actor.may_maintain_knowledge:
            return catalogue
        return replace(
            catalogue, people=tuple(replace(item, email=None) for item in catalogue.people)
        )

    def audit(self, actor: Actor) -> tuple[OrganisationAuditEvent, ...]:
        require_maintainer(actor)
        return self._repository.audit(_AUDIT_LIMIT)

    def ownership(self, system_id: str, actor: Actor) -> SystemOwnership:
        return self.view(actor).ownership(system_id)

    def save_person(
        self, person: Person, expected_revision: int | None, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)
        return self._repository.change(
            lambda current: current.put_person(person, expected_revision),
            actor.id,
            "save_person",
            person.id,
        )

    def save_value_stream(
        self, stream: ValueStream, expected_revision: int | None, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)
        return self._repository.change(
            lambda current: current.put_value_stream(stream, expected_revision),
            actor.id,
            "save_value_stream",
            stream.id,
        )

    def save_product(
        self, product: Product, expected_revision: int | None, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)

        def change(current: OrganisationCatalogue) -> OrganisationCatalogue:
            previous = next((item for item in current.products if item.id == product.id), None)
            self._require_catalogued(
                product.system_ids, previous.system_ids if previous is not None else ()
            )
            return current.put_product(product, expected_revision)

        return self._repository.change(change, actor.id, "save_product", product.id)

    def save_squad(
        self, squad: Squad, expected_revision: int | None, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)

        def change(current: OrganisationCatalogue) -> OrganisationCatalogue:
            previous = next((item for item in current.squads if item.id == squad.id), None)
            self._require_catalogued(
                tuple(item.system_id for item in squad.systems),
                tuple(item.system_id for item in previous.systems) if previous else (),
            )
            return current.put_squad(squad, expected_revision)

        return self._repository.change(change, actor.id, "save_squad", squad.id)

    def remove_value_stream(
        self, value_stream_id: str, expected_revision: int, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)
        return self._repository.change(
            lambda current: current.remove_value_stream(value_stream_id, expected_revision),
            actor.id,
            "remove_value_stream",
            value_stream_id,
        )

    def remove_product(
        self, product_id: str, expected_revision: int, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)
        return self._repository.change(
            lambda current: current.remove_product(product_id, expected_revision),
            actor.id,
            "remove_product",
            product_id,
        )

    def remove_squad(
        self, squad_id: str, expected_revision: int, actor: Actor
    ) -> OrganisationCatalogue:
        require_maintainer(actor)
        return self._repository.change(
            lambda current: current.remove_squad(squad_id, expected_revision),
            actor.id,
            "remove_squad",
            squad_id,
        )

    def _require_catalogued(
        self, system_ids: tuple[str, ...], already_linked: tuple[str, ...]
    ) -> None:
        """New links must name systems in the active release; kept links may have lapsed."""
        known = {item.id for item in self._architecture.active().systems}
        unknown = sorted(set(system_ids) - known - set(already_linked))
        if unknown:
            raise InvalidOrganisationError(
                f"Systems {', '.join(unknown)} are not in the active architecture catalogue."
            )
