#!/usr/bin/env python3
"""Generate candidate Runtime Pydantic models with zero semantic post-processing."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = RUNTIME_ROOT.parent
OPENAPI_SPEC = (
    REPO_ROOT / "agent-api" / "src" / "test" / "resources"
    / "contract" / "candidate" / "openapi" / "agent-runtime-openapi.json"
)
PYTHON = sys.executable


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate candidate Runtime contracts")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def run_codegen(output: Path) -> int:
    """Invoke datamodel-code-generator; return its exact process exit code."""
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        PYTHON, "-m", "datamodel_code_generator",
        "--input", str(OPENAPI_SPEC),
        "--input-file-type", "openapi",
        "--output", str(output),
        "--output-model-type", "pydantic_v2.BaseModel",
        "--target-python-version", "3.12",
        "--snake-case-field",
        "--allow-population-by-field-name",
        "--use-schema-description",
        "--strict-nullable",
        "--use-subclass-enum",
        "--collapse-root-models",
        "--field-constraints",
    ]
    return subprocess.run(command, cwd=RUNTIME_ROOT, check=False).returncode


def compute_source_hash(spec: Path = OPENAPI_SPEC) -> str:
    """Return full SHA-256 of the exact candidate OpenAPI bytes."""
    return hashlib.sha256(spec.read_bytes()).hexdigest()


def strip_codegen_preamble(text: str) -> str:
    """Remove only datamodel-codegen's volatile leading comments/blank lines.

    This function must never rewrite classes, fields, aliases, enum values,
    unions, validators or imports.
    """
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    while lines and (not lines[0].strip() or lines[0].startswith("#")):
        lines.pop(0)
    return "".join(lines).lstrip("\n")


def add_header(text: str, source_hash: str) -> str:
    header = (
        "# Auto-generated from candidate agent-runtime OpenAPI. DO NOT EDIT.\n"
        "# Source: agent-api/src/test/resources/contract/candidate/openapi/"
        "agent-runtime-openapi.json\n"
        f"# source_sha256: {source_hash}\n"
        "# Generator: scripts/target_contract/generate_contract_models.py\n\n"
    )
    return header + strip_codegen_preamble(text).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.output.resolve()
    if not OPENAPI_SPEC.is_file():
        print(f"ERROR: candidate OpenAPI not found: {OPENAPI_SPEC}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".candidate-contract-codegen-", dir=target.parent
    ) as temp_dir:
        raw_output = Path(temp_dir) / "generated_models.py"
        result = run_codegen(raw_output)
        if result != 0:
            print("ERROR: datamodel-code-generator failed", file=sys.stderr)
            return result
        try:
            generated = raw_output.read_text(encoding="utf-8")
            final_text = add_header(generated, compute_source_hash())
            raw_output.write_text(final_text, encoding="utf-8", newline="\n")
            raw_output.replace(target)
        except OSError as exc:
            print(f"ERROR: cannot finalize generated model: {exc}", file=sys.stderr)
            return 1

    print(f"Generated candidate contract model: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
