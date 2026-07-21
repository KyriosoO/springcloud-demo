package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** 权限不足时抛出（intent/domain/field/operator 任一维度不满足）。 */
public class AgentPermissionDeniedException extends AgentException {
    public AgentPermissionDeniedException(String safeMessage) {
        super(AgentErrorCode.AGENT_FIELD_FORBIDDEN, HttpStatus.FORBIDDEN, safeMessage);
    }

    public AgentPermissionDeniedException(AgentErrorCode errorCode, String safeMessage) {
        super(errorCode, HttpStatus.FORBIDDEN, safeMessage);
    }
}
