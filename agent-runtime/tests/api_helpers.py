from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from agent_runtime.api.models import RuntimeInvokeRequest
from agent_runtime.capability_api.contracts import CapabilityStatus, FailureDetail, FailureSource
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome


def runtime_request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "contractVersion": 1,
        "requestId": "7251cedd-6762-4fd3-874d-b1607570f0ac",
        "correlationId": "corr-101",
        "question": "请查询员工信息",
        "subject": {"id": "dylan", "type": "user"},
        "deadlineEpochMs": int(time.time() * 1000) + 30_000,
        "remainingTimeoutMs": 29_500,
    }
    value.update(overrides)
    return value


class CapturingInvoker:
    def __init__(
        self,
        outcome: AgentSemanticOutcome | None = None,
        *,
        release: asyncio.Event | None = None,
    ) -> None:
        self.outcome = outcome or AgentSemanticOutcome(
            status=CapabilityStatus.UNSUPPORTED,
            capability_id=None,
            answer_text="当前不支持该查询。",
            user_result=None,
            failure=FailureDetail(code="core.no_enabled_capability", source=FailureSource.CORE),
        )
        self.release = release
        self.calls = 0
        self.questions: list[str] = []
        self.scopes: list[RequestExecutionScope] = []
        self.started = asyncio.Event()

    async def ainvoke(
        self,
        *,
        question: str,
        scope: RequestExecutionScope,
    ) -> AgentSemanticOutcome:
        self.calls += 1
        self.questions.append(question)
        self.scopes.append(scope)
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        return self.outcome


@dataclass(frozen=True, slots=True)
class FixedClocks:
    epoch: int
    monotonic_value: float

    def epoch_ms(self) -> int:
        return self.epoch

    def monotonic(self) -> float:
        return self.monotonic_value
