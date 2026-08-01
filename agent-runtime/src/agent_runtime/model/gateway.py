from __future__ import annotations

import asyncio
from types import MappingProxyType
from typing import Any, Sequence, cast

from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelCallContext,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTaskDefinition,
    ModelTaskId,
    ModelTaskResult,
    ModelTransportError,
    StructuredModelTransport,
    TInput,
    TOutput,
)


class FrozenModelTaskRegistry:
    __slots__ = ("_definitions",)

    def __init__(self, definitions: Sequence[ModelTaskDefinition[Any, Any]]) -> None:
        registered: dict[tuple[ModelTaskId, str], ModelTaskDefinition[Any, Any]] = {}
        for definition in definitions:
            key = (definition.task_id, definition.task_version)
            if key in registered:
                raise ValueError("model.duplicate_task_definition")
            registered[key] = definition
        if not registered:
            raise ValueError("model.task_registry_empty")
        self._definitions = MappingProxyType(registered)

    def owns(self, definition: ModelTaskDefinition[Any, Any]) -> bool:
        registered = self._definitions.get((definition.task_id, definition.task_version))
        return registered is definition


class BoundedStructuredModelGateway:
    __slots__ = ("_max_waiters", "_registry", "_semaphore", "_transport", "_waiting")

    def __init__(
        self,
        *,
        transport: StructuredModelTransport,
        definitions: Sequence[ModelTaskDefinition[Any, Any]],
        max_concurrency: int,
    ) -> None:
        if not callable(getattr(transport, "complete", None)):
            raise ValueError("model.invalid_transport")
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or not 1 <= max_concurrency <= 8:
            raise ValueError("model.invalid_concurrency")
        self._transport = transport
        self._registry = FrozenModelTaskRegistry(definitions)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_waiters = max_concurrency
        self._waiting = 0

    async def generate(
        self,
        *,
        definition: ModelTaskDefinition[TInput, TOutput],
        input: TInput,
        context: ModelCallContext,
    ) -> ModelTaskResult[TOutput]:
        erased_definition = cast(ModelTaskDefinition[Any, Any], definition)
        if not self._registry.owns(erased_definition) or type(input) is not definition.input_type:
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.INPUT_DENIED)
        loop = asyncio.get_running_loop()
        call_deadline = min(
            loop.time() + (definition.timeout_ms / 1000),
            context.deadline_monotonic - 0.250,
        )
        if call_deadline <= loop.time():
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.PROVIDER_TIMEOUT)
        queued = False
        if self._semaphore.locked():
            if self._waiting >= self._max_waiters:
                return ModelTaskResult(failure_kind=ModelProviderFailureKind.PROVIDER_TIMEOUT)
            self._waiting += 1
            queued = True
        try:
            async with asyncio.timeout_at(call_deadline):
                async with self._semaphore:
                    if queued:
                        self._waiting -= 1
                        queued = False
                    request = definition.build_request(input)
                    response = await self._transport.complete(request, call_deadline=call_deadline)
                    output = definition.parse_response(response)
            return ModelTaskResult(output=output)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.PROVIDER_TIMEOUT)
        except ModelInputDenied:
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.INPUT_DENIED)
        except InvalidModelOutput:
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.INVALID_OUTPUT)
        except ModelTransportError as exc:
            return ModelTaskResult(failure_kind=exc.kind)
        except Exception:
            return ModelTaskResult(failure_kind=ModelProviderFailureKind.PROVIDER_FAILURE)
        finally:
            if queued:
                self._waiting -= 1
