from __future__ import annotations

import asyncio

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot, LocalModelCompositionRoot
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput,
    SummaryCoverageInput,
    SummaryEvidenceInput,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.model.contracts import (
    ModelCallContext,
    ModelProviderFailureKind,
    StructuredFinishKind,
    StructuredModelResponse,
)
from agent_runtime.model.settings import ModelSettings
from tests.model_helpers import FakeStructuredModelTransport


def _input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="税务政策",
        coverage=SummaryCoverageInput(
            retrieval_complete=True,
            domain_coverage_complete=True,
        ),
        evidence=(
            SummaryEvidenceInput(
                evidence_ref="e1",
                content="税务政策正文",
                domain_ids=("tax.policy",),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_production_registry_owns_summary_v2_and_rejects_v1_definition() -> None:
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    transport = FakeStructuredModelTransport(
        StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"税务政策正文"}]}',
            tool_calls=(),
            usage_total_tokens=None,
        )
    )
    model = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={},
        additional_definitions=tasks.as_tuple(),
    )
    context = ModelCallContext(
        request_id="req-summary-v2",
        correlation_id="corr-summary-v2",
        deadline_monotonic=asyncio.get_running_loop().time() + 5.0,
    )

    v2_result = await model.gateway.generate(
        definition=tasks.summary,
        input=_input(),
        context=context,
    )
    v1_result = await model.gateway.generate(
        definition=KnowledgeSummaryTaskV1.definition(),
        input=_input(),
        context=context,
    )

    assert v2_result.failure_kind is None
    assert v2_result.output is not None
    assert v2_result.output.outcome is SummaryOutcome.ANSWER
    assert v1_result.failure_kind is ModelProviderFailureKind.INPUT_DENIED
    assert transport.calls == 1


def test_disabled_path_creates_no_knowledge_task_definitions() -> None:
    assert KnowledgeCompositionRoot.task_definitions(enabled=False) is None
