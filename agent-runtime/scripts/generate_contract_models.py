from __future__ import annotations

import argparse
import importlib.metadata
import subprocess
import sys
from pathlib import Path


GENERATOR_DISTRIBUTION = "datamodel-code-generator"
GENERATOR_VERSION = "0.69.0"
GENERATOR_ARGUMENTS = (
    "--input-file-type",
    "openapi",
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--target-python-version",
    "3.12",
    "--target-pydantic-version",
    "2.12",
    "--extra-fields",
    "forbid",
    "--strict-nullable",
    "--snake-case-field",
    "--use-annotated",
    "--use-standard-collections",
    "--use-union-operator",
    "--disable-timestamp",
    "--formatters",
    "builtin",
)


def generate_models(openapi_path: Path, output_path: Path) -> None:
    actual_version = importlib.metadata.version(GENERATOR_DISTRIBUTION)
    if actual_version != GENERATOR_VERSION:
        raise RuntimeError(
            f"CONTRACT_GENERATOR_VERSION_MISMATCH: expected {GENERATOR_VERSION}, got {actual_version}"
        )
    if not openapi_path.is_file():
        raise FileNotFoundError(f"CONTRACT_SOURCE_INVALID: {openapi_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(openapi_path),
        "--output",
        str(output_path),
        *GENERATOR_ARGUMENTS,
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"CONTRACT_PYTHON_GENERATION_FAILED: {diagnostic}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate strict Pydantic models from the Agent Runtime OpenAPI")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    generate_models(args.input.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
