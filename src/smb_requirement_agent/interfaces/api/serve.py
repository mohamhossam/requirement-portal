"""API server process: ``python -m smb_requirement_agent.interfaces.api.serve``.

Configures operational logging before the server starts, so uvicorn's own
records use the same format, then serves the application. The application logs
one line per request itself (route template, status, duration, correlation ID),
so uvicorn's access log is off.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import uvicorn
from smb_kernel.observability.logging import configure_logging

from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings

# On SIGTERM, in-flight requests get this long to finish before the server stops. The
# reference manifest's stop_grace_period (30s) leaves room for it.
GRACEFUL_SHUTDOWN_SECONDS = 25


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the requirement API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--forwarded-allow-ips",
        default="127.0.0.1",
        help="Proxies trusted to set X-Forwarded-* headers (the reverse proxy's address).",
    )
    arguments = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"[api] {exc}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level, settings.log_format)
    uvicorn.run(
        "smb_requirement_agent.interfaces.api.main:app",
        host=arguments.host,
        port=arguments.port,
        log_config=None,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=arguments.forwarded_allow_ips,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
