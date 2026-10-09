"""The reference deployment runs requirement work on its own.

ADR-0104 gives the knowledge portal its own deployment, sign-in entities and
address. These checks hold the manifest, the edge proxy and the identity realm
to that: nothing of the knowledge portal runs or signs in here, the two connect
only through the optional peer overlay, and no browser reaches /internal.
"""

import inspect
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from smb_requirement_agent.identity.application.ports import identity

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
MANIFEST: dict[str, Any] = yaml.safe_load(
    (DEPLOY / "compose.production.yaml").read_text(encoding="utf-8")
)
PEER: dict[str, Any] = yaml.safe_load((DEPLOY / "compose.peer.yaml").read_text(encoding="utf-8"))
SERVICES: dict[str, Any] = MANIFEST["services"]
EDGE = (DEPLOY / "web" / "default.conf.template").read_text(encoding="utf-8")
WEB_IMAGE = (DEPLOY / "web" / "Dockerfile").read_text(encoding="utf-8")
URL_CHECK = DEPLOY / "web" / "check-knowledge-portal-url.sh"
REALM: dict[str, Any] = json.loads(
    (DEPLOY / "keycloak" / "realm-requirement-ai.json").read_text(encoding="utf-8")
)
PEER_SETTINGS = (
    "KNOWLEDGE_API_BASE_URL",
    "REQUIREMENT_SERVICE_TOKEN",
    "KNOWLEDGE_SERVICE_TOKEN",
)


def test_the_project_never_collides_with_the_earlier_deployment() -> None:
    assert MANIFEST["name"] == "requirement-platform"
    built = [SERVICES[name].get("image", "") for name in ("api", "web")]
    assert all(image.startswith("requirement-platform/") for image in built)


def test_nothing_of_the_knowledge_portal_runs_here() -> None:
    assert not [name for name in SERVICES if name.startswith("knowledge")]
    assert "x-knowledge" not in MANIFEST
    assert set(MANIFEST["volumes"]) == {"postgres_data", "clamav_data"}
    images = [service.get("image", "") for service in SERVICES.values()]
    assert not [image for image in images if "knowledge" in image]
    assert not (DEPLOY / "knowledge.env.example").exists()


def test_the_knowledge_portal_is_configured_in_the_settings_file_or_not_at_all() -> None:
    """The link is optional (ADR-0104): production.env names it, the manifest does not."""
    environment = MANIFEST["x-backend"]["environment"]

    assert "@postgres:5432/smb_requirements" in environment["DATABASE_URL"]
    for setting in PEER_SETTINGS:
        assert setting not in environment, setting
    settings = (DEPLOY / "production.env.example").read_text(encoding="utf-8")
    for setting in PEER_SETTINGS:
        assert f"# {setting}=" in settings, setting


def test_the_peer_overlay_names_requirement_work_on_an_external_network() -> None:
    api = PEER["services"]["api"]["networks"]

    assert api["peer"]["aliases"] == ["requirement-api"]
    assert "default" in api
    assert "peer" in PEER["services"]["worker"]["networks"]
    network = PEER["networks"]["peer"]
    assert network["external"] is True
    assert network["name"] == "${PEER_NETWORK:-platform-internal}"


def test_the_knowledge_tables_drop_only_on_request() -> None:
    dropper = SERVICES["drop-knowledge-tables"]

    assert dropper["profiles"] == ["drop-knowledge-tables"]
    assert set(dropper["depends_on"]) == {"migrate"}
    # An entrypoint, not a command, so `run --rm drop-knowledge-tables --dry-run`
    # appends the flag, and the knowledge database's address, instead of
    # replacing the command.
    assert "command" not in dropper
    assert dropper["entrypoint"] == [
        "python",
        "-m",
        "smb_requirement_agent.interfaces.drop_knowledge_tables",
    ]


def test_the_edge_waits_only_for_requirement_work() -> None:
    assert SERVICES["web"]["depends_on"] == {"api": {"condition": "service_healthy"}}


def test_no_internal_route_passes_the_edge() -> None:
    block = re.search(r"location \^~ /api/internal \{(.*?)\}", EDGE, re.S)

    assert block is not None
    assert "return 404;" in block.group(1)
    assert "proxy_pass ${API_UPSTREAM}$api_request_uri;" in EDGE


def test_the_edge_proxies_nothing_of_the_knowledge_portal() -> None:
    assert "KNOWLEDGE_API_UPSTREAM" not in EDGE
    assert "KNOWLEDGE_WEB_UPSTREAM" not in EDGE
    assert "knowledge-unavailable" not in EDGE + WEB_IMAGE
    api = re.search(r"location \^~ /knowledge-api/ \{(.*?)\}", EDGE, re.S)
    assert api is not None
    assert "return 404;" in api.group(1)


def test_old_bookmarks_redirect_to_the_configured_address() -> None:
    assert re.search(r"location \^~ /knowledge/ \{", EDGE)
    assert 'set $knowledge_portal_url "${KNOWLEDGE_PORTAL_URL}";' in EDGE
    assert "return 301 $knowledge_portal_url$knowledge_bookmark;" in EDGE
    # One setting for the links and the redirect; empty leaves both out.
    web = SERVICES["web"]
    assert web["build"]["args"]["VITE_KNOWLEDGE_PORTAL_URL"] == "${KNOWLEDGE_PORTAL_URL:-}"
    assert web["environment"]["KNOWLEDGE_PORTAL_URL"] == "${KNOWLEDGE_PORTAL_URL:-}"
    assert "ARG VITE_KNOWLEDGE_PORTAL_URL=\n" in WEB_IMAGE
    assert (
        "COPY --chmod=755 deploy/web/check-knowledge-portal-url.sh "
        "/docker-entrypoint.d/10-check-knowledge-portal-url.sh" in WEB_IMAGE
    )


@pytest.mark.parametrize(
    ("url", "accepted"),
    [
        ("", True),
        ("https://knowledge.example.com/", True),
        ("https://knowledge.example.com/knowledge/", True),
        ("http://127.0.0.1:8090/knowledge/", True),
        # A bookmark's path is appended: without the slash it could name another host.
        ("https://knowledge.example.com", False),
        ("knowledge.example.com/", False),
        ("/knowledge/", False),
    ],
)
def test_the_web_image_refuses_a_redirect_address_without_a_trailing_slash(
    url: str, accepted: bool
) -> None:
    result = subprocess.run(
        ["sh", str(URL_CHECK)],
        env={**os.environ, "KNOWLEDGE_PORTAL_URL": url},
        capture_output=True,
        check=False,
    )

    assert (result.returncode == 0) is accepted, result.stderr


def test_the_realm_holds_only_requirement_work_s_entities() -> None:
    roles = [role["name"] for role in REALM["roles"]["realm"]]
    assert roles == ["architecture_reader", "architecture_maintainer"]
    groups = {item["name"]: item["realmRoles"] for item in REALM["groups"]}
    assert groups == {
        "architecture-readers": ["architecture_reader"],
        "architecture-maintainers": ["architecture_reader", "architecture_maintainer"],
    }
    clients = {client["clientId"]: client for client in REALM["clients"]}
    assert set(clients) == {"requirement-spa", "requirement-service"}

    mappers = {mapper["name"]: mapper for mapper in clients["requirement-spa"]["protocolMappers"]}
    roles_claim = mappers["realm-roles"]
    assert roles_claim["protocolMapper"] == "oidc-usermodel-realm-role-mapper"
    assert roles_claim["config"]["claim.name"] == "roles"
    assert roles_claim["config"]["access.token.claim"] == "true"
    audiences = [
        mapper["config"]["included.client.audience"]
        for mapper in mappers.values()
        if mapper["protocolMapper"] == "oidc-audience-mapper"
    ]
    assert audiences == ["requirement-api"]


def test_the_realm_defines_every_role_requirement_work_checks() -> None:
    """The roles mapping jobs check (require_reader, require_maintainer) exist."""
    source = inspect.getsource(identity)
    checked = set(re.findall(r'"(architecture_\w+)"', source))

    assert checked == {"architecture_reader", "architecture_maintainer"}
    assert checked <= {role["name"] for role in REALM["roles"]["realm"]}
    # The knowledge portal's roles are its own (ADR-0104).
    assert "knowledge_" not in source
