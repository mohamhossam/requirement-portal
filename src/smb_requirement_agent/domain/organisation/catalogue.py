"""Who works on what: value streams own products and squads; squads staff systems.

The organisation catalogue is static reference data. It is edited in place (each
record carries its own revision for optimistic concurrency) rather than released
in versions like the architecture catalogue. Systems are referenced by their
architecture catalogue id and are never created here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime


class InvalidOrganisationError(ValueError):
    """A proposed organisation change violates a business invariant."""


class OrganisationConflictError(Exception):
    """A record changed while an editor was working on it."""


class OrganisationNotFoundError(Exception):
    """A referenced organisation record does not exist."""


def _required(value: str, label: str) -> str:
    result = value.strip()
    if not result:
        raise InvalidOrganisationError(f"{label} must not be blank.")
    return result


def _optional(value: str | None, label: str) -> str | None:
    return None if value is None else _required(value, label)


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    email: str | None = None
    team: str | None = None
    active: bool = True
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "Person id"))
        object.__setattr__(self, "name", _required(self.name, "Person name"))
        object.__setattr__(self, "email", _optional(self.email, "Person email"))
        object.__setattr__(self, "team", _optional(self.team, "Team"))
        if self.email is not None and "@" not in self.email:
            raise InvalidOrganisationError("Person email must be an email address.")


@dataclass(frozen=True)
class ValueStream:
    id: str
    name: str
    lead_person_id: str | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "Value stream id"))
        object.__setattr__(self, "name", _required(self.name, "Value stream name"))
        object.__setattr__(
            self, "lead_person_id", _optional(self.lead_person_id, "Value stream lead")
        )


@dataclass(frozen=True)
class Product:
    id: str
    value_stream_id: str
    name: str
    description: str = ""
    system_ids: tuple[str, ...] = ()
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "Product id"))
        object.__setattr__(self, "value_stream_id", _required(self.value_stream_id, "Value stream"))
        object.__setattr__(self, "name", _required(self.name, "Product name"))
        object.__setattr__(self, "description", self.description.strip())
        systems = tuple(_required(item, "Product system") for item in self.system_ids)
        if len(set(systems)) != len(systems):
            raise InvalidOrganisationError("A product lists each system once.")
        object.__setattr__(self, "system_ids", systems)


@dataclass(frozen=True)
class SquadSystemResource:
    """The one person who represents a system inside a squad, if already named."""

    system_id: str
    person_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "system_id", _required(self.system_id, "Squad system"))
        object.__setattr__(self, "person_id", _optional(self.person_id, "System resource"))


@dataclass(frozen=True)
class Squad:
    id: str
    name: str
    value_stream_id: str
    scrum_master_person_id: str | None = None
    systems: tuple[SquadSystemResource, ...] = ()
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "Squad id"))
        object.__setattr__(self, "name", _required(self.name, "Squad name"))
        object.__setattr__(self, "value_stream_id", _required(self.value_stream_id, "Value stream"))
        object.__setattr__(
            self,
            "scrum_master_person_id",
            _optional(self.scrum_master_person_id, "Scrum master"),
        )
        system_ids = [item.system_id for item in self.systems]
        if len(set(system_ids)) != len(system_ids):
            raise InvalidOrganisationError("A squad lists each system once.")


@dataclass(frozen=True)
class OrganisationAuditEvent:
    actor_id: str
    action: str
    subject_id: str
    created_at: datetime


@dataclass(frozen=True)
class SystemOwnership:
    """Where one architecture system sits in the organisation."""

    system_id: str
    squads: tuple[Squad, ...]
    products: tuple[Product, ...]
    value_streams: tuple[ValueStream, ...]


def _put[R: (Person, ValueStream, Product, Squad)](
    records: tuple[R, ...], record: R, expected_revision: int | None, label: str
) -> tuple[R, ...]:
    """Create when no revision is expected, otherwise replace the matching revision."""
    current = next((item for item in records if item.id == record.id), None)
    if expected_revision is None:
        if current is not None:
            raise OrganisationConflictError(f"{label} {record.id!r} already exists.")
        return records + (replace(record, revision=1),)
    if current is None:
        raise OrganisationNotFoundError(f"{label} {record.id!r} was not found.")
    if current.revision != expected_revision:
        raise OrganisationConflictError(f"{label} {record.id!r} changed; reload before saving.")
    updated = replace(record, revision=current.revision + 1)
    return tuple(updated if item.id == record.id else item for item in records)


def _remove[R: (Person, ValueStream, Product, Squad)](
    records: tuple[R, ...], record_id: str, expected_revision: int, label: str
) -> tuple[R, ...]:
    current = next((item for item in records if item.id == record_id), None)
    if current is None:
        raise OrganisationNotFoundError(f"{label} {record_id!r} was not found.")
    if current.revision != expected_revision:
        raise OrganisationConflictError(f"{label} {record_id!r} changed; reload before removing.")
    return tuple(item for item in records if item.id != record_id)


def _unique(values: Iterable[str], message: str) -> None:
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key in seen:
            raise InvalidOrganisationError(message.format(value=value))
        seen.add(key)


@dataclass(frozen=True)
class OrganisationCatalogue:
    people: tuple[Person, ...] = ()
    value_streams: tuple[ValueStream, ...] = ()
    products: tuple[Product, ...] = ()
    squads: tuple[Squad, ...] = ()

    def __post_init__(self) -> None:
        for label, records in (
            ("person", self.people),
            ("value stream", self.value_streams),
            ("product", self.products),
            ("squad", self.squads),
        ):
            _unique((item.id for item in records), f"Duplicate {label} id {{value!r}}.")
        _unique(
            (item.email for item in self.people if item.email),
            "Email {value!r} belongs to more than one person.",
        )
        _unique(
            (item.name for item in self.value_streams),
            "Value stream name {value!r} is already used.",
        )
        people = {item.id: item for item in self.people}
        streams = {item.id for item in self.value_streams}

        def require_person(person_id: str | None, role: str) -> None:
            if person_id is None:
                return
            person = people.get(person_id)
            if person is None:
                raise InvalidOrganisationError(f"{role} {person_id!r} is not a known person.")
            if not person.active:
                raise InvalidOrganisationError(
                    f"{person.name} is inactive and cannot be the {role.lower()}."
                )

        for stream in self.value_streams:
            require_person(stream.lead_person_id, "Value stream lead")
        owned: list[Product | Squad] = [*self.products, *self.squads]
        for item in owned:
            if item.value_stream_id not in streams:
                raise InvalidOrganisationError(
                    f"Unknown value stream {item.value_stream_id!r} for {item.name!r}."
                )
        for stream_id in streams:
            _unique(
                (item.name for item in self.products if item.value_stream_id == stream_id),
                "Product name {value!r} is already used in this value stream.",
            )
            _unique(
                (item.name for item in self.squads if item.value_stream_id == stream_id),
                "Squad name {value!r} is already used in this value stream.",
            )
        for squad in self.squads:
            require_person(squad.scrum_master_person_id, "Scrum master")
            for resource in squad.systems:
                require_person(resource.person_id, "System resource")

    def person(self, person_id: str) -> Person:
        return self._find(self.people, person_id, "Person")

    def value_stream(self, value_stream_id: str) -> ValueStream:
        return self._find(self.value_streams, value_stream_id, "Value stream")

    def product(self, product_id: str) -> Product:
        return self._find(self.products, product_id, "Product")

    def squad(self, squad_id: str) -> Squad:
        return self._find(self.squads, squad_id, "Squad")

    @staticmethod
    def _find[R: (Person, ValueStream, Product, Squad)](
        records: tuple[R, ...], record_id: str, label: str
    ) -> R:
        found = next((item for item in records if item.id == record_id), None)
        if found is None:
            raise OrganisationNotFoundError(f"{label} {record_id!r} was not found.")
        return found

    def put_person(self, person: Person, expected_revision: int | None) -> OrganisationCatalogue:
        return replace(self, people=_put(self.people, person, expected_revision, "Person"))

    def put_value_stream(
        self, stream: ValueStream, expected_revision: int | None
    ) -> OrganisationCatalogue:
        return replace(
            self,
            value_streams=_put(self.value_streams, stream, expected_revision, "Value stream"),
        )

    def put_product(self, product: Product, expected_revision: int | None) -> OrganisationCatalogue:
        return replace(self, products=_put(self.products, product, expected_revision, "Product"))

    def put_squad(self, squad: Squad, expected_revision: int | None) -> OrganisationCatalogue:
        return replace(self, squads=_put(self.squads, squad, expected_revision, "Squad"))

    def remove_value_stream(
        self, value_stream_id: str, expected_revision: int
    ) -> OrganisationCatalogue:
        owned: list[Product | Squad] = [*self.products, *self.squads]
        if any(item.value_stream_id == value_stream_id for item in owned):
            raise InvalidOrganisationError(
                "Move or remove this value stream's products and squads first."
            )
        return replace(
            self,
            value_streams=_remove(
                self.value_streams, value_stream_id, expected_revision, "Value stream"
            ),
        )

    def remove_product(self, product_id: str, expected_revision: int) -> OrganisationCatalogue:
        return replace(
            self, products=_remove(self.products, product_id, expected_revision, "Product")
        )

    def remove_squad(self, squad_id: str, expected_revision: int) -> OrganisationCatalogue:
        return replace(self, squads=_remove(self.squads, squad_id, expected_revision, "Squad"))

    def ownership(self, system_id: str) -> SystemOwnership:
        squads = tuple(
            sorted(
                (
                    squad
                    for squad in self.squads
                    if any(item.system_id == system_id for item in squad.systems)
                ),
                key=lambda item: item.name.casefold(),
            )
        )
        products = tuple(
            sorted(
                (item for item in self.products if system_id in item.system_ids),
                key=lambda item: item.name.casefold(),
            )
        )
        stream_ids = {item.value_stream_id for item in squads} | {
            item.value_stream_id for item in products
        }
        streams = tuple(
            sorted(
                (item for item in self.value_streams if item.id in stream_ids),
                key=lambda item: item.name.casefold(),
            )
        )
        return SystemOwnership(system_id, squads, products, streams)
