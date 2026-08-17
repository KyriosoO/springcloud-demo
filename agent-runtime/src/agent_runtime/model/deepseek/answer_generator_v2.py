from __future__ import annotations

from dataclasses import replace

from agent_runtime.model.contracts import (
    CandidateAnswer,
    ModelTaskDefinition,
    StructuredModelRequest,
)
from agent_runtime.model.deepseek.answer_generator import (
    AnswerGenerationTaskInput,
    build_answer_generation_task_definition,
)


_ANSWER_V2_SYSTEM_INSTRUCTION = (
    "Return one JSON object with exactly answer, used_fact_ids, and unsupported_claims. "
    "Use only supplied facts. Every non-empty factual sentence or semicolon-delimited factual "
    "segment in answer must contain at least one inline marker in the exact form [fact-NNNN], "
    "where the ID is present in the supplied facts. Do not invent markers. "
    "used_fact_ids must contain no duplicates and its set must exactly equal the set of inline "
    "markers in answer. Keep unsupported_claims as an empty array. "
    'Example: {"answer":"Position is engineer [fact-0001]; work base is Shanghai '
    '[fact-0002].","used_fact_ids":["fact-0001","fact-0002"],'
    '"unsupported_claims":[]}'
)


def build_answer_generation_v2_task_definition(
    *,
    timeout_ms: int,
    max_input_bytes: int = 65536,
    max_output_tokens: int = 1024,
) -> ModelTaskDefinition[AnswerGenerationTaskInput, CandidateAnswer]:
    base = build_answer_generation_task_definition(
        timeout_ms=timeout_ms,
        max_input_bytes=max_input_bytes,
        max_output_tokens=max_output_tokens,
    )

    def build_request(input: AnswerGenerationTaskInput) -> StructuredModelRequest:
        request = base.build_request(input)
        return replace(
            request,
            task_version="answer-generation-v2",
            system_instruction=_ANSWER_V2_SYSTEM_INSTRUCTION,
        )

    return replace(
        base,
        task_version="answer-generation-v2",
        build_request=build_request,
    )
