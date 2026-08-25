from __future__ import annotations

import os
from typing import Mapping

import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.bootstrap import (
    BusinessQueryRuntimeCompositionRoot,
    LocalModelCompositionRoot,
    RuntimeCompositionRoot,
)
from agent_runtime.business.http_client import HttpxBusinessDomainTransport
from agent_runtime.business.settings import BusinessGlobalSettings
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.settings import ModelProvider, ModelSettings


class _DisabledSelector:
    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)


class _DisabledAnswerGenerator:
    async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision:
        del input
        return AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.FAILURE,
            failure=ModelNodeFailure(kind=ModelNodeFailureKind.INPUT_DENIED),
        )


def build_stub_runtime() -> AgentRuntimeInvoker:
    return RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(),
        capability_selector=_DisabledSelector(),
        answer_generator=_DisabledAnswerGenerator(),
    )


def build_runtime(
    environ: Mapping[str, str] | None = None,
) -> AgentRuntimeInvoker | ModelContextBindingRuntimeInvoker:
    active = os.environ if environ is None else environ
    model_settings = ModelSettings.from_env(active)
    if model_settings.provider is ModelProvider.STUB:
        return build_stub_runtime()
    global_settings = BusinessGlobalSettings.from_env(active)
    employee_endpoint = active.get("AGENT_EMPLOYEE_BASE_URL", "http://127.0.0.1:9210")
    transaction_endpoint = active.get("AGENT_TRANSACTION_BASE_URL", "http://127.0.0.1:8182")
    model = LocalModelCompositionRoot.build(
        settings=model_settings,
        grounding_policies={},
    )
    employee_transport = HttpxBusinessDomainTransport(
        base_endpoint=employee_endpoint,
        allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
        max_response_bytes=global_settings.http_max_response_bytes,
    )
    transaction_transport = HttpxBusinessDomainTransport(
        base_endpoint=transaction_endpoint,
        allowed_paths=frozenset({"/txn/search"}),
        max_response_bytes=global_settings.http_max_response_bytes,
    )
    return BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=employee_transport,
        transaction_transport=transaction_transport,
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
        global_settings=global_settings,
    )


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    app = create_app(settings, build_runtime)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
    )


if __name__ == "__main__":
    main()
