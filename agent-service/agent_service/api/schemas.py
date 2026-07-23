from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator


class ConversationRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: ConversationRole
    content: StrictStr = Field(min_length=1, max_length=4000)


class AgentExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    message: StrictStr = Field(min_length=1, max_length=4000)
    timeout_ms: int | None = Field(default=None, alias="timeoutMs", ge=1000, le=30000)
    conversation: tuple[ConversationTurn, ...] = Field(default=(), max_length=10)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized

    @model_validator(mode="after")
    def conversation_budget(self) -> "AgentExecuteRequest":
        if sum(len(turn.content) for turn in self.conversation) > 12000:
            raise ValueError("conversation content exceeds budget")
        return self


class AgentExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: UUID = Field(alias="requestId")
    type: str
    capability: str | None = None
    data: Any | None = None
    citations: tuple[Any, ...] = ()
    warnings: tuple[str, ...] = ()


class AgentErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: UUID = Field(alias="requestId")
    code: str
    message: str
    retryable: bool
