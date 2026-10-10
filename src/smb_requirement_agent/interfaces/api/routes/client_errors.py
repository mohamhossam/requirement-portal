"""Browsers report their own failures, which otherwise only their console sees.

Public, because the app may fail before anyone has signed in, or while signing in.
The edge limits it per address (`deploy/web/default.conf.template`), and the body
names only a kind, so a report cannot carry content into the logs.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from smb_requirement_agent.interfaces.api.dependencies import ContainerDep
from smb_requirement_agent.interfaces.api.schemas.client_errors import ClientErrorReport

router = APIRouter(tags=["client-errors"])
_LOGGER = logging.getLogger("smb_requirement_agent.client_errors")


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
def report_client_error(report: ClientErrorReport, container: ContainerDep) -> Response:
    """Count one browser failure in `smb_client_errors_total`."""
    container.metrics.record_client_error(report.kind)
    _LOGGER.warning("A browser reported a failure: %s", report.kind)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
