"""Poll a local URL until it answers, for start.bat (avoids a PowerShell dependency)."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request


def url_ready(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Label used in the timeout message.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if url_ready(args.url, timeout=2.0):
            return 0
        time.sleep(0.3)

    print(
        f"[startup] {args.name} did not become ready at {args.url} "
        f"within {args.timeout:g} seconds. Check its Command Prompt window for errors.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
