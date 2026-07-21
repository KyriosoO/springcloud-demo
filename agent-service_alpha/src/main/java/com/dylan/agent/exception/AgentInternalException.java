package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** 系统内部错误（不应暴露给用户的故障）。 */
public class AgentInternalException extends AgentException {
    public AgentInternalException(String safeMessage, Throwable cause) {
        super(AgentErrorCode.AGENT_INTERNAL_ERROR, HttpStatus.INTERNAL_SERVER_ERROR, safeMessage, cause);
    }
}
