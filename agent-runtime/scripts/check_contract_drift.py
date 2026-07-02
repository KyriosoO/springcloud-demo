#!/usr/bin/env python3
"""校验当前 Python 代码生成可复现性和 OpenAPI 来源。"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parent
GENERATOR = Path(__file__).resolve().parent / "generate_contract_models.py"
OPENAPI_SPEC = (
    REPO_ROOT / "agent-api" / "src" / "main" / "resources"
    / "openapi" / "agent-runtime-openapi.json"
)
PYTHON = sys.executable
HASH_PATTERN = re.compile(r"(?m)^# source_sha256: ([a-f0-9]{64})$")


def verify_source_hash(generated_text: str, spec_path: Path) -> list[str]:
    """返回精确来源校验错误；空列表表示完整哈希一致。"""
    if not spec_path.is_file():
        return [f"ERROR: OpenAPI spec not found: {spec_path}"]
    match = HASH_PATTERN.search(generated_text)
    if match is None:
        return ["ERROR: generated model has no valid source_sha256 header"]
    expected = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    if match.group(1) != expected:
        return [
            "ERROR: source hash mismatch\n"
            f"  generated: {match.group(1)}\n"
            f"  expected:  {expected}"
        ]
    return []


def generate_once(output: Path) -> int:
    completed = subprocess.run(
        [PYTHON, str(GENERATOR), "--output", str(output)],
        cwd=RUNTIME_ROOT,
        check=False,
    )
    return completed.returncode


def main() -> int:
    for required in (GENERATOR, OPENAPI_SPEC):
        if not required.is_file():
            print(f"ERROR: required file not found: {required}", file=sys.stderr)
            return 1

    with tempfile.TemporaryDirectory(prefix="active-contract-drift-") as temp_dir:
        first = Path(temp_dir) / "first.py"
        second = Path(temp_dir) / "second.py"
        for output in (first, second):
            code = generate_once(output)
            if code != 0:
                print(f"ERROR: generation failed for {output.name}", file=sys.stderr)
                return code

        try:
            first_text = first.read_text(encoding="utf-8")
            second_text = second.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot read generated model: {exc}", file=sys.stderr)
            return 1

        errors = verify_source_hash(first_text, OPENAPI_SPEC)
        errors.extend(verify_source_hash(second_text, OPENAPI_SPEC))
        if first_text != second_text:
            errors.append("ERROR: two generations from the same OpenAPI are not identical")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("OK: active Python codegen is reproducible and provenance is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
