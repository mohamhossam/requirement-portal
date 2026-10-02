"""Deterministic offline identity provider."""

from smb_requirement_agent.application.errors import AuthenticationRequiredError
from smb_requirement_agent.application.ports.identity_provider import (
    IdentityCredential,
    IdentityProviderPort,
)
from smb_requirement_agent.domain.identity.entities import ActorId, ActorProfile

FAKE_ACTORS = (
    ActorProfile(
        ActorId("fake-owner"),
        "Amina Owner",
        "amina.owner@example.test",
        frozenset({"knowledge_reader", "knowledge_maintainer"}),
    ),
    ActorProfile(
        ActorId("fake-reviewer"),
        "Ravi Reviewer",
        "ravi.reviewer@example.test",
        frozenset({"knowledge_reader"}),
    ),
    ActorProfile(ActorId("fake-observer"), "Omar Observer", "omar.observer@example.test"),
)


class FakeIdentityProvider(IdentityProviderPort):
    def __init__(self, actors: tuple[ActorProfile, ...] = FAKE_ACTORS) -> None:
        self.actors = actors

    def authenticate(self, credential: IdentityCredential) -> ActorProfile:
        actor_id = (credential.actor_hint or self.actors[0].id.value).strip()
        actor = next((item for item in self.actors if item.id.value == actor_id), None)
        if actor is None:
            raise AuthenticationRequiredError("Unknown fake actor identity.")
        return actor
