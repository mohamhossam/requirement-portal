"""HTTP schemas for the organisation catalogue: value streams, products, squads, people."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationAuditEvent,
    OrganisationCatalogue,
    Person,
    Product,
    Squad,
    SquadSystemResource,
    SystemOwnership,
    ValueStream,
)
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_CATALOGUE_ITEMS,
    Identifier,
    Name,
    RequiredIdentifier,
    Text,
)


class PersonSchema(BaseModel):
    id: RequiredIdentifier
    name: Name
    email: Name | None = None
    team: Name | None = None
    active: bool = True
    revision: int = 1

    @classmethod
    def from_domain(cls, person: Person) -> PersonSchema:
        return cls.model_construct(
            id=person.id,
            name=person.name,
            email=person.email,
            team=person.team,
            active=person.active,
            revision=person.revision,
        )

    def to_domain(self) -> Person:
        return Person(self.id, self.name, self.email, self.team, self.active)


class ValueStreamSchema(BaseModel):
    id: RequiredIdentifier
    name: Name
    lead_person_id: Identifier | None = None
    revision: int = 1

    @classmethod
    def from_domain(cls, stream: ValueStream) -> ValueStreamSchema:
        return cls.model_construct(
            id=stream.id,
            name=stream.name,
            lead_person_id=stream.lead_person_id,
            revision=stream.revision,
        )

    def to_domain(self) -> ValueStream:
        return ValueStream(self.id, self.name, self.lead_person_id)


class ProductSchema(BaseModel):
    id: RequiredIdentifier
    value_stream_id: RequiredIdentifier
    name: Name
    description: Text = ""
    system_ids: list[Identifier] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    revision: int = 1

    @classmethod
    def from_domain(cls, product: Product) -> ProductSchema:
        return cls.model_construct(
            id=product.id,
            value_stream_id=product.value_stream_id,
            name=product.name,
            description=product.description,
            system_ids=list(product.system_ids),
            revision=product.revision,
        )

    def to_domain(self) -> Product:
        return Product(
            self.id, self.value_stream_id, self.name, self.description, tuple(self.system_ids)
        )


class SquadSystemSchema(BaseModel):
    system_id: RequiredIdentifier
    person_id: Identifier | None = None


class SquadSchema(BaseModel):
    id: RequiredIdentifier
    name: Name
    value_stream_id: RequiredIdentifier
    scrum_master_person_id: Identifier | None = None
    systems: list[SquadSystemSchema] = Field(default=[], max_length=MAX_CATALOGUE_ITEMS)
    revision: int = 1

    @classmethod
    def from_domain(cls, squad: Squad) -> SquadSchema:
        return cls.model_construct(
            id=squad.id,
            name=squad.name,
            value_stream_id=squad.value_stream_id,
            scrum_master_person_id=squad.scrum_master_person_id,
            systems=[
                SquadSystemSchema.model_construct(
                    system_id=item.system_id, person_id=item.person_id
                )
                for item in squad.systems
            ],
            revision=squad.revision,
        )

    def to_domain(self) -> Squad:
        return Squad(
            self.id,
            self.name,
            self.value_stream_id,
            self.scrum_master_person_id,
            tuple(SquadSystemResource(item.system_id, item.person_id) for item in self.systems),
        )


class OrganisationResponse(BaseModel):
    people: list[PersonSchema]
    value_streams: list[ValueStreamSchema]
    products: list[ProductSchema]
    squads: list[SquadSchema]

    @classmethod
    def from_domain(cls, catalogue: OrganisationCatalogue) -> OrganisationResponse:
        return cls.model_construct(
            people=[PersonSchema.from_domain(item) for item in catalogue.people],
            value_streams=[ValueStreamSchema.from_domain(item) for item in catalogue.value_streams],
            products=[ProductSchema.from_domain(item) for item in catalogue.products],
            squads=[SquadSchema.from_domain(item) for item in catalogue.squads],
        )


class SystemOwnershipResponse(BaseModel):
    system_id: str
    squads: list[SquadSchema]
    products: list[ProductSchema]
    value_streams: list[ValueStreamSchema]

    @classmethod
    def from_domain(cls, ownership: SystemOwnership) -> SystemOwnershipResponse:
        return cls.model_construct(
            system_id=ownership.system_id,
            squads=[SquadSchema.from_domain(item) for item in ownership.squads],
            products=[ProductSchema.from_domain(item) for item in ownership.products],
            value_streams=[ValueStreamSchema.from_domain(item) for item in ownership.value_streams],
        )


class OrganisationAuditEventResponse(BaseModel):
    actor_id: str
    action: str
    subject_id: str
    created_at: datetime

    @classmethod
    def from_domain(cls, event: OrganisationAuditEvent) -> OrganisationAuditEventResponse:
        return cls(
            actor_id=event.actor_id,
            action=event.action,
            subject_id=event.subject_id,
            created_at=event.created_at,
        )


class PersonRequest(BaseModel):
    """``expected_revision`` is omitted to create and required to update."""

    expected_revision: int | None = None
    person: PersonSchema


class ValueStreamRequest(BaseModel):
    expected_revision: int | None = None
    value_stream: ValueStreamSchema


class ProductRequest(BaseModel):
    expected_revision: int | None = None
    product: ProductSchema


class SquadRequest(BaseModel):
    expected_revision: int | None = None
    squad: SquadSchema


class RemovalRequest(BaseModel):
    expected_revision: int
