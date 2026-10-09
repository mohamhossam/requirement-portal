"""Deterministic offline identity provider.

The ids and the knowledge_admin role match knowledge-portal's personas, so the
two agree on who is who, and who is a knowledge admin, when run together
without an identity provider. Nothing depends on that (ADR-0104).
"""

from smb_kernel.identity.fake import FakeIdentityProvider as KernelFakeIdentityProvider

from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)

FAKE_ACTORS = (
    ActorProfile(
        ActorId("fake-owner"),
        "Amina Owner",
        "amina.owner@example.test",
        frozenset({"knowledge_admin", "architecture_maintainer"}),
    ),
    ActorProfile(
        ActorId("fake-reviewer"),
        "Ravi Reviewer",
        "ravi.reviewer@example.test",
        frozenset({"knowledge_admin"}),
    ),
    # Not a knowledge admin: no link to the knowledge portal.
    ActorProfile(ActorId("fake-observer"), "Omar Observer", "omar.observer@example.test"),
)


class FakeIdentityProvider(KernelFakeIdentityProvider):
    """The kernel's offline provider with this application's personas."""

    def __init__(self, actors: tuple[ActorProfile, ...] = FAKE_ACTORS) -> None:
        super().__init__(actors)
