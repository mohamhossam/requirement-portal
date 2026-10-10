"""A withdrawal in the knowledge portal reaches requirement work within one poll (ADR-0099).

Run by CI's deployment job against both portals, started offline from their own
manifests and joined on the peer network (ADR-0104). Through the knowledge portal's
edge, as a knowledge admin, it adds a
library document, reviews and approves it, and waits for requirement work's copy of
that document (`reference_publication_state`, fed by the knowledge event feed) to show
it published. It then withdraws the document and requires the copy to show no live
publication within the deadline. Citations are judged current against that copy, so
this is the step that makes them stale.

Standard library only: the job runs it without installing the project.

    python3 tests/platform_withdrawal.py \
        --knowledge-url http://127.0.0.1:8090/knowledge-api \
        --requirements-psql "docker compose -f deploy/compose.production.yaml exec -T postgres \
            psql -U smb -d smb_requirements"
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

ADMIN = {"X-Fake-Actor-Id": "fake-owner"}
# Requirement work's event loop rests a second when idle; one poll is well inside this.
WITHIN_SECONDS = 15


class Platform:
    def __init__(self, knowledge_url: str, requirements_psql: str) -> None:
        self._base = knowledge_url.rstrip("/")
        self._psql = shlex.split(requirements_psql)

    def call(self, method: str, path: str, body: Any = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        headers = {**ADMIN, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self._base + path, data, headers, method=method)  # noqa: S310 - the test's own http base URL
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - the test's own http base URL
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            detail = error.read()[:500]
            raise SystemExit(f"{method} {path} answered {error.code}: {detail!r}") from None

    def upload(self, title: str, name: str, content: bytes) -> Any:
        boundary = uuid.uuid4().hex
        fields = {"title": title, "idempotency_key": f"platform-withdrawal-{boundary}"}
        head = f"--{boundary}\r\nContent-Disposition: form-data; name="
        parts = [f'{head}"{key}"\r\n\r\n{value}\r\n'.encode() for key, value in fields.items()]
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: text/plain\r\n\r\n".encode()
            + content
            + b"\r\n"
        )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        request = urllib.request.Request(  # noqa: S310 - the test's own http base URL
            self._base + "/library/ingestions",
            body,
            {**ADMIN, "Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - the test's own http base URL
            return json.loads(response.read())

    def requirement_copy(self, document_id: str) -> dict[str, Any] | None:
        """Requirement work's copy of a document's publication, read from its database."""
        query = (
            "SELECT payload FROM reference_publication_state "  # noqa: S608 - test-made id, quotes stripped
            f"WHERE document_id = '{document_id.replace(chr(39), '')}'"
        )
        found = subprocess.run(  # noqa: S603 - fixed psql argv
            [*self._psql, "-tAc", query],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return json.loads(found) if found else None


def wait_for(what: str, seconds: float, check: Any) -> Any:
    deadline = time.monotonic() + seconds
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > deadline:
            raise SystemExit(f"Timed out after {seconds}s waiting for {what}.")
        time.sleep(0.5)


def read(platform: Platform, path: str) -> Any:
    """The document once it waits for review; a failed reading ends the check."""
    current = platform.call("GET", path)
    version = current["versions"][0]
    if version["stage"] == "failed":
        raise SystemExit(f"The knowledge portal could not read the document: {version['error']}")
    return current if version["stage"] == "ready_for_review" else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--knowledge-url", default="http://127.0.0.1:8090/knowledge-api")
    parser.add_argument(
        "--requirements-psql",
        default=(
            "docker compose -f deploy/compose.production.yaml exec -T postgres "
            "psql -U smb -d smb_requirements"
        ),
        help="A psql command line for requirement work's database.",
    )
    arguments = parser.parse_args()
    platform = Platform(arguments.knowledge_url, arguments.requirements_psql)

    document = platform.upload(
        "Platform withdrawal check", "withdrawal.txt", b"XGPON coverage is required."
    )
    path = f"/library/documents/{document['id']}"
    view = wait_for("the document to be scanned and read", 300, lambda: read(platform, path))
    source = view["versions"][0]
    reviewed = platform.call(
        "POST",
        f"{path}/versions/{source['id']}/review",
        {
            "expected_version": view["version"],
            "explanation": "Platform check",
            "passages": [
                {"block_id": b["id"], "text": b["text"], "included": True, "exclusion_reason": ""}
                for b in source["blocks"]
            ],
        },
    )
    platform.call(
        "POST",
        f"{path}/versions/{source['id']}/approval",
        {
            "expected_version": reviewed["version"],
            "revision_id": reviewed["versions"][0]["revisions"][-1]["id"],
            "fingerprint": reviewed["review_fingerprint"],
        },
    )
    published = wait_for(
        "the knowledge portal to publish the document",
        120,
        lambda: (current := platform.call("GET", path))["published_id"] and current,
    )
    wait_for(
        "requirement work's copy to show the publication",
        WITHIN_SECONDS,
        lambda: (platform.requirement_copy(document["id"]) or {}).get("published"),
    )
    print(f"Published {document['id']}; requirement work's copy shows it published.")

    platform.call(
        "POST",
        f"{path}/withdrawal",
        {"expected_version": published["version"], "reason": "Platform withdrawal check"},
    )
    started = time.monotonic()
    wait_for(
        "requirement work's copy to show the withdrawal",
        WITHIN_SECONDS,
        lambda: (
            (copy := platform.requirement_copy(document["id"])) is not None
            and copy.get("published") is None
        ),
    )
    print(
        f"Withdrew {document['id']}; requirement work's copy showed it withdrawn after "
        f"{time.monotonic() - started:.1f}s."
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(f"{error.cmd} failed: {error.stderr}")
