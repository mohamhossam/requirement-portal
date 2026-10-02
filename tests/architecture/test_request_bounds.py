"""Every string and list a client can send has a declared maximum size.

The request-body ceiling (`REQUEST_MAX_BODY_BYTES`) bounds a whole request, but
not a single field inside it. Several fields reach a model prompt, so an
over-long value should be a 422 naming the field, not a provider failure or
wasted spend. The check walks the OpenAPI request bodies, so it covers every
way a bound can be declared (`Field`, `StringConstraints`, shared aliases)
and every model nested inside a body, including discriminated unions.
"""

from collections.abc import Iterator
from typing import Any

from smb_requirement_agent.interfaces.api.main import create_app

# Multipart uploads are bounded by the upload size limits, not by a schema.
UNSCHEMA_BOUND_CONTENT = {"multipart/form-data"}

# Fields of a domain value used directly as a request item. The domain bounds
# them at submission (`require_submittable_passages`, called by
# `DocumentLibrary.review`), and a request-only copy would rename the shared
# OpenAPI component the browser client is typed against.
_REVIEW = "POST /library/documents/{document_id}/versions/{version_id}/review body.passages[]"
DOMAIN_BOUNDED = {f"{_REVIEW}.block_id", f"{_REVIEW}.text", f"{_REVIEW}.exclusion_reason"}


def _resolve(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    resolved: dict[str, Any] = components[reference.rsplit("/", 1)[-1]]
    return resolved


def _unbounded(
    schema: dict[str, Any], components: dict[str, Any], path: str, seen: set[str]
) -> Iterator[str]:
    reference = schema.get("$ref")
    if reference is not None:
        if reference in seen:
            return
        seen = seen | {reference}
    schema = _resolve(schema, components)
    for key in ("anyOf", "oneOf", "allOf"):
        for option in schema.get(key, ()):
            yield from _unbounded(option, components, path, seen)
    kind = schema.get("type")
    if kind == "string":
        bounded = "maxLength" in schema or "enum" in schema or "const" in schema
        if not bounded and schema.get("format") not in {"date-time", "date", "uuid"}:
            yield path
    elif kind == "array":
        if "maxItems" not in schema:
            yield f"{path}[]"
        yield from _unbounded(schema.get("items", {}), components, f"{path}[]", seen)
    elif kind == "object" or "properties" in schema:
        for name, child in schema.get("properties", {}).items():
            yield from _unbounded(child, components, f"{path}.{name}", seen)
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict) or extra is True:
            yield f"{path}.*"


def test_every_request_string_and_list_is_bounded() -> None:
    document = create_app().openapi()
    components = document.get("components", {}).get("schemas", {})
    unbounded: list[str] = []
    for route, operations in document["paths"].items():
        for method, operation in operations.items():
            content = operation.get("requestBody", {}).get("content", {})
            for media_type, body in content.items():
                if media_type in UNSCHEMA_BOUND_CONTENT:
                    continue
                label = f"{method.upper()} {route}"
                unbounded.extend(
                    f"{label} {field}"
                    for field in _unbounded(body["schema"], components, "body", set())
                )

    unexplained = set(unbounded) - DOMAIN_BOUNDED
    assert not unexplained, "Unbounded request fields:\n" + "\n".join(sorted(unexplained))
    assert DOMAIN_BOUNDED <= set(unbounded), "A domain-bounded entry is stale."
