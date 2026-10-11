"""The work-item tracker's service hook, as the API serves it (ontology plan Phase 7).

The tracker signs its calls with Basic auth: any user name, and `ADO_HOOK_SECRET` as the
password. The route is served only with that secret set and a knowledge service to send
closures to; otherwise it answers 404, as if it were not there.
"""

from __future__ import annotations

import base64
import binascii
import hmac
from dataclasses import dataclass, field

from smb_requirement_agent.governance.application.use_cases.delivery_closure import (
    RecordTrackerEvent,
)


@dataclass(frozen=True)
class TrackerHook:
    secret: str = field(repr=False)
    record: RecordTrackerEvent

    def admits(self, authorization: str | None) -> bool:
        """Whether a request's `Authorization` header carries the secret, compared in
        constant time."""
        scheme, _, encoded = (authorization or "").partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return False
        try:
            decoded = base64.b64decode(encoded.strip(), validate=True).decode()
        except (binascii.Error, UnicodeDecodeError):
            return False
        _, _, password = decoded.partition(":")
        return hmac.compare_digest(password.encode(), self.secret.encode())
