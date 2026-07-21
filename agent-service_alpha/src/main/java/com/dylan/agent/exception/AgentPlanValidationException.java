package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** Runtime 返回的 plan 结构或语义不合法时抛出。 */
public class AgentPlanValidationException extends AgentException {
    public AgentPlanValidationException(String safeMessage) {
        super(AgentErrorCode.AGENT_PLAN_INVALID, HttpStatus.UNPROCESSABLE_ENTITY, safeMessage);
    }
}
