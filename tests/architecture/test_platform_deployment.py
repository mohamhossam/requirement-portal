"""The reference deployment runs requirement work and the knowledge service together.

ADR-0099 splits knowledge into its own service and database. These checks hold
the manifest, the edge proxy and the identity realm to that split: each service
keeps its own database, finds the other by its service name, presents and
checks the same tokens, and no browser reaches either service's /internal routes.
"""

import inspect
import json
import re
from pathlib import Path
from typing import Any

import yaml

from smb_requirement_agent.application.ports import identity

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
MANIFEST: dict[str, Any] = yaml.safe_load(
    (DEPLOY / "compose.production.yaml").read_text(encoding="utf-8")
)
SERVICES: dict[str, Any] = MANIFEST["services"]
EDGE = (DEPLOY / "web" / "default.conf.template").read_text(encoding="utf-8")
REALM: dict[str, Any] = json.loads(
    (DEPLOY / "keycloak" / "realm-requirement-ai.json").read_text(encoding="utf-8")
)
REQUIREMENT_PROCESSES = ("api", "worker", "migrate", "maintenance", "retention")
KNOWLEDGE_PROCESSES = ("knowledge-api", "knowledge-worker", "knowledge-migrate", "knowledge-import")
TOKENS = ("REQUIREMENT_SERVICE_TOKEN", "KNOWLEDGE_SERVICE_TOKEN")


def _environment(name: str) -> dict[str, str]:
    return dict(SERVICES[name]["environment"])


def test_the_project_never_collides_with_the_earlier_deployment() -> None:
    assert MANIFEST["name"] == "requirement-platform"
    built = [SERVICES[name].get("image", "") for name in ("api", "web")]
    assert all(image.startswith("requirement-platform/") for image in built)


def test_each_service_keeps_its_own_database() -> None:
    requirement = _environment("api")["DATABASE_URL"]
    knowledge = _environment("knowledge-api")["DATABASE_URL"]

    assert "@postgres:5432/smb_requirements" in requirement
    assert "@knowledge-postgres:5432/smb_knowledge" in knowledge
    assert "knowledge_postgres_data" in MANIFEST["volumes"]


def test_each_service_finds_the_other_by_name_and_shares_both_tokens() -> None:
    for name in REQUIREMENT_PROCESSES:
        environment = _environment(name)
        assert environment["KNOWLEDGE_API_BASE_URL"] == "http://knowledge-api:8000", name
        for token in TOKENS:
            assert environment[token] == f"${{{token}:?set {token}}}", (name, token)
    for name in KNOWLEDGE_PROCESSES:
        environment = _environment(name)
        assert environment["REQUIREMENT_API_BASE_URL"] == "http://api:8000", name
        assert environment["PERSISTENCE_PROVIDER"] == "postgres", name
        for token in TOKENS:
            assert environment[token] == f"${{{token}:?set {token}}}", (name, token)


def test_the_knowledge_service_runs_the_published_image_with_its_own_settings() -> None:
    for name in KNOWLEDGE_PROCESSES:
        service = SERVICES[name]
        assert service["image"].startswith("ghcr.io/mohamhossam/knowledge-api:"), name
        assert service["env_file"] == [{"path": "knowledge.env", "required": True}], name
        assert service["read_only"] is True, name
        # Model profiles come from a read-only mount, as for requirement work.
        assert service["volumes"] == MANIFEST["x-knowledge"]["volumes"], name
    (mount,) = MANIFEST["x-knowledge"]["volumes"]
    assert (mount["target"], mount["read_only"]) == ("/app/config", True)
    assert mount["bind"]["create_host_path"] is False
    assert (DEPLOY / "knowledge.env.example").is_file()
    assert SERVICES["knowledge-api"]["environment"]["API_BACKGROUND_WORKERS"] == "false"


def test_the_import_runs_only_on_request_after_both_schemas_exist() -> None:
    importer = SERVICES["knowledge-import"]

    assert importer["profiles"] == ["knowledge-import"]
    assert set(importer["depends_on"]) == {"migrate", "knowledge-migrate"}
    assert "--verify" in importer["command"]
    assert any("@postgres:5432/smb_requirements" in part for part in importer["command"])


def test_the_edge_waits_for_both_apis_and_the_portal_app() -> None:
    depends = SERVICES["web"]["depends_on"]

    assert depends["api"] == {"condition": "service_healthy"}
    assert depends["knowledge-api"] == {"condition": "service_healthy"}
    assert depends["knowledge-web"] == {"condition": "service_healthy"}


def test_the_portal_app_comes_from_the_same_release_and_learns_the_issuer_at_start() -> None:
    portal = SERVICES["knowledge-web"]

    tag = SERVICES["knowledge-api"]["image"].split(":", 1)[1]
    assert portal["image"] == f"ghcr.io/mohamhossam/knowledge-web:{tag}"
    assert portal["environment"]["CSP_IDENTITY_ORIGINS"] == "${CSP_IDENTITY_ORIGINS:-}"
    assert portal["read_only"] is True
    assert "/etc/nginx/conf.d:uid=101,gid=101" in portal["tmpfs"]
    assert "8080" in " ".join(portal["healthcheck"]["test"])


def test_no_internal_route_passes_the_edge() -> None:
    for prefix in ("/api/internal", "/knowledge-api/internal"):
        block = re.search(rf"location \^~ {re.escape(prefix)} \{{(.*?)\}}", EDGE, re.S)
        assert block is not None, prefix
        assert "return 404;" in block.group(1), prefix


def test_the_edge_proxies_each_api_and_the_knowledge_portal() -> None:
    assert "proxy_pass ${API_UPSTREAM}$api_request_uri;" in EDGE
    assert "proxy_pass ${KNOWLEDGE_API_UPSTREAM}$knowledge_api_request_uri;" in EDGE
    # Resolved per request, so the proxy starts before the portal's image exists.
    assert "proxy_pass ${KNOWLEDGE_WEB_UPSTREAM}$request_uri;" in EDGE
    assert "/knowledge-unavailable.html" in EDGE
    assert (DEPLOY / "web" / "knowledge-unavailable.html").is_file()


def test_the_realm_grants_each_role_through_a_group_and_a_roles_claim() -> None:
    roles = [role["name"] for role in REALM["roles"]["realm"]]
    assert roles == ["knowledge_admin", "knowledge_reader", "knowledge_maintainer"]
    groups = {item["name"]: item["realmRoles"] for item in REALM["groups"]}
    assert groups == {
        "knowledge-admins": ["knowledge_admin"],
        "knowledge-readers": ["knowledge_reader"],
        "knowledge-maintainers": ["knowledge_reader", "knowledge_maintainer"],
    }

    clients = {client["clientId"]: client for client in REALM["clients"]}
    for client_id, audience in (
        ("requirement-spa", "requirement-api"),
        ("knowledge-spa", "knowledge-api"),
    ):
        mappers = {mapper["name"]: mapper for mapper in clients[client_id]["protocolMappers"]}
        roles = mappers["realm-roles"]
        assert roles["protocolMapper"] == "oidc-usermodel-realm-role-mapper"
        assert roles["config"]["claim.name"] == "roles"
        assert roles["config"]["access.token.claim"] == "true"
        audiences = [
            mapper["config"]["included.client.audience"]
            for mapper in mappers.values()
            if mapper["protocolMapper"] == "oidc-audience-mapper"
        ]
        assert audiences == [audience], client_id


def test_the_knowledge_client_signs_in_only_under_its_own_path() -> None:
    client = next(item for item in REALM["clients"] if item["clientId"] == "knowledge-spa")

    assert client["publicClient"] is True
    assert client["directAccessGrantsEnabled"] is False
    assert client["implicitFlowEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert all(
        uri.startswith("${KNOWLEDGE_APP_ORIGIN}/knowledge/") for uri in client["redirectUris"]
    )


def test_the_realm_defines_every_role_requirement_work_checks() -> None:
    """The roles mapping jobs check (require_reader, require_maintainer) exist."""
    checked = set(re.findall(r'"(knowledge_\w+)"', inspect.getsource(identity)))

    assert checked == {"knowledge_reader", "knowledge_maintainer"}
    assert checked <= {role["name"] for role in REALM["roles"]["realm"]}
