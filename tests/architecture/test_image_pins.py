"""Every third-party container image is pinned by digest.

A tag can be re-pointed upstream, so an unpinned tag lets a build change, or
pick up a compromised image, without a commit. Dependabot proposes digest
updates as reviewable pull requests instead. PostgreSQL must also be the same
image everywhere: development, CI and the reference deployment.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINNED = re.compile(r"^[\w./:-]+@sha256:[0-9a-f]{64}$")
# The images this repository builds, tagged rather than pulled; a release names
# them by variable and tag (ADR-0108). The knowledge portal's are pinned by its
# own deployment (ADR-0104).
OWN_IMAGES = (
    "requirement-platform/",
    "${REQUIREMENT_API_IMAGE:-",
    "${REQUIREMENT_WEB_IMAGE:-",
    # The release workflow names the images it just pushed by their digest
    # (`${{ env.API_DIGEST }}`).
    "${{",
)


def _references() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for dockerfile in (ROOT / "deploy").rglob("Dockerfile"):
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            if line.startswith("FROM "):
                found.append((dockerfile.name, line.split()[1]))
            copy_from = re.match(r"COPY --from=(\S+)", line)
            if copy_from and ("/" in copy_from.group(1) or ":" in copy_from.group(1)):
                found.append((dockerfile.name, copy_from.group(1)))
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    for manifest in (
        ROOT / "compose.yaml",
        ROOT / "deploy" / "compose.production.yaml",
        ROOT / "deploy" / "compose.monitoring.yaml",
        ROOT / "deploy" / "keycloak" / "compose.yaml",
        *workflows,
    ):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            image = re.match(r"\s*image:\s*(\S+)", line)
            if image and not image.group(1).startswith(OWN_IMAGES):
                found.append((manifest.name, image.group(1)))
    # Workflows also name the images they `docker run` in an environment variable,
    # such as TRIVY or GITLEAKS.
    for workflow in workflows:
        for line in workflow.read_text(encoding="utf-8").splitlines():
            run_image = re.match(r"\s*[A-Z][A-Z0-9_]*:\s*([\w.-]+/[\w./-]+:[\w.-]+\S*)\s*$", line)
            if run_image:
                found.append((workflow.name, run_image.group(1)))
    return found


def test_image_references_were_found() -> None:
    assert len(_references()) >= 8


def test_every_third_party_image_is_pinned_by_digest() -> None:
    unpinned = [(where, image) for where, image in _references() if not PINNED.match(image)]

    assert unpinned == [], f"Pin these images as tag@sha256:<digest>: {unpinned}"


def test_postgres_is_the_same_image_everywhere() -> None:
    postgres = {image for _, image in _references() if image.startswith("pgvector/")}

    assert len(postgres) == 1, f"PostgreSQL images differ: {sorted(postgres)}"
