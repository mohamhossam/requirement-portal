"""The fingerprint that binds an AI job to the exact command it runs.

Pure function over the jobs vocabulary, so it is jobs' (ADR-0103 PR 14); it was in workflows'
`ai_jobs`, which knowledge's `prior_art` imported it from.
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
