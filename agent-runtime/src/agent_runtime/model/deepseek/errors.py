from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agent_runtime.graph.state import ModelNodeFailure, ModelNodeFailureKind
from agent_runtime.model.contracts import ModelProviderFailureKind


class DeepSeekTransportFailureCategory(StrEnum):
    TIMEOUT = "timeout"
    HTTP = "http"
    TRANSPORT = "transport"
    PARSE = "parse"
    SCHEMA = "schema"
    MODEL = "model"
    SIZE = "size"


class DeepSeekTransportPhase(StrEnum):
    PERMIT = "permit"
    CONNECT = "connect"
    WRITE = "write"
    READ = "read"
    PARSE = "parse"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True, kw_only=True)
class DeepSeekTransportFailure:
    category: DeepSeekTransportFailureCategory
    status_code: int | None = None
    phase: DeepSeekTransportPhase | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, DeepSeekTransportFailureCategory):
            raise ValueError("model.invalid_transport_failure")
        if self.status_code is not None and (
            not isinstance(self.status_code, int)
            or isinstance(self.status_code, bool)
            or not 100 <= self.status_code <= 599
        ):
            raise ValueError("model.invalid_transport_failure")
        if self.phase is not None and not isinstance(self.phase, DeepSeekTransportPhase):
            raise ValueError("model.invalid_transport_failure")


def map_deepseek_failure(failure: DeepSeekTransportFailure) -> ModelProviderFailureKind:
    if failure.category is DeepSeekTransportFailureCategory.TIMEOUT or failure.status_code in (408, 504):
        return ModelProviderFailureKind.PROVIDER_TIMEOUT
    if failure.category in {
        DeepSeekTransportFailureCategory.PARSE,
        DeepSeekTransportFailureCategory.SCHEMA,
        DeepSeekTransportFailureCategory.MODEL,
        DeepSeekTransportFailureCategory.SIZE,
    }:
        return ModelProviderFailureKind.INVALID_OUTPUT
    return ModelProviderFailureKind.PROVIDER_FAILURE


def to_model_node_failure(kind: ModelProviderFailureKind) -> ModelNodeFailure:
    mapping = {
        ModelProviderFailureKind.INPUT_DENIED: ModelNodeFailureKind.INPUT_DENIED,
        ModelProviderFailureKind.PROVIDER_TIMEOUT: ModelNodeFailureKind.PROVIDER_TIMEOUT,
        ModelProviderFailureKind.PROVIDER_FAILURE: ModelNodeFailureKind.PROVIDER_FAILURE,
        ModelProviderFailureKind.INVALID_OUTPUT: ModelNodeFailureKind.INVALID_OUTPUT,
    }
    return ModelNodeFailure(kind=mapping[kind])

