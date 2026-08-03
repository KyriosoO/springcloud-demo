from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityKind, JsonObject


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionPocCase:
    case_id: str
    question: str
    expected_capability_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerPocCase:
    case_id: str
    question: str
    safe_payload: JsonObject
    required_fact_ids: frozenset[str]
    required_answer_fragments: tuple[str, ...]


def action_descriptors() -> tuple[CapabilityDescriptor, ...]:
    empty_schema: JsonObject = {
        "type": "object",
        "properties": {},
        "required": (),
        "additionalProperties": False,
    }
    knowledge_schema: JsonObject = {
        "type": "object",
        "properties": {"question": {"type": "string", "minLength": 1, "maxLength": 256}},
        "required": ("question",),
        "additionalProperties": False,
    }
    return (
        CapabilityDescriptor(
            capability_id="knowledge.query",
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Public tax knowledge query",
            description="Answer a public tax law, regulation, policy, invoice, or filing knowledge question.",
            aliases=(),
            argument_schema=knowledge_schema,
        ),
        CapabilityDescriptor(
            capability_id="employee.query",
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Employee query metadata",
            description="Describe supported employee list or query fields and conditions; never reads a person record.",
            aliases=(),
            argument_schema=empty_schema,
        ),
        CapabilityDescriptor(
            capability_id="transaction.query",
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Transaction query metadata",
            description="Describe supported transaction search fields and conditions; never reads a transaction record.",
            aliases=(),
            argument_schema=empty_schema,
        ),
    )


ACTION_CASES: tuple[ActionPocCase, ...] = (
    ActionPocCase(case_id="tax_policy_scope", question="增值税政策适用范围是什么？", expected_capability_id="knowledge.query"),
    ActionPocCase(case_id="tax_invoice_rule", question="发票管理法规有哪些基本要求？", expected_capability_id="knowledge.query"),
    ActionPocCase(case_id="tax_filing_rule", question="纳税申报政策的一般原则是什么？", expected_capability_id="knowledge.query"),
    ActionPocCase(case_id="tax_law_hierarchy", question="税收法律和行政法规的关系是什么？", expected_capability_id="knowledge.query"),
    ActionPocCase(case_id="employee_conditions", question="员工查询支持哪些条件？", expected_capability_id="employee.query"),
    ActionPocCase(case_id="employee_fields", question="员工列表允许哪些字段？", expected_capability_id="employee.query"),
    ActionPocCase(case_id="employee_filters", question="员工查询有哪些筛选项？", expected_capability_id="employee.query"),
    ActionPocCase(case_id="transaction_conditions", question="交易查询支持哪些条件？", expected_capability_id="transaction.query"),
    ActionPocCase(case_id="transaction_fields", question="交易记录允许哪些字段？", expected_capability_id="transaction.query"),
    ActionPocCase(case_id="transaction_filters", question="交易查询有哪些筛选项？", expected_capability_id="transaction.query"),
)


ANSWER_CASES: tuple[AnswerPocCase, ...] = (
    AnswerPocCase(
        case_id="answer_text_fact",
        question="税务政策中的合成申报规则是什么？",
        safe_payload={
            "schema_version": 1,
            "facts": ({"fact_id": "fact-text", "text": "合成申报规则为按期提交。"},),
        },
        required_fact_ids=frozenset({"fact-text"}),
        required_answer_fragments=("按期提交",),
    ),
    AnswerPocCase(
        case_id="answer_numeric_status",
        question="税务政策中的合成税率和状态是什么？",
        safe_payload={
            "schema_version": 1,
            "facts": ({"fact_id": "fact-number", "text": "合成税率为7%，状态为有效。"},),
        },
        required_fact_ids=frozenset({"fact-number"}),
        required_answer_fragments=("7%", "有效"),
    ),
    AnswerPocCase(
        case_id="answer_coverage",
        question="税务政策中的合成申报范围和截止规则是什么？",
        safe_payload={
            "schema_version": 1,
            "facts": (
                {"fact_id": "fact-scope", "text": "合成申报范围为甲类事项。"},
                {"fact_id": "fact-deadline", "text": "合成截止规则为每月第十日。"},
            ),
        },
        required_fact_ids=frozenset({"fact-scope", "fact-deadline"}),
        required_answer_fragments=("甲类事项", "每月第十日"),
    ),
)
