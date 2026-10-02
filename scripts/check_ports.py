"""Fail fast when a fixed local launcher port is taken, for start.sh and start.bat."""

from __future__ import annotations

import argparse
import socket
import sys


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if sys.platform == "win32":
            # Windows SO_REUSEADDR would let the probe share a live listener's port.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # Ignore TIME_WAIT sockets from a just-stopped run; a live listener still fails.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        action="append",
        required=True,
        metavar="NAME=PORT",
        help="Label and port to check, for example API=8000. Repeat for each port.",
    )
    args = parser.parse_args(argv)

    for entry in args.port:
        name, _, raw_port = entry.rpartition("=")
        if not name or not raw_port.isdigit():
            parser.error(f"Expected NAME=PORT, got {entry!r}.")
        if not port_available(int(raw_port)):
            print(
                f"[startup] {name} cannot start because http://127.0.0.1:{raw_port} is "
                "already in use. Stop the existing process, then rerun the launcher.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
