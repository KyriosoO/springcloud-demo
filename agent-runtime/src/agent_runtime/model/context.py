from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import Awaitable, Callable, Protocol

from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.model.contracts import MissingModelCallContext, ModelCallContext


_MODEL_CALL_CONTEXT: ContextVar[ModelCallContext | None] = ContextVar(
    "agent_runtime_model_call_context",
    default=None,
)


class RuntimeInvoker(Protocol):
    async def ainvoke(
        self,
        *,
        question: str,
        scope: RequestExecutionScope,
    ) -> AgentSemanticOutcome: ...


class ModelCallContextAccessor:
    def require_current(self) -> ModelCallContext:
        context = _MODEL_CALL_CONTEXT.get()
        if context is None:
            raise MissingModelCallContext("model.missing_call_context")
        return context


class ModelContextBindingRuntimeInvoker:
    __slots__ = ("_close", "_close_lock", "_closed", "_delegate")

    def __init__(
        self,
        delegate: RuntimeInvoker,
        *,
        close: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._delegate = delegate
        self._close = close
        self._close_lock = asyncio.Lock()
        self._closed = False

    async def ainvoke(
        self,
        *,
        question: str,
        scope: RequestExecutionScope,
    ) -> AgentSemanticOutcome:
        if self._closed:
            raise RuntimeError("model.runtime_closed")
        context = ModelCallContext(
            request_id=scope.context.request_id,
            correlation_id=scope.context.correlation_id,
            deadline_monotonic=scope.context.deadline_monotonic,
        )
        token: Token[ModelCallContext | None] = _MODEL_CALL_CONTEXT.set(context)
        try:
            return await self._delegate.ainvoke(question=question, scope=scope)
        finally:
            _MODEL_CALL_CONTEXT.reset(token)

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            if self._close is not None:
                await self._close()
