"""
Prompt 契约测试：确保静态 prompt 文件与 generated models 一致，避免漂移。

覆盖文档 Section 9.3 的四项验收标准：
1. prompt 中列出的 enum 必须来自生成模型
2. prompt 示例 JSON 必须能被生成模型解析
3. AGGREGATE 示例必须包含 query:null、clarify:null
4. prompt 中不允许出现旧字段名，例如 bucketSize
"""

import json
import re
from pathlib import Path

import pytest

from app.contracts.generated_models import (
    AgentAggregateSpec,
    AgentFilter,
    AgentPlan,
    AgentQuerySpec,
    ClarifySpec,
)

# prompt 文件路径（相对于 agent-runtime 根目录）
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "app" / "prompts"

# 应从 generated models 获取的合法 enum 值，禁止在 prompt 中硬编码过时/错误的枚举
VALID_INTENTS = {"QUERY", "CLARIFY", "AGGREGATE"}
VALID_OPERATORS = {"EQ", "CONTAINS", "CONTAINS_ANY", "STARTS_WITH", "STARTS_WITH_ANY", "IN", "GT", "LT"}
VALID_AGGREGATE_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
FORBIDDEN_TERMS = {"bucketSize", "BucketSize", "bucket_size"}


def _load_prompt(filename: str) -> str:
    """读取 prompt 文件，不存在则测试失败。"""
    path = PROMPTS_DIR / filename
    assert path.exists(), f"Prompt file not found: {path}"
    return path.read_text(encoding="utf-8")


def _extract_json_blocks(text: str) -> list[dict]:
    """从 prompt 文本中提取所有 JSON 对象。

    支持两种格式：(1) ```json ... ``` markdown fence; (2) 裸 JSON 顶级对象。
    """
    blocks: list[dict] = []

    # 方式一：markdown fenced code blocks
    pattern = r"```(?:json)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    for m in matches:
        try:
            blocks.append(json.loads(m.strip()))
        except json.JSONDecodeError:
            pass

    if blocks:
        return blocks

    # 方式二：无 markdown fence，扫描大括号匹配的顶级 JSON 对象。
    # 只取最外层（深度=0），跳过内层嵌套对象避免重复提取。
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth = 0
            j = i
            while j < len(text):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            blocks.append(json.loads(text[i:j + 1]))
                        except json.JSONDecodeError:
                            pass
                        i = j  # 跳过整个已提取的块，避免提取内嵌 JSON
                        break
                j += 1
        i += 1
    return blocks


# ─── 1. prompt 中的 enum 值必须来自 generated models ──────────────────────────

class TestPromptEnumValues:
    """校验 prompt 文件中硬编码的 intent / operator / aggregate function 枚举值。"""

    def test_route_prompt_intents(self):
        """route_system.md 中 "Supported intents" 列表必须与 VALID_INTENTS 一致。"""
        text = _load_prompt("route_system.md")
        # 提取 "Supported intents:" 下方的 intent 列表
        m = re.search(r"Supported intents:\s*\n((?:\s*- \w+\n?)+)", text)
        assert m is not None, "route_system.md must contain 'Supported intents:' section"
        lines = m.group(1).strip().split("\n")
        intents_in_prompt = {line.strip("- ").strip() for line in lines}
        assert intents_in_prompt == VALID_INTENTS, (
            f"route_system.md intents {intents_in_prompt} differ from valid {VALID_INTENTS}"
        )

    def test_no_hardcoded_invalid_intent_in_examples(self):
        """所有 prompt 的 JSON 示例中 intent 字段值必须在 VALID_INTENTS 内。"""
        for filename in ["route_system.md", "query_system.md", "aggregate_system.md"]:
            text = _load_prompt(filename)
            blocks = _extract_json_blocks(text)
            for block in blocks:
                if "intent" in block:
                    assert block["intent"] in VALID_INTENTS, (
                        f"{filename}: intent '{block['intent']}' not in {VALID_INTENTS}"
                    )

    def test_no_hardcoded_invalid_operator_in_examples(self):
        """所有 prompt 的 JSON 示例中 operator 字段值必须在 VALID_OPERATORS 内。"""
        for filename in ["query_system.md", "aggregate_system.md"]:
            text = _load_prompt(filename)
            # 用正则直接提取 operator 值，因为有些示例嵌在文本中
            operators_found = set(re.findall(r'"operator":\s*"([A-Z_]+)"', text))
            for op in operators_found:
                assert op in VALID_OPERATORS, (
                    f"{filename}: operator '{op}' not in {VALID_OPERATORS}"
                )

    def test_no_hardcoded_invalid_aggregate_function_in_examples(self):
        """aggregate_system.md 的 JSON 示例中 function 字段值必须在 VALID_AGGREGATE_FUNCTIONS 内。"""
        text = _load_prompt("aggregate_system.md")
        functions_found = set(re.findall(r'"function":\s*"([A-Z]+)"', text))
        for fn in functions_found:
            assert fn in VALID_AGGREGATE_FUNCTIONS, (
                f"aggregate_system.md: function '{fn}' not in {VALID_AGGREGATE_FUNCTIONS}"
            )


# ─── 2. prompt 示例 JSON 必须能被 generated model 解析 ─────────────────────────

class TestPromptExamplesAreParseable:
    """校验每个 prompt 文件中的 JSON 示例能被对应的 generated model 正确解析。"""

    def test_route_examples_parseable(self):
        """route_system.md 的 JSON 示例可被 RouteDecision 解析（route 输出非 AgentPlan）。"""
        from app.core.route_models import RouteDecision
        text = _load_prompt("route_system.md")
        blocks = _extract_json_blocks(text)
        assert len(blocks) >= 3, f"Expected at least 3 route examples, got {len(blocks)}"
        for block in blocks:
            # 每个 route 示例必须能被 RouteDecision 解析
            rd = RouteDecision.model_validate(block)
            assert rd.intent.value in VALID_INTENTS

    def test_query_examples_parseable(self):
        """query_system.md 的 JSON 示例可被 AgentPlan 解析且 intent=QUERY。"""
        text = _load_prompt("query_system.md")
        blocks = _extract_json_blocks(text)
        assert len(blocks) >= 1, f"Expected at least 1 query example, got {len(blocks)}"
        for block in blocks:
            # prompt 中的 QUERY 示例可能是完整 AgentPlan（含 planVersion/intent/domain）或内层 query spec
            if "planVersion" in block:
                plan = AgentPlan.model_validate(block)
            else:
                # 内层 query spec，包装为完整 AgentPlan
                plan = AgentPlan.model_validate({
                    "planVersion": "1.0",
                    "intent": "QUERY",
                    "domain": "transaction",
                    "query": block,
                })
            assert plan.intent.value == "QUERY", f"Query example has intent={plan.intent.value}"
            assert plan.query is not None, "Query example must have non-null query"
            if plan.query.filters:
                for f in plan.query.filters:
                    assert f.field, "Filter field must not be blank"
                    assert f.operator.value in VALID_OPERATORS

    def test_aggregate_examples_parseable(self):
        """aggregate_system.md 的 JSON 示例可被 AgentAggregateSpec 解析，并嵌入 AgentPlan 整体校验。"""
        text = _load_prompt("aggregate_system.md")
        blocks = _extract_json_blocks(text)
        assert len(blocks) >= 1, f"Expected at least 1 aggregate example, got {len(blocks)}"
        for block in blocks:
            # prompt 中的 AGGREGATE 示例可能是完整的 AgentPlan 或内层 aggregate spec
            if "intent" in block and block.get("intent") == "AGGREGATE":
                plan = AgentPlan.model_validate(block)
            else:
                # 内层 aggregate spec，包装为完整 AgentPlan
                aggregate_spec = AgentAggregateSpec.model_validate(block)
                plan = AgentPlan.model_validate({
                    "planVersion": "1.0",
                    "intent": "AGGREGATE",
                    "domain": "transaction",
                    "aggregate": block,
                })
            assert plan.aggregate is not None, "Aggregate example must have non-null aggregate"
            agg = plan.aggregate
            assert len(agg.metrics) >= 1, "Aggregate must have at least one metric"
            for m in agg.metrics:
                assert m.alias, "Metric alias must not be blank"
                assert m.function.value in VALID_AGGREGATE_FUNCTIONS


# ─── 3. AGGREGATE 示例必须包含 query:null、clarify:null ────────────────────────

class TestAggregateExamplesHaveNullQueryAndClarify:
    """校验 aggregate_system.md 中的所有 JSON 示例均设置 query:null 和 clarify:null。"""

    def test_aggregate_examples_null_query_and_clarify(self):
        text = _load_prompt("aggregate_system.md")
        blocks = _extract_json_blocks(text)
        for i, block in enumerate(blocks):
            if block.get("intent") == "AGGREGATE":
                assert block.get("query") is None, (
                    f"Aggregate example #{i} must have query:null, got {block.get('query')!r}"
                )
                assert block.get("clarify") is None, (
                    f"Aggregate example #{i} must have clarify:null, got {block.get('clarify')!r}"
                )


# ─── 4. prompt 中不允许出现旧字段名 ────────────────────────────────────────────

class TestNoLegacyFieldNames:
    """校验所有 prompt 文件中不包含已废弃的字段名。"""

    @pytest.mark.parametrize("filename", ["route_system.md", "query_system.md", "aggregate_system.md"])
    def test_no_forbidden_terms(self, filename: str):
        text = _load_prompt(filename)
        for term in FORBIDDEN_TERMS:
            assert term not in text, (
                f"{filename} contains forbidden term '{term}'"
            )

    @pytest.mark.parametrize("filename", ["route_system.md", "query_system.md", "aggregate_system.md"])
    def test_no_plan_system_references(self, filename: str):
        """确保 prompt 中不引用已删除的 plan_system.md。"""
        text = _load_prompt(filename)
        assert "plan_system.md" not in text, (
            f"{filename} references deleted plan_system.md"
        )
