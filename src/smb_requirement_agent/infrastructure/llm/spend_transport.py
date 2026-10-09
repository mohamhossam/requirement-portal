"""Count the tokens each model response reports toward the daily budget (ADR-0106).

Counting never fails a model call: a response is returned as received, and a
failure to record its spend is logged instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
import httpx2
from smb_kernel.observability.metrics import provider_usage

_LOGGER = logging.getLogger(__name__)


def _record(record: Callable[[int], None], status_code: int, body: bytes) -> None:
    if not 200 <= status_code < 300:
        return
    try:
        usage = provider_usage(body)
        if usage is not None:
            record(sum(usage[1].values()))
    except Exception:
        _LOGGER.warning("Recording provider token spend failed.", exc_info=True)


class SpendCountingTransport(httpx.BaseTransport):
    def __init__(self, record: Callable[[int], None], inner: httpx.BaseTransport) -> None:
        self._record = record
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)
        # Model calls are non-streaming, so the client reuses the content read here.
        _record(self._record, response.status_code, response.read())
        return response

    def close(self) -> None:
        self._inner.close()


class SpendCountingTransport2(httpx2.BaseTransport):
    """The same, for the `httpx2` client inside the OpenAI SDK."""

    def __init__(self, record: Callable[[int], None], inner: httpx2.BaseTransport) -> None:
        self._record = record
        self._inner = inner

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        response = self._inner.handle_request(request)
        _record(self._record, response.status_code, response.read())
        return response

    def close(self) -> None:
        self._inner.close()
