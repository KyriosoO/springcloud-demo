from __future__ import annotations

import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.graph.state import (
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings


class _DisabledSelector:
    async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision:
        del input
        return ActionSelectionDecision(kind=ActionSelectionDecisionKind.UNSUPPORTED)


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
        action_selector=_DisabledSelector(),
        answer_generator=_DisabledAnswerGenerator(),
    )


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    app = create_app(settings, build_stub_runtime)
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
