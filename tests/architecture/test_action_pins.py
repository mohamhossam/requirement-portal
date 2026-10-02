"""Every GitHub Action is pinned by commit SHA, with its release named beside it.

A tag such as `v4` can be moved upstream, so a tag-pinned action can change
what runs in CI, with repository credentials, without a commit here. A full
commit SHA cannot move. Dependabot (`.github/dependabot.yml`) proposes SHA
updates as reviewable pull requests, and the trailing `# vX.Y.Z` comment keeps
the pin readable. The same rule for container images is in test_image_pins.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
RELEASE_COMMENT = re.compile(r"^\s*#\s*v\d+\.\d+\.\d+\s*$")


def _uses() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = USES.match(line)
            if match:
                found.append((workflow.name, match.group(1), match.group(2)))
    return found


def test_action_references_were_found() -> None:
    assert len(_uses()) >= 10


def test_every_action_is_pinned_by_commit_sha_with_its_release() -> None:
    unpinned = [
        (where, action)
        for where, action, comment in _uses()
        if not action.startswith("./")
        and not (PINNED.match(action) and RELEASE_COMMENT.match(comment))
    ]

    assert unpinned == [], f"Pin these as owner/repo@<40-hex sha> # vX.Y.Z: {unpinned}"
