"""Actor failures raised by the identity use cases."""


class ActorNotFoundError(Exception):
    """An assignment target is not known to this workspace."""
