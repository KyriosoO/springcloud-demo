"""内部路由决策模型，不暴露给 Java。"""
from typing import Optional

from pydantic import Field, model_validator

from app.contracts.models import AgentIntent, StrictModel


class RouteDecision(StrictModel):
    """route_system.md 产生的内部路由结果。

    intent: QUERY/CLARIFY/AGGREGATE。
    domain: 选定的业务域；QUERY 和 AGGREGATE 必填，CLARIFY 可选。
    question: 反问文本；CLARIFY 必填，QUERY 和 AGGREGATE 必须为空。
    confidence: LLM 置信度 [0.0, 1.0]；低于 route_confidence_threshold 的 QUERY/AGGREGATE 会被降级为 CLARIFY。
    reason: 路由决策的可读理由（调试/审计用途）。
    """

    intent: AgentIntent
    domain: Optional[str] = None
    question: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_intent_shape(self) -> "RouteDecision":
        """强制 QUERY/AGGREGATE-必须有-domain 和 CLARIFY-必须有-question 的不变式。"""
        if self.intent in (AgentIntent.QUERY, AgentIntent.AGGREGATE):
            if self.domain is None or not self.domain.strip():
                raise ValueError(f"{self.intent.value} route requires a non-null domain")
            if self.question is not None:
                raise ValueError(f"{self.intent.value} route must not have a question")
        elif self.intent == AgentIntent.CLARIFY:
            if self.question is None or not self.question.strip():
                raise ValueError("CLARIFY route requires a non-null question")
        return self
