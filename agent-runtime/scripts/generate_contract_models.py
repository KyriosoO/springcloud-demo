#!/usr/bin/env python3
"""(1) Run datamodel-codegen, then (2) post-process to canonical model names and camelCase aliases."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENAPI_SPEC = ROOT.parent / "agent-api" / "src" / "main" / "resources" / "openapi" / "agent-runtime-openapi.json"
OUTPUT = ROOT / "app" / "contracts" / "generated_models.py"
PYTHON = sys.executable

# Support --output PATH override (used by drift check for temp-file generation).
_args = sys.argv[1:]
for i, a in enumerate(_args):
    if a == "--output" and i + 1 < len(_args):
        OUTPUT = Path(_args[i + 1])
    elif a.startswith("--output="):
        OUTPUT = Path(a.split("=", 1)[1])


def run_codegen() -> int:
    cmd = [
        PYTHON, "-m", "datamodel_code_generator",
        "--input", str(OPENAPI_SPEC),
        "--input-file-type", "openapi",
        "--output", str(OUTPUT),
        "--use-schema-description",
        "--strict-nullable",
        "--target-python-version", "3.12",
        "--snake-case-field",
        "--allow-population-by-field-name",
        "--output-model-type", "pydantic_v2.BaseModel",
        "--use-subclass-enum",
    ]
    return subprocess.run(cmd).returncode


# ── mapping keys ──────────────────────────────────────────────
# Canonical class name  -> set of duplicates that should be deleted (and all refs rewritten).

MERGE_ENUMS: dict[str, set[str]] = {
    "AgentIntent": {"Intent"},
    "AgentOperator": {"Operator"},
    "AgentFieldType": {"Type"},
    "AggregateFunction": {"Function", "SupportedAggregateFunction"},
    "AgentResponseType": set(),
    "AgentErrorCode": set(),
    "QueryContextMode": {"ContextMode"},
    "RuntimeRole": {"Role"},
    "RuntimeErrorResponse": set(),
    "AgentCapabilityExecutionMode": {"ExecutionMode"},
    "AgentCapabilityRiskLevel": {"RiskLevel"},
}

# Canonical class name -> camelCase alias map for property names (snake→camel).
# Only needed for fields where the alias differs from the camelCase derived from the property name.

CAMEL_OVERRIDES: dict[str, dict[str, str]] = {
    "AggregateMetricSpec": {},
    "AggregateOrderSpec": {},
    "AgentAggregateSpec": {
        "group_by_fields": "groupByFields",
        "order_by": "orderBy",
        "max_rows": "maxRows",
    },
    "AgentPlan": {
        "plan_version": "planVersion",
    },
    "AgentQuerySpec": {
        "context_mode": "contextMode",
        "remove_fields": "removeFields",
        "select_fields": "selectFields",
    },
    "PlanGenerateRequest": {
        "request_id": "requestId",
        "domain_schemas": "domainSchemas",
        "recent_turns": "recentTurns",
        "previous_query": "previousQuery",
    },
    "PlanGenerateResponse": {
        "request_id": "requestId",
    },
    "RuntimeDomainSchema": {
        "default_select_fields": "defaultSelectFields",
        "default_size": "defaultSize",
        "max_filters": "maxFilters",
        "max_result_window": "maxResultWindow",
        "max_size": "maxSize",
    },
    "RuntimeFieldSchema": {
        "format_hint": "formatHint",
        "supported_aggregate_functions": "supportedAggregateFunctions",
    },
    "RuntimeQueryContext": {
        "source_turn_id": "sourceTurnId",
        "select_fields": "selectFields",
    },
    "RuntimeErrorResponse": {
        "request_id": "requestId",
    },
}


def aliasify_model_block(text: str, class_name: str) -> str:
    """Patch a Pydantic model block: fix alias names for camelCase."""
    overrides = CAMEL_OVERRIDES.get(class_name, {})
    for snake, camel in overrides.items():
        text = re.sub(
            rf'alias="{snake}"',
            f'alias="{camel}"',
            text,
        )
    return text


def merge_duplicate_enums(text: str) -> str:
    """Remove duplicate enum classes and fix references to use canonical names."""
    # 1. Collect all canonical names that have duplicates to process
    for canonical, duplicates in MERGE_ENUMS.items():
        if not duplicates:
            continue
        # 2. Search for "class DuplicateName(Enum):" blocks and remove them
        for dup in duplicates:
            # Remove the entire enum definition block
            pattern = rf'\n\nclass {dup}\(Enum\):.*?(?=\n\nclass |\n\n[#]|\Z)'
            text = re.sub(pattern, '', text, flags=re.DOTALL)

    # 3. Fix references to use canonical names
    name_map: dict[str, str] = {}
    for canonical, duplicates in MERGE_ENUMS.items():
        for dup in duplicates:
            name_map[dup] = canonical

    for dup, canonical in name_map.items():
        # Fix type hints: "field: Dup" -> "field: Canonical"
        text = re.sub(rf'\b{dup}\b', canonical, text)

    return text


def fix_alias_patterns(text: str) -> str:
    """Apply alias fixes to each model block."""
    for class_name in CAMEL_OVERRIDES:
        # Find the class block and patch it
        pattern = rf'(class {class_name}\(BaseModel\):.*?(?=\n\nclass |\n\n[#]|\Z))'
        def _patcher(m: re.Match, cn: str = class_name) -> str:
            return aliasify_model_block(m.group(1), cn)
        text = re.sub(pattern, _patcher, text, flags=re.DOTALL)
    return text


def remove_root_model_wrappers(text: str) -> str:
    """Remove GroupByField(RootModel) wrapper. Flatten into simple Optional[str]."""
    text = re.sub(
        r'\n\nclass GroupByField\(RootModel\[.*?\]\):.*?(?=\n\nclass )',
        '',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r'Optional\[GroupByField\]', 'Optional[str]', text)
    return text


def deduplicate_aliased_enums(text: str) -> str:
    """AgentIntent, et al. each appear twice (once standalone, once from a $ref alias).
    deduplicate_aliased_enums keeps only the first occurrence and removes the second."""
    seen: set[str] = set()
    lines = text.split('\n')
    result: list[str] = []
    skip_until_next_class = False
    for i, line in enumerate(lines):
        m = re.match(r'^class (\w+)\(.*Enum.*\):', line)
        if m:
            name = m.group(1)
            if name in seen:
                skip_until_next_class = True
                continue
            seen.add(name)
        if skip_until_next_class:
            if line.strip() == '' and i + 1 < len(lines) and lines[i + 1].startswith('class '):
                skip_until_next_class = False
                result.append(line)
            continue
        result.append(line)
    return '\n'.join(result)


def add_header(text: str) -> str:
    header = (
        '# Auto-generated from agent-api OpenAPI spec. DO NOT EDIT.\n'
        '# Source: agent-api/src/main/resources/openapi/agent-runtime-openapi.json\n'
        '# Regenerate: cd agent-runtime && python scripts/generate_contract_models.py\n'
    )
    # Remove the file-level docstring the codegen adds
    if text.startswith('"""'):
        text = re.sub(r'^""".*?"""\n', '', text, flags=re.DOTALL)
    if text.startswith('#'):
        # Remove the codegen timestamp comment
        while text.startswith('#'):
            nl = text.index('\n')
            text = text[nl + 1:]
    return header + '\n' + text


def add_upper_enum_aliases(text: str) -> str:
    """Add .UPPER aliases for str-subclass Enums for backwards compat."""
    upper_map: dict[str, dict[str, str]] = {
        "AgentIntent": {"QUERY": "query", "CLARIFY": "clarify", "AGGREGATE": "aggregate"},
        "AgentOperator": {"EQ": "eq", "CONTAINS": "contains", "CONTAINS_ANY": "contains_any",
                          "STARTS_WITH": "starts_with", "STARTS_WITH_ANY": "starts_with_any",
                          "IN": "in_", "GT": "gt", "LT": "lt"},
        "AgentFieldType": {"STRING": "string", "DECIMAL": "decimal", "INSTANT": "instant"},
        "AggregateFunction": {"COUNT": "count", "SUM": "sum", "AVG": "avg", "MIN": "min", "MAX": "max"},
        "AgentResponseType": {"RESULT": "result", "CLARIFY": "clarify",
                              "AGGREGATE_RESULT": "aggregate_result", "ERROR": "error"},
        "QueryContextMode": {"REPLACE": "replace", "MERGE": "merge"},
        "RuntimeRole": {"USER": "user", "ASSISTANT": "assistant"},
    }

    for class_name, aliases in upper_map.items():
        # Find the class body and inject UPPER aliases after each member line
        pattern = rf'(class {class_name}\(str, Enum\):\n.*?)(?=\nclass |\n\n[#]|\Z)'
        def _inject(m: re.Match, cn: str = class_name, al: dict[str, str] = aliases) -> str:
            block = m.group(1)
            lines = block.split('\n')
            new_lines: list[str] = []
            for line in lines:
                new_lines.append(line)
                m2 = re.match(r'^\s*(\w+)\s*=\s*[\'\"]([A-Z_]+)[\'\"]', line)
                if m2:
                    member_lower = m2.group(1)
                    val = m2.group(2)
                    # If this member has an UPPER alias, inject after it
                    for upper, lower in al.items():
                        if lower == member_lower:
                            new_lines.append(f'    {upper} = {lower}  # noqa: E221')
                            break
            return '\n'.join(new_lines)
        text = re.sub(pattern, _inject, text, flags=re.DOTALL)
    return text


def post_process(text: str) -> str:
    text = merge_duplicate_enums(text)
    text = deduplicate_aliased_enums(text)
    text = remove_root_model_wrappers(text)
    text = fix_alias_patterns(text)
    text = add_upper_enum_aliases(text)
    text = add_header(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def main() -> int:
    if not OPENAPI_SPEC.exists():
        print(f"OpenAPI spec not found: {OPENAPI_SPEC}")
        print("Run 'mvn -pl ../agent-api -am -Dagent.contract.update=true test' first.")
        return 1

    rc = run_codegen()
    if rc != 0:
        print("datamodel-codegen failed")
        return rc

    raw = OUTPUT.read_text(encoding="utf-8")
    processed = post_process(raw)
    OUTPUT.write_text(processed, encoding="utf-8")
    print(f"Generated and post-processed: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
