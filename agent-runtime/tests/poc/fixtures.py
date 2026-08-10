from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.capability_api.contracts import CapabilityDescriptor, JsonObject
from agent_runtime.knowledge.provider import knowledge_query_descriptor


class ActionPocCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    question: str = Field(min_length=1, max_length=256)
    expected_capability_id: Literal[
        "knowledge.query",
        "employee.detail",
        "transaction.search",
        "agent_unsupported",
    ]


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerPocCase:
    case_id: str
    question: str
    safe_payload: JsonObject
    required_fact_ids: frozenset[str]
    required_answer_fragments: tuple[str, ...]


def action_descriptors() -> tuple[CapabilityDescriptor, ...]:
    return (
        knowledge_query_descriptor(),
        employee_detail_definition().descriptor,
        transaction_search_definition().descriptor,
    )


ACTION_FIXTURE_PATH = Path(__file__).with_name("fixtures") / "action_selection_v4.json"


class _DuplicateFixtureKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateFixtureKey
        result[key] = value
    return result


def load_action_cases(path: Path = ACTION_FIXTURE_PATH) -> tuple[ActionPocCase, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except _DuplicateFixtureKey as exc:
        raise ValueError("poc.action_fixture_duplicate_key") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("poc.action_fixture_invalid") from exc
    cases = TypeAdapter(tuple[ActionPocCase, ...]).validate_python(
        tuple(raw) if isinstance(raw, list) else raw,
        strict=True,
    )
    if len(cases) != 10 or len({case.case_id for case in cases}) != 10:
        raise ValueError("poc.action_fixture_invalid")
    return cases


ACTION_CASES = load_action_cases()


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
