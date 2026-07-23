from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Capability(StrEnum):
    QUERY = "QUERY"
    AGGREGATE = "AGGREGATE"
    DOCUMENT = "DOCUMENT"


class PlanDisposition(StrEnum):
    EXECUTE = "EXECUTE"
    CLARIFY = "CLARIFY"
    REJECT = "REJECT"


class ExecutePlanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1"]
    outcome: Literal[PlanDisposition.EXECUTE]
    capability: Capability
    domain: str
    intent: str
    payload: dict[str, object]


class ClarifyPlanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1"]
    outcome: Literal[PlanDisposition.CLARIFY]
    reason_code: str
    missing_fields: tuple[str, ...] = ()
    option_keys: tuple[str, ...] = ()


class RejectPlanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1"]
    outcome: Literal[PlanDisposition.REJECT]
    reason_code: str


PlanCandidate = Annotated[
    ExecutePlanCandidate | ClarifyPlanCandidate | RejectPlanCandidate,
    Field(discriminator="outcome"),
]
