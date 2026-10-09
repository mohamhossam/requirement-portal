"""Static safety checks for the optional Keycloak identity deployment."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_keycloak_realm_keeps_credentials_and_account_creation_at_the_broker() -> None:
    realm_text = (ROOT / "deploy/keycloak/realm-requirement-ai.json").read_text(encoding="utf-8")
    realm = json.loads(realm_text)

    assert "${env." not in realm_text
    assert realm["registrationAllowed"] is False
    assert realm["resetPasswordAllowed"] is True
    assert realm["verifyEmail"] is True
    assert realm["bruteForceProtected"] is True
    assert "users" not in realm

    client = next(item for item in realm["clients"] if item["clientId"] == "requirement-spa")
    assert client["publicClient"] is True
    assert client["standardFlowEnabled"] is True
    assert client["directAccessGrantsEnabled"] is False
    assert client["implicitFlowEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"

    broker = next(item for item in realm["identityProviders"] if item["alias"] == "company-sso")
    assert broker["providerId"] == "oidc"
    assert broker["linkOnly"] is False
    assert broker["trustEmail"] is False
    assert broker["config"]["issuer"].startswith("https://login.microsoftonline.com/")


def test_company_sso_rejects_unlinked_identities_without_creating_or_linking_users() -> None:
    realm = json.loads(
        (ROOT / "deploy/keycloak/realm-requirement-ai.json").read_text(encoding="utf-8")
    )
    broker = next(item for item in realm["identityProviders"] if item["alias"] == "company-sso")
    flow = next(
        item
        for item in realm["authenticationFlows"]
        if item["alias"] == broker["firstBrokerLoginFlowAlias"]
    )

    # Keycloak bypasses first-broker-login for an existing federated identity link.
    # Everyone else must reach only the built-in unconditional denial, including
    # an unlinked identity whose email matches an existing local account.
    assert broker["enabled"] is True
    assert broker["linkOnly"] is False
    assert flow["providerId"] == "basic-flow"
    assert flow["topLevel"] is True
    executions = flow["authenticationExecutions"]
    assert len(executions) == 1
    assert executions[0]["authenticator"] == "deny-access-authenticator"
    assert executions[0]["requirement"] == "REQUIRED"
    assert executions[0]["authenticatorFlow"] is False


def test_keycloak_compose_passes_required_admin_secrets_to_recognized_settings() -> None:
    compose = yaml.safe_load((ROOT / "deploy/keycloak/compose.yaml").read_text(encoding="utf-8"))
    environment = compose["services"]["keycloak"]["environment"]

    assert environment["KC_BOOTSTRAP_ADMIN_USERNAME"] == "${KEYCLOAK_ADMIN:?Set KEYCLOAK_ADMIN}"
    assert environment["KC_BOOTSTRAP_ADMIN_PASSWORD"] == (
        "${KEYCLOAK_ADMIN_PASSWORD:?Set KEYCLOAK_ADMIN_PASSWORD}"
    )
    assert "KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME" not in environment
    assert "KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD" not in environment


def test_keycloak_theme_covers_login_recovery_and_error_copy() -> None:
    theme = ROOT / "deploy/keycloak/themes/requirement-ai/login"
    properties = (theme / "theme.properties").read_text(encoding="utf-8")
    messages = (theme / "messages/messages_en.properties").read_text(encoding="utf-8")
    css = (theme / "resources/css/login.css").read_text(encoding="utf-8")

    assert "parent=keycloak.v2" in properties
    assert "emailForgotTitle=Reset your password" in messages
    assert "updatePasswordTitle=Choose a new password" in messages
    assert "errorTitle=" in messages
    assert "#kc-login" in css


def test_the_service_client_is_granted_tokens_for_the_knowledge_internal_api_only() -> None:
    """Requirement work's own credential (ADR-0104): no browser flows, no stored secret."""
    realm = json.loads(
        (ROOT / "deploy/keycloak/realm-requirement-ai.json").read_text(encoding="utf-8")
    )
    client = next(item for item in realm["clients"] if item["clientId"] == "requirement-service")
    assert client["publicClient"] is False
    assert client["serviceAccountsEnabled"] is True
    assert client["standardFlowEnabled"] is False
    assert client["directAccessGrantsEnabled"] is False
    assert client["implicitFlowEnabled"] is False
    assert client["fullScopeAllowed"] is False
    assert "secret" not in client
    audiences = [
        mapper["config"]["included.custom.audience"]
        for mapper in client["protocolMappers"]
        if mapper["protocolMapper"] == "oidc-audience-mapper"
    ]
    assert audiences == ["knowledge-internal"]
