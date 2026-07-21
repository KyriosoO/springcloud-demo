from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "agent-api/src/main/resources/openapi/agent-runtime-openapi.json"
FIXTURES = ROOT / "agent-api/src/test/resources/contract/fixtures/agent-runtime/manifest.json"
PYTHON_MODELS = ROOT / "agent-runtime/src/agent_runtime/contracts/generated_models.py"
PYTHON_METADATA = ROOT / "agent-runtime/src/agent_runtime/contracts/contract_metadata.json"
PYTHON_SCHEMA = ROOT / "agent-runtime/src/agent_runtime/contracts/contract_schema.json"
LOCK = ROOT / "agent-api/src/main/resources/openapi/agent-runtime-contract.lock.json"
SOURCE_RELATIVE_PATH = "agent-api/src/main/resources/openapi/agent-runtime-openapi.json"
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
JAVA_GENERATOR_VERSION = "7.24.0"
JAVA_VALIDATOR_VERSION = "2.0.4"
PYTHON_MODEL_VERSION = "2.13.4"
PYTHON_SCHEMA_VERSION = "4.26.0"
PYTHON_BUILD_VERSION = "83.0.0"

JAVA_GENERATOR_CONFIG = {
    "failOnUnknownProperties": "true",
    "generateApiDocumentation": "false",
    "generateApiTests": "false",
    "generateApis": "false",
    "generateModelDocumentation": "false",
    "generateModelTests": "false",
    "generateModels": "true",
    "generateSupportingFiles": "false",
    "generatorName": "java",
    "hideGenerationTimestamp": "true",
    "inputSpec": "${project.basedir}/src/main/resources/openapi/agent-runtime-openapi.json",
    "legacyDiscriminatorBehavior": "false",
    "library": "restclient",
    "modelPackage": "com.dylan.baseline.agent.api.runtime.generated",
    "openApiNullable": "false",
    "output": "${agent.contract.generated.output}",
    "serializationLibrary": "jackson",
    "sourceFolder": "java",
    "useBeanValidation": "true",
    "useJakartaEe": "true",
    "useOneOfDiscriminatorLookup": "false",
    "useOneOfInterfaces": "true",
    "useSealedOneOfInterfaces": "true",
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"CONTRACT_DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def load_canonical_json(path: Path, error_code: str) -> dict[str, object]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise RuntimeError(f"{error_code}: UTF-8 without BOM and LF are required")
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"{error_code}: invalid JSON") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value):
        raise RuntimeError(f"{error_code}: canonical JSON is required")
    return value


def verify_single_authority() -> None:
    candidates = sorted(
        (
            path.resolve()
            for path in ROOT.glob("agent-*/src/main/resources/openapi/**/*")
            if path.is_file()
            and path.suffix.lower() in {".json", ".yaml", ".yml"}
            and "openapi" in path.stem.lower()
            and any(token in path.stem.lower() for token in ("runtime", "tool"))
            and not any(part.endswith("_alpha") for part in path.parts)
        ),
        key=lambda path: path.as_posix(),
    )
    if candidates != [OPENAPI.resolve()]:
        names = ", ".join(path.relative_to(ROOT).as_posix() for path in candidates)
        raise RuntimeError("CONTRACT_AUTHORITY_VIOLATION: " + names)


def validate_openapi(source: dict[str, object]) -> list[str]:
    if not str(source.get("openapi", "")).startswith("3.1."):
        raise RuntimeError("CONTRACT_SOURCE_INVALID: OpenAPI 3.1.x is required")
    info = source.get("info")
    if not isinstance(info, dict) or not SEMVER.fullmatch(str(info.get("version", ""))):
        raise RuntimeError("CONTRACT_SOURCE_INVALID: info.version must be SemVer")
    components = source.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    if not isinstance(schemas, dict) or not schemas:
        raise RuntimeError("CONTRACT_SOURCE_INVALID: components.schemas is required")

    def validate_refs(value: object) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if ref is not None:
                prefix = "#/components/schemas/"
                if not isinstance(ref, str) or not ref.startswith(prefix) or ref.removeprefix(prefix) not in schemas:
                    raise RuntimeError("CONTRACT_REMOTE_OR_UNKNOWN_REF")
            for child in value.values():
                validate_refs(child)
        elif isinstance(value, list):
            for child in value:
                validate_refs(child)

    validate_refs(source)
    capabilities: list[str] = []
    paths = source.get("paths")
    if not isinstance(paths, dict):
        raise RuntimeError("CONTRACT_SOURCE_INVALID: paths must be an object")
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise RuntimeError("CONTRACT_SOURCE_INVALID: operationId is required")
            if operation.get("x-agent-management-operation") is not True:
                capabilities.append(operation_id)
    if len(capabilities) != len(set(capabilities)):
        raise RuntimeError("CONTRACT_SOURCE_INVALID: duplicate business operationId")
    return sorted(capabilities)


def _find_dependency_version(pom_root: ET.Element, group_id: str, artifact_id: str) -> str:
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    for dependency in pom_root.findall(".//m:dependency", namespace):
        group = dependency.findtext("m:groupId", default="", namespaces=namespace)
        artifact = dependency.findtext("m:artifactId", default="", namespaces=namespace)
        if group == group_id and artifact == artifact_id:
            return dependency.findtext("m:version", default="", namespaces=namespace)
    return ""


def verify_toolchain_configuration() -> tuple[str, str]:
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    api_root = ET.parse(ROOT / "agent-api/pom.xml").getroot()
    service_root = ET.parse(ROOT / "agent-service/pom.xml").getroot()
    java_version = api_root.findtext("m:properties/m:openapi-generator.version", default="", namespaces=namespace)
    if java_version != JAVA_GENERATOR_VERSION:
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Java generator")
    if _find_dependency_version(
        service_root, "com.networknt", "json-schema-validator"
    ) != JAVA_VALIDATOR_VERSION:
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Java schema validator")

    execution = api_root.find(".//m:execution[m:id='generate-agent-runtime-contract-models']", namespace)
    if execution is None:
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Java execution missing")
    configuration = execution.find("m:configuration", namespace)
    if configuration is None:
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Java configuration missing")
    actual_config: dict[str, str] = {}
    for key in JAVA_GENERATOR_CONFIG:
        node = configuration.find(f"m:{key}", namespace)
        if node is None:
            node = configuration.find(f"m:configOptions/m:{key}", namespace)
        actual_config[key] = "" if node is None or node.text is None else node.text.strip()
    if actual_config != JAVA_GENERATOR_CONFIG:
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Java semantic parameters")
    generator_plugin = api_root.find(
        ".//m:plugin[m:groupId='org.openapitools'][m:artifactId='openapi-generator-maven-plugin']", namespace
    )
    if generator_plugin is None or generator_plugin.findtext("m:version", default="", namespaces=namespace) != "${openapi-generator.version}":
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Java plugin identity")

    pyproject = tomllib.loads((ROOT / "agent-runtime/pyproject.toml").read_text(encoding="utf-8"))
    runtime_dependencies = set(pyproject["project"]["dependencies"])
    dev_dependencies = set(pyproject["project"]["optional-dependencies"]["dev"])
    build_dependencies = set(pyproject["build-system"]["requires"])
    required_runtime = {f"pydantic=={PYTHON_MODEL_VERSION}", f"jsonschema=={PYTHON_SCHEMA_VERSION}"}
    if runtime_dependencies != required_runtime:
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Python runtime")
    if dev_dependencies != {"datamodel-code-generator==0.69.0", f"setuptools=={PYTHON_BUILD_VERSION}"}:
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Python generator")
    if build_dependencies != {f"setuptools=={PYTHON_BUILD_VERSION}"}:
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Python build backend")
    if pyproject["project"].get("requires-python") != ">=3.12,<3.13":
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Python version")
    if pyproject["build-system"].get("build-backend") != "setuptools.build_meta":
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Python build backend")
    if set(pyproject["tool"]["setuptools"]["package-data"].get("agent_runtime.contracts", [])) != {
        "contract_metadata.json",
        "contract_schema.json",
    }:
        raise RuntimeError("CONTRACT_GENERATOR_CONFIG_MISMATCH: Python package data")

    import sys

    sys.path.insert(0, str(ROOT / "agent-runtime/scripts"))
    from generate_contract_models import GENERATOR_ARGUMENTS, GENERATOR_VERSION

    if GENERATOR_VERSION != "0.69.0":
        raise RuntimeError("CONTRACT_GENERATOR_VERSION_MISMATCH: Python generator script")
    java_config_sha = sha256(canonical_bytes(actual_config))
    python_config_sha = sha256(canonical_bytes(list(GENERATOR_ARGUMENTS)))
    return java_config_sha, python_config_sha


def build_schema_bundle(source: dict[str, object]) -> dict[str, object]:
    schemas = json.loads(json.dumps(source["components"]["schemas"]))

    def rewrite(value: object) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str):
                prefix = "#/components/schemas/"
                if not ref.startswith(prefix):
                    raise RuntimeError("CONTRACT_REMOTE_OR_UNKNOWN_REF")
                value["$ref"] = "#/$defs/" + ref.removeprefix(prefix)
            for child in value.values():
                rewrite(child)
        elif isinstance(value, list):
            for child in value:
                rewrite(child)

    rewrite(schemas)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": schemas}


def validate_fixture_manifest(fixture: dict[str, object], source: dict[str, object]) -> None:
    fixture_items = fixture.get("fixtures")
    if fixture.get("formatVersion") != 1 or not isinstance(fixture_items, list) or not fixture_items:
        raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: formatVersion or fixtures")
    fixture_root = FIXTURES.parent.resolve()
    seen_ids: set[str] = set()
    compatibility_codes = {
        "FINGERPRINT_MISMATCH": "RUNTIME_CONTRACT_INCOMPATIBLE",
        "CAPABILITY_MISSING": "RUNTIME_CAPABILITY_UNAVAILABLE",
    }
    for item in fixture_items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen_ids:
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: duplicate or missing id")
        seen_ids.add(item["id"])
        if item.get("direction") != "RUNTIME_TO_JAVA" or item.get("expectation") not in {"ACCEPT", "REJECT"}:
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: direction or expectation")
        if item.get("schema") not in source["components"]["schemas"]:
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: unknown schema")
        stage = item.get("stage", "PARSE")
        if stage not in {"PARSE", "COMPATIBILITY"}:
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: unknown stage")
        if item["expectation"] == "REJECT" and not isinstance(item.get("expectedCode"), str):
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: expectedCode")
        if stage == "COMPATIBILITY":
            reason = item.get("expectedReason")
            fingerprint = item.get("expectedContractFingerprint")
            if (
                item["expectation"] != "REJECT"
                or item.get("schema") != "ContractMetadata"
                or reason not in compatibility_codes
                or item.get("expectedCode") != compatibility_codes[reason]
                or not isinstance(fingerprint, str)
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", fingerprint)
                or (reason == "CAPABILITY_MISSING" and not isinstance(item.get("requiredCapability"), str))
            ):
                raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: compatibility fields")
        fixture_path = (FIXTURES.parent / str(item.get("file", ""))).resolve()
        try:
            fixture_path.relative_to(fixture_root)
        except ValueError as exc:
            raise RuntimeError("CONTRACT_FIXTURE_PATH_INVALID") from exc
        if not fixture_path.is_file():
            raise RuntimeError("CONTRACT_FIXTURE_PATH_INVALID")
        content = fixture_path.read_bytes()
        try:
            json.loads(content, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("CONTRACT_FIXTURE_JSON_INVALID") from exc
        if not SHA256_HEX.fullmatch(str(item.get("sha256", ""))):
            raise RuntimeError("CONTRACT_FIXTURE_MANIFEST_INVALID: invalid sha256")
        if sha256(content) != item["sha256"]:
            raise RuntimeError(f"CONTRACT_FIXTURE_HASH_MISMATCH: {item['file']}")


def generate_python(output: Path) -> bytes:
    import sys

    sys.path.insert(0, str(ROOT / "agent-runtime/scripts"))
    from generate_contract_models import generate_models

    generate_models(OPENAPI, output)
    return output.read_bytes().replace(b"\r\n", b"\n")


def generate_java(output: Path) -> str:
    wrapper = ROOT / "serviceCenter" / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    command = [
        str(wrapper),
        "-f",
        str(ROOT / "serviceCenter/pom.xml"),
        "-pl",
        "../agent-api",
        "-am",
        "clean",
        "compile",
        "-DskipTests",
        f"-Dagent.contract.generated.output={output}",
        "--batch-mode",
        "--no-transfer-progress",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout)[-2000:]
        raise RuntimeError("CONTRACT_JAVA_GENERATION_FAILED: " + diagnostic)
    digest = hashlib.sha256()
    java_files = sorted(output.rglob("*.java"), key=lambda path: path.relative_to(output).as_posix())
    if not java_files:
        raise RuntimeError("CONTRACT_JAVA_GENERATION_EMPTY")
    for path in java_files:
        digest.update(path.relative_to(output).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def expected_artifacts(temp: Path) -> dict[Path, bytes]:
    verify_single_authority()
    java_config_sha, python_config_sha = verify_toolchain_configuration()
    source = load_canonical_json(OPENAPI, "CONTRACT_SOURCE_INVALID")
    capabilities = validate_openapi(source)
    source_bytes = OPENAPI.read_bytes()
    source_hash = sha256(source_bytes)
    fingerprint = "sha256:" + source_hash
    fixture = load_canonical_json(FIXTURES, "CONTRACT_FIXTURE_MANIFEST_INVALID")
    validate_fixture_manifest(fixture, source)

    first = generate_python(temp / "first.py")
    second = generate_python(temp / "second.py")
    if first != second:
        raise RuntimeError("CONTRACT_GENERATION_NON_DETERMINISTIC")
    java_first = generate_java(temp / "java-first")
    java_second = generate_java(temp / "java-second")
    if java_first != java_second:
        raise RuntimeError("CONTRACT_GENERATION_NON_DETERMINISTIC")

    schema_bytes = canonical_bytes(build_schema_bundle(source))
    metadata = {
        "capabilities": capabilities,
        "contractFingerprint": fingerprint,
        "contractVersion": source["info"]["version"],
        "lockFormatVersion": 1,
        "sourceSha256": source_hash,
    }
    metadata_bytes = canonical_bytes(metadata)
    lock = {
        **metadata,
        "fixtureManifestSha256": sha256(canonical_bytes(fixture)),
        "javaGenerator": {
            "configSha256": java_config_sha,
            "coordinate": "org.openapitools:openapi-generator-maven-plugin",
            "schemaValidator": f"com.networknt:json-schema-validator:{JAVA_VALIDATOR_VERSION}",
            "version": JAVA_GENERATOR_VERSION,
        },
        "pythonGenerator": {
            "buildBackend": f"setuptools=={PYTHON_BUILD_VERSION}",
            "configSha256": python_config_sha,
            "modelRuntime": f"pydantic=={PYTHON_MODEL_VERSION}",
            "package": "datamodel-code-generator",
            "schemaValidator": f"jsonschema=={PYTHON_SCHEMA_VERSION}",
            "version": "0.69.0",
        },
        "sourcePath": SOURCE_RELATIVE_PATH,
        "generatedArtifacts": [
            {"path": "agent-api/target/generated-sources/openapi/java", "sha256": java_first, "type": "TREE"},
            {"path": PYTHON_METADATA.relative_to(ROOT).as_posix(), "sha256": sha256(metadata_bytes), "type": "FILE"},
            {"path": PYTHON_MODELS.relative_to(ROOT).as_posix(), "sha256": sha256(first), "type": "FILE"},
            {"path": PYTHON_SCHEMA.relative_to(ROOT).as_posix(), "sha256": sha256(schema_bytes), "type": "FILE"},
        ],
    }
    return {
        PYTHON_MODELS: first,
        PYTHON_METADATA: metadata_bytes,
        PYTHON_SCHEMA: schema_bytes,
        LOCK: canonical_bytes(lock),
    }


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    if args.check and args.update:
        parser.error("--check and --update are mutually exclusive")
    with tempfile.TemporaryDirectory(prefix="agent-contract-") as directory:
        artifacts = expected_artifacts(Path(directory))
    drift = []
    for path, content in artifacts.items():
        if path.exists() and path.read_bytes().replace(b"\r\n", b"\n") == content:
            continue
        if args.update:
            atomic_write(path, content)
        else:
            drift.append(path.relative_to(ROOT).as_posix())
    if drift:
        raise SystemExit("CONTRACT_ARTIFACT_DRIFT: " + ", ".join(drift))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
