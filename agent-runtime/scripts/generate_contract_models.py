#!/usr/bin/env python3
"""生成当前运行时模型，不做语义后处理。"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parent
OPENAPI_SPEC = (
    REPO_ROOT / "agent-api" / "src" / "main" / "resources"
    / "openapi" / "agent-runtime-openapi.json"
)
DEFAULT_OUTPUT = RUNTIME_ROOT / "app" / "contracts" / "generated_models.py"
PYTHON = sys.executable


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 active Runtime 契约")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def run_codegen(output: Path) -> int:
    """调用 datamodel-code-generator，并返回原始进程退出码。"""
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
    """返回当前 OpenAPI 原始字节的完整 SHA-256。"""
    return hashlib.sha256(spec.read_bytes()).hexdigest()


def strip_codegen_preamble(text: str) -> str:
    """仅移除 datamodel-codegen 生成的易变头部注释和空行。

    本函数绝不能改写类、字段、别名、枚举值、联合类型、校验器或导入。
    """
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    while lines and (not lines[0].strip() or lines[0].startswith("#")):
        lines.pop(0)
    return "".join(lines).lstrip("\n")


def add_header(text: str, source_hash: str) -> str:
    header = (
        "# 基于当前 agent-runtime OpenAPI 自动生成，请勿手工编辑。\n"
        "# 来源：agent-api/src/main/resources/openapi/"
        "agent-runtime-openapi.json\n"
        f"# source_sha256: {source_hash}\n"
        "# 生成器：scripts/generate_contract_models.py\n\n"
    )
    return header + strip_codegen_preamble(text).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.output.resolve()
    if not OPENAPI_SPEC.is_file():
        print(f"ERROR: active OpenAPI not found: {OPENAPI_SPEC}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".active-contract-codegen-", dir=target.parent
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

    print(f"已生成 active 契约模型：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
