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
from smb_requirement_agent.interfaces.api import serve

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
MANIFEST: dict[str, Any] = yaml.safe_load(
    (DEPLOY / "compose.production.yaml").read_text(encoding="utf-8")
)
PEER: dict[str, Any] = yaml.safe_load((DEPLOY / "compose.peer.yaml").read_text(encoding="utf-8"))


class _ComposeLoader(yaml.SafeLoader):
    """SafeLoader that also reads Compose's `!override` tag (replace, do not merge)."""


def _override(loader: yaml.SafeLoader, node: yaml.Node) -> dict[str, Any]:
    assert isinstance(node, yaml.SequenceNode)
    return {"!override": loader.construct_sequence(node)}


_ComposeLoader.add_constructor("!override", _override)
DEMO: dict[str, Any] = yaml.load(
    (DEPLOY / "compose.demo.yaml").read_text(encoding="utf-8"), Loader=_ComposeLoader
)
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
    assert built == [
        "${REQUIREMENT_API_IMAGE:-requirement-platform/api}:${IMAGE_TAG:-local}",
        "${REQUIREMENT_WEB_IMAGE:-requirement-platform/web}:${IMAGE_TAG:-local}",
    ]


def test_a_release_deploys_by_tag_and_a_backup_is_one_command_away() -> None:
    """Published images replace the local build by name and tag (ADR-0108)."""
    backup = SERVICES["backup"]
    postgres = SERVICES["postgres"]

    assert backup["image"] == postgres["image"]
    assert backup["profiles"] == ["backup"]
    assert backup["restart"] == "no"
    assert backup["volumes"] == ["backups:/backups"]
    script = backup["command"][0]
    assert "pg_dump --format=custom" in script
    assert "--dbname=smb_requirements" in script
    # A dump is visible under its final name only once it is complete.
    assert '"$$target.partial"' in script and 'mv "$$target.partial" "$$target"' in script
    assert backup["environment"]["BACKUP_RETENTION_DAYS"] == "${BACKUP_RETENTION_DAYS:-14}"


def test_nothing_of_the_knowledge_portal_runs_here() -> None:
    assert not [name for name in SERVICES if name.startswith("knowledge")]
    assert "x-knowledge" not in MANIFEST
    assert set(MANIFEST["volumes"]) == {"postgres_data", "clamav_data", "backups"}
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


def test_the_edge_waits_only_for_requirement_work() -> None:
    assert SERVICES["web"]["depends_on"] == {"api": {"condition": "service_healthy"}}


def test_the_api_drains_in_flight_requests_and_the_edge_reports_its_health() -> None:
    assert SERVICES["api"]["stop_grace_period"] == "30s"
    assert serve.GRACEFUL_SHUTDOWN_SECONDS < 30
    assert SERVICES["web"]["healthcheck"]["test"][:2] == ["CMD", "wget"]


def test_no_api_request_waits_on_a_model_at_the_edge() -> None:
    """Model work runs as jobs (ADR-0105), so the edge holds a request a minute at most."""
    block = re.search(r"location /api/ \{(.*?)\n    \}", EDGE, re.S)

    assert block is not None
    assert "proxy_read_timeout 60s;" in block.group(1)
    assert "proxy_send_timeout 60s;" in block.group(1)


def test_no_internal_route_passes_the_edge() -> None:
    block = re.search(r"location \^~ /api/internal \{(.*?)\}", EDGE, re.S)

    assert block is not None
    assert "return 404;" in block.group(1)
    assert "proxy_pass ${API_UPSTREAM}$api_request_uri;" in EDGE


@pytest.mark.parametrize(
    "location",
    ["location ^~ /api/docs {", "location = /api/redoc {", "location = /api/openapi.json {"],
)
def test_the_api_documentation_is_not_served_at_the_edge(location: str) -> None:
    block = re.search(re.escape(location) + r"(.*?)\}", EDGE, re.S)

    assert block is not None, location
    assert "return 404;" in block.group(1)


BACKEND_PROCESSES = ("migrate", "maintenance", "retention", "api", "worker")


def test_the_manifest_always_runs_production_with_real_sign_in() -> None:
    """Set in the manifest, not production.env, so a missing line fails closed."""
    environment = MANIFEST["x-backend"]["environment"]

    assert environment["APP_ENV"] == "production"
    assert environment["IDENTITY_PROVIDER"] == "oidc"
    for name in BACKEND_PROCESSES:
        assert SERVICES[name]["environment"]["APP_ENV"] == "production", name
        assert SERVICES[name]["environment"]["IDENTITY_PROVIDER"] == "oidc", name


def test_the_demo_overlay_keeps_development_personas_on_this_machine() -> None:
    demo = DEMO["services"]

    assert set(demo) == {*BACKEND_PROCESSES, "web"}
    for name in BACKEND_PROCESSES:
        assert demo[name] == {
            "environment": {"APP_ENV": "development", "IDENTITY_PROVIDER": "fake"}
        }, name
    assert demo["web"] == {"ports": {"!override": ["127.0.0.1:${WEB_PORT:-8080}:8080"]}}


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
    assert roles == ["architecture_maintainer"]
    groups = {item["name"]: item["realmRoles"] for item in REALM["groups"]}
    assert groups == {"architecture-maintainers": ["architecture_maintainer"]}
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
    """The role mapping jobs check (require_maintainer) exists."""
    source = inspect.getsource(identity)
    checked = set(re.findall(r'"(architecture_\w+)"', source))

    assert checked == {"architecture_maintainer"}
    assert checked <= {role["name"] for role in REALM["roles"]["realm"]}
    # The knowledge portal's roles are its own (ADR-0104).
    assert "knowledge_" not in source
