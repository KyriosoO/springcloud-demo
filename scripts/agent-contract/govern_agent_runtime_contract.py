from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "agent-api/src/main/resources/openapi/agent-runtime-openapi.json"
FIXTURES = ROOT / "agent-api/src/test/resources/contract/fixtures/agent-runtime/manifest.json"
PYTHON_MODELS = ROOT / "agent-runtime/src/agent_runtime/contracts/generated_models.py"
PYTHON_METADATA = ROOT / "agent-runtime/src/agent_runtime/contracts/contract_metadata.json"
PYTHON_SCHEMA = ROOT / "agent-runtime/src/agent_runtime/contracts/contract_schema.json"
LOCK = ROOT / "agent-api/src/main/resources/openapi/agent-runtime-contract.lock.json"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_single_authority() -> None:
    candidates = []
    for path in ROOT.glob("agent-*/src/main/resources/openapi/*runtime*openapi*.json"):
        if not any(part.endswith("_alpha") for part in path.parts):
            candidates.append(path.resolve())
    if candidates != [OPENAPI.resolve()]:
        names = ", ".join(path.relative_to(ROOT).as_posix() for path in candidates)
        raise RuntimeError("CONTRACT_AUTHORITY_VIOLATION: " + names)


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
        "generate-sources",
        f"-Dagent.contract.generated.output={output}",
        "--batch-mode",
        "--no-transfer-progress",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("CONTRACT_JAVA_GENERATION_FAILED: " + completed.stderr[-2000:])
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
    source = json.loads(OPENAPI.read_text(encoding="utf-8"))
    source_bytes = canonical_bytes(source)
    source_hash = sha256(source_bytes)
    fingerprint = "sha256:" + source_hash
    fixture = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for item in fixture["fixtures"]:
        content = (FIXTURES.parent / item["file"]).read_bytes()
        if sha256(content) != item["sha256"]:
            raise RuntimeError(f"CONTRACT_FIXTURE_HASH_MISMATCH: {item['file']}")

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
        "capabilities": [],
        "contractFingerprint": fingerprint,
        "contractVersion": source["info"]["version"],
        "lockFormatVersion": 1,
        "sourceSha256": source_hash,
    }
    metadata_bytes = canonical_bytes(metadata)
    lock = {
        **metadata,
        "fixtureManifestSha256": sha256(canonical_bytes(fixture)),
        "generators": {
            "java": "org.openapitools:openapi-generator-maven-plugin:7.24.0",
            "python": "datamodel-code-generator==0.69.0",
        },
        "toolchain": {
            "javaSchemaValidator": "com.networknt:json-schema-validator:2.0.4",
            "pythonBuildBackend": "setuptools==83.0.0",
            "pythonModelRuntime": "pydantic==2.13.4",
            "pythonSchemaValidator": "jsonschema==4.26.0",
        },
        "generatedArtifacts": {
            "javaModelTreeSha256": java_first,
            "pythonMetadataSha256": sha256(metadata_bytes),
            "pythonModelsSha256": sha256(first),
            "pythonSchemaSha256": sha256(schema_bytes),
        },
    }
    return {
        PYTHON_MODELS: first,
        PYTHON_METADATA: metadata_bytes,
        PYTHON_SCHEMA: schema_bytes,
        LOCK: canonical_bytes(lock),
    }


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


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
