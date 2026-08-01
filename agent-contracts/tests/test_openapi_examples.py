from __future__ import annotations

import copy
import json
from pathlib import Path
from collections.abc import Hashable
from typing import Any, Mapping, cast

import pytest
import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = {
    "public": ROOT / "openapi" / "agent-public-v1.yaml",
    "internal": ROOT / "openapi" / "agent-runtime-internal-v1.yaml",
}
FIXTURES = ROOT / "fixtures"


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


DOCUMENTS = {name: _load_yaml(path) for name, path in OPENAPI.items()}
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def _resolve_refs(value: object, document: Mapping[str, Any]) -> object:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            assert ref.startswith("#/components/schemas/")
            target = document["components"]["schemas"][ref.rsplit("/", 1)[1]]
            return _resolve_refs(copy.deepcopy(target), document)
        return {key: _resolve_refs(item, document) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(item, document) for item in value]
    return value


def _external_values(value: object) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        external = value.get("externalValue")
        if isinstance(external, str):
            found.append(external)
        for item in value.values():
            found.extend(_external_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_external_values(item))
    return tuple(found)


def _schema_valid(contract: str, schema_name: str, body: object) -> bool:
    document = DOCUMENTS[contract]
    schema = _resolve_refs(document["components"]["schemas"][schema_name], document)
    assert isinstance(schema, Mapping)
    validator = Draft202012Validator(schema)
    return not list(validator.iter_errors(body))


def _semantic_valid(case: Mapping[str, Any], body: Mapping[str, Any]) -> bool:
    schema_name = str(case["schema"])
    if schema_name == "AgentQueryResponse":
        status = body.get("status")
        error = body.get("error")
        result = body.get("result")
        if status in ("success", "no_result"):
            return error is None
        return error is not None and result is None
    if schema_name == "RuntimeInvokeResponse":
        status = body.get("status")
        failure = body.get("failure")
        user_result = body.get("userResult")
        if status in ("success", "no_result"):
            return failure is None
        return failure is not None and user_result is None
    if schema_name == "RuntimeInvokeRequest":
        headers = case.get("headers", {})
        assert isinstance(headers, Mapping)
        version = headers.get("X-Agent-Contract-Version")
        if not isinstance(version, str) or version not in ("1", "2"):
            return False
        return version == str(body.get("contractVersion"))
    return True


def test_openapi_documents_freeze_paths_and_strict_top_level_schemas() -> None:
    public = DOCUMENTS["public"]
    internal = DOCUMENTS["internal"]

    assert public["openapi"] == "3.1.0"
    assert set(public["paths"]) == {"/api/v1/agent/queries"}
    assert set(internal["paths"]) == {
        "/internal/v1/agent-runs:invoke",
        "/internal/health/live",
        "/internal/health/ready",
    }
    for document, names in (
        (public, ("AgentQueryRequest", "AgentQueryResponse", "FailureResponse")),
        (internal, ("RuntimeInvokeRequest", "RuntimeInvokeResponse", "RuntimeSubject", "FailureResponse")),
    ):
        for name in names:
            assert document["components"]["schemas"][name]["additionalProperties"] is False
    assert (
        internal["components"]["schemas"]["RuntimeSubject"]["properties"]["id"]["x-maxUtf8Bytes"]
        == 256
    )


@pytest.mark.parametrize("document", DOCUMENTS.values(), ids=DOCUMENTS.keys())
def test_openapi_document_is_valid_openapi_31(document: Mapping[str, Any]) -> None:
    validate(cast(Mapping[Hashable, Any], document))


@pytest.mark.parametrize("contract", DOCUMENTS)
def test_openapi_examples_reference_existing_shared_fixtures(contract: str) -> None:
    document_path = OPENAPI[contract]
    external_values = _external_values(DOCUMENTS[contract])

    assert external_values
    for external_value in external_values:
        fixture = (document_path.parent / external_value).resolve()
        assert fixture.is_relative_to(FIXTURES.resolve())
        assert fixture.is_file()
        json.loads(fixture.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda case: case["id"])
def test_shared_fixture_matches_schema_and_semantic_expectation(case: Mapping[str, Any]) -> None:
    body = json.loads((FIXTURES / case["bodyFile"]).read_text(encoding="utf-8"))

    assert _schema_valid(case["contract"], case["schema"], body) is case["expectedSchemaValid"]
    if case["expectedSchemaValid"]:
        assert _semantic_valid(case, body) is case["expectedSemanticValid"]


def test_internal_header_version_cases_have_stable_protocol_status() -> None:
    cases = {case["id"]: case for case in MANIFEST["cases"]}

    assert cases["internal-request-valid"]["expectedProtocolStatus"] == 200
    assert cases["internal-request-version-conflict"]["expectedProtocolStatus"] == 409
    assert cases["internal-request-missing-version-header"]["expectedProtocolStatus"] == 400
