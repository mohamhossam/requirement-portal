"""What other contexts may call in jobs (ADR-0103 §1): the AI-job command fingerprint.

The fingerprint binds an AI job to the exact command it runs. It is a pure function over the
jobs vocabulary, so it is jobs' (PR 14), and knowledge's prior-art screening uses it to
deduplicate its jobs.
"""

from __future__ import annotations

import hashlib
import json

from smb_requirement_agent.jobs.application.ports.ai_jobs import AiJobCommand
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

COMMAND_FINGERPRINT_VERSION = 2


def command_fingerprint(
    requirement_id: RequirementId,
    operation: AiJobOperation,
    command: AiJobCommand,
) -> str:
    payload = json.dumps(
        {
            "version": COMMAND_FINGERPRINT_VERSION,
            "requirement_id": requirement_id.value,
            "operation": operation.value,
            "arguments": command.arguments,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"v{COMMAND_FINGERPRINT_VERSION}:{digest}"
