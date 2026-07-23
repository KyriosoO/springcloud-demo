from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AgentErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    UNSUPPORTED = "UNSUPPORTED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AgentError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: AgentErrorCode
    message: str
    retryable: bool = False
    reason_code: str | None = None


class AgentFailure(RuntimeError):
    def __init__(self, error: AgentError) -> None:
        super().__init__(error.code)
        self.error = error
