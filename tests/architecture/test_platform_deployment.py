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
    (DEPLOY / "compose.demo.yaml").read_text(encoding="utf-8"),
    Loader=_ComposeLoader,  # noqa: S506 - a SafeLoader subclass
)
SERVICES: dict[str, Any] = MANIFEST["services"]
EDGE = (DEPLOY / "web" / "default.conf.template").read_text(encoding="utf-8")
WEB_IMAGE = (DEPLOY / "web" / "Dockerfile").read_text(encoding="utf-8")
URL_CHECK = DEPLOY / "web" / "check-knowledge-portal-url.sh"
RENDER_INDEX = DEPLOY / "web" / "render-index.sh"
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


def test_the_database_connection_ceiling_is_set_and_documented() -> None:
    """Pools and one-shot commands are sized against it (production hardening PR 3)."""
    assert SERVICES["postgres"]["command"] == [
        "postgres",
        "-c",
        "max_connections=${POSTGRES_MAX_CONNECTIONS:-200}",
    ]
    guide = (ROOT / "docs" / "operations" / "deployment.md").read_text(encoding="utf-8")
    assert "POSTGRES_MAX_CONNECTIONS" in guide


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


def test_the_edge_limits_each_client_address_and_answers_in_the_api_error_shape() -> None:
    """Per-address limits at the edge, behind a trusted TLS proxy only (ADR-0106)."""
    api = re.search(r"location /api/ \{(.*?)\n    \}", EDGE, re.S)
    preview = re.search(
        r"location ~ \^/api/requirements/\[\^/\]\+/impact-preview\$ \{(.*?)\n        \}",
        EDGE,
        re.S,
    )
    reports = re.search(r"location = /api/client-errors \{(.*?)\n        \}", EDGE, re.S)
    refusal = re.search(r"location @edge_rate_limited \{(.*?)\n    \}", EDGE, re.S)

    assert "set_real_ip_from ${TRUSTED_PROXY_CIDR};" in EDGE
    assert "real_ip_header X-Forwarded-For;" in EDGE
    assert "rate=${EDGE_RATE_PER_SECOND}r/s" in EDGE
    assert api is not None and preview is not None and refusal is not None
    assert "limit_req zone=api_per_address burst=${EDGE_BURST} nodelay;" in api.group(1)
    assert "error_page 429 = @edge_rate_limited;" in api.group(1)
    # A nested location replaces its parent's limits, so it names both.
    assert "zone=api_per_address" in preview.group(1)
    assert "zone=impact_preview_per_address" in preview.group(1)
    # Public browser error reports (PR 12): the strictest budget, and a tiny body.
    assert "zone=client_errors_per_address:1m rate=1r/s" in EDGE
    assert reports is not None
    assert "zone=api_per_address" in reports.group(1)
    assert "zone=client_errors_per_address burst=10 nodelay" in reports.group(1)
    assert "client_max_body_size 1k;" in reports.group(1)
    assert '"code":"edge_rate_limited"' in refusal.group(1)
    assert "Retry-After" in refusal.group(1)
    for setting, default in (
        ("TRUSTED_PROXY_CIDR", "127.0.0.1/32"),
        ("EDGE_RATE_PER_SECOND", "50"),
        ("EDGE_BURST", "100"),
    ):
        assert f"{setting}={default}" in WEB_IMAGE
        assert SERVICES["web"]["environment"][setting] == f"${{{setting}:-{default}}}"


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
    assert demo["web"] == {
        "environment": {"IDENTITY_PROVIDER": "fake"},
        "ports": {"!override": ["127.0.0.1:${WEB_PORT:-8080}:8080"]},
    }


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
    # One setting for the links and the redirect, read when the container starts;
    # empty leaves both out.
    web = SERVICES["web"]
    assert "args" not in web["build"]
    assert web["environment"]["KNOWLEDGE_PORTAL_URL"] == "${KNOWLEDGE_PORTAL_URL:-}"
    assert "VITE_KNOWLEDGE_PORTAL" not in WEB_IMAGE
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
    result = subprocess.run(  # noqa: S603 - the repository's own script
        ["sh", str(URL_CHECK)],  # noqa: S607 - the repository's own script
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


def test_every_container_rotates_its_logs_and_has_resource_limits() -> None:
    """Production hardening PR 10: one runaway container cannot fill the disk or starve the host."""
    for name, service in SERVICES.items():
        assert service["logging"] == {
            "driver": "json-file",
            "options": {"max-size": "10m", "max-file": "5"},
        }, name
        assert service.get("mem_limit") and service.get("cpus") and service.get("pids_limit"), name
    # The alerts compare memory against these defaults (docs/operations/alerts.md).
    assert SERVICES["api"]["mem_limit"] == "${API_MEM_LIMIT:-2g}"
    assert SERVICES["worker"]["mem_limit"] == "${WORKER_MEM_LIMIT:-3g}"


def test_the_scanner_and_the_worker_report_their_health() -> None:
    assert SERVICES["clamav"]["healthcheck"]["test"] == ["CMD", "clamdcheck.sh"]
    probe = " ".join(SERVICES["worker"]["healthcheck"]["test"])
    assert "9464/metrics" in probe and "smb_ready 1.0" in probe


def test_the_api_trusts_forwarded_headers_from_its_own_network_only() -> None:
    subnet = "${REQUIREMENT_SUBNET:-172.30.80.0/24}"
    assert MANIFEST["networks"]["default"]["ipam"]["config"] == [{"subnet": subnet}]
    assert f"--forwarded-allow-ips={subnet}" in SERVICES["api"]["command"]
    assert not any("allow-ips=*" in part for part in SERVICES["api"]["command"])


def test_a_managed_database_replaces_the_bundled_one_by_its_url() -> None:
    url = MANIFEST["x-backend"]["environment"]["DATABASE_URL"]
    assert url.startswith("${DATABASE_URL:-postgresql://smb:")
    assert "sslmode=${DATABASE_SSLMODE:-prefer}" in url


def test_the_edge_forwards_the_original_scheme_and_sends_hsts_over_https_only() -> None:
    headers = (DEPLOY / "web" / "security-headers.conf").read_text(encoding="utf-8")
    assert "proxy_set_header X-Forwarded-Proto $forwarded_scheme;" in EDGE
    assert "proxy_set_header X-Forwarded-Proto $scheme;" not in EDGE
    # Only the trusted TLS proxy may say the browser used HTTPS.
    assert "geo $realip_remote_addr $from_trusted_proxy" in EDGE
    assert '"1:https" https;' in EDGE
    assert 'https "max-age=31536000";' in EDGE
    assert "add_header Strict-Transport-Security $strict_transport_security always;" in headers


def test_one_web_image_takes_its_deployment_values_when_it_starts() -> None:
    """The issuer origins and portal link are rendered at start (production hardening PR 12)."""
    web = SERVICES["web"]

    assert "ENV VITE_API_BASE=$VITE_API_BASE \\\n    WEB_RUNTIME_CONFIG=true" in WEB_IMAGE
    assert "ARG CSP_IDENTITY_ORIGINS" not in WEB_IMAGE
    assert (
        "COPY --chmod=755 deploy/web/render-index.sh /docker-entrypoint.d/30-render-index.sh"
        in WEB_IMAGE
    )
    assert web["environment"]["IDENTITY_PROVIDER"] == "oidc"
    assert web["environment"]["CSP_IDENTITY_ORIGINS"] == "${CSP_IDENTITY_ORIGINS:-}"
    assert web["environment"]["KNOWLEDGE_PORTAL_ROLE"] == "${KNOWLEDGE_PORTAL_ROLE-knowledge_admin}"
    assert "/run/web:uid=101,gid=101" in web["tmpfs"]
    page = re.search(r"location = /index.html \{(.*?)\n    \}", EDGE, re.S)
    assert page is not None
    assert "root /run/web;" in page.group(1)
    assert 'add_header Cache-Control "no-cache" always;' in page.group(1)
    assert "security-headers.conf" in page.group(1)


_PAGE = (
    "<html><head>"
    '<meta http-equiv="Content-Security-Policy" content="connect-src \'self\' '
    '__CSP_IDENTITY_ORIGINS__; frame-src blob: __CSP_IDENTITY_ORIGINS__" />'
    '<meta name="knowledge-portal-url" content="__KNOWLEDGE_PORTAL_URL__" />'
    '<meta name="knowledge-portal-role" content="__KNOWLEDGE_PORTAL_ROLE__" />'
    "</head></html>"
)


def _render(tmp_path: Path, **environment: str) -> tuple[subprocess.CompletedProcess[str], str]:
    source, target = tmp_path / "source.html", tmp_path / "index.html"
    source.write_text(_PAGE, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - the repository's own script
        ["sh", str(RENDER_INDEX)],  # noqa: S607 - the repository's own script
        env={
            "PATH": os.environ["PATH"],
            "RENDER_INDEX_SOURCE": str(source),
            "RENDER_INDEX_TARGET": str(target),
            **environment,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, target.read_text(encoding="utf-8") if target.exists() else ""


def test_the_page_names_the_deployment_issuer_and_portal(tmp_path: Path) -> None:
    result, page = _render(
        tmp_path,
        CSP_IDENTITY_ORIGINS="https://login.example.com https://sso.example.com:8443/",
        KNOWLEDGE_PORTAL_URL="https://knowledge.example.com/",
        KNOWLEDGE_PORTAL_ROLE="curators",
    )

    assert result.returncode == 0, result.stderr
    origins = "https://login.example.com https://sso.example.com:8443"
    assert f"connect-src 'self' {origins}; frame-src blob: {origins}\"" in page
    assert 'name="knowledge-portal-url" content="https://knowledge.example.com/"' in page
    assert 'name="knowledge-portal-role" content="curators"' in page
    assert "__" not in page


def test_the_demo_page_needs_no_issuer_and_keeps_the_default_role(tmp_path: Path) -> None:
    result, page = _render(tmp_path, IDENTITY_PROVIDER="fake")

    assert result.returncode == 0, result.stderr
    assert "connect-src 'self'; frame-src blob:\"" in page
    assert 'name="knowledge-portal-url" content=""' in page
    assert 'name="knowledge-portal-role" content="knowledge_admin"' in page


@pytest.mark.parametrize(
    ("environment", "refusal"),
    [
        # Under OIDC the browser could not reach the issuer: refuse to start.
        ({}, "must name the OIDC issuer origin"),
        ({"IDENTITY_PROVIDER": "oidc", "CSP_IDENTITY_ORIGINS": " "}, "must name the OIDC issuer"),
        ({"CSP_IDENTITY_ORIGINS": "https://login.example.com/realms/x"}, "without a path"),
        ({"CSP_IDENTITY_ORIGINS": "login.example.com"}, "without a path"),
        ({"CSP_IDENTITY_ORIGINS": 'https://a.example.com" onload="x'}, "without a path"),
        ({"CSP_IDENTITY_ORIGINS": "https://a.example.com|b"}, "without a path"),
        ({"CSP_IDENTITY_ORIGINS": "https://*.example.com"}, "without a path"),
        (
            {"CSP_IDENTITY_ORIGINS": "https://login.example.com", "KNOWLEDGE_PORTAL_URL": "x/"},
            "KNOWLEDGE_PORTAL_URL",
        ),
        (
            {
                "CSP_IDENTITY_ORIGINS": "https://login.example.com",
                "KNOWLEDGE_PORTAL_URL": 'https://k.example.com/"/',
            },
            "KNOWLEDGE_PORTAL_URL",
        ),
        (
            {
                "CSP_IDENTITY_ORIGINS": "https://login.example.com",
                "KNOWLEDGE_PORTAL_URL": "https://k.example.com/\n<script>/",
            },
            "KNOWLEDGE_PORTAL_URL",
        ),
        (
            {"CSP_IDENTITY_ORIGINS": "https://login.example.com", "KNOWLEDGE_PORTAL_ROLE": "a b"},
            "KNOWLEDGE_PORTAL_ROLE",
        ),
        (
            {"CSP_IDENTITY_ORIGINS": "https://login.example.com", "KNOWLEDGE_PORTAL_ROLE": "a\nb"},
            "KNOWLEDGE_PORTAL_ROLE",
        ),
        (
            {"CSP_IDENTITY_ORIGINS": "https://login.example.com", "KNOWLEDGE_PORTAL_ROLE": "a&b"},
            "KNOWLEDGE_PORTAL_ROLE",
        ),
    ],
)
def test_the_page_refuses_values_that_could_break_it(
    tmp_path: Path, environment: dict[str, str], refusal: str
) -> None:
    result, page = _render(tmp_path, **environment)

    assert result.returncode == 1
    assert refusal in result.stderr
    assert page == ""
