package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** Runtime 服务不可用或调用失败时抛出。 */
public class AgentRuntimeException extends AgentException {
    public AgentRuntimeException(String safeMessage) {
        super(AgentErrorCode.AGENT_RUNTIME_UNAVAILABLE, HttpStatus.BAD_GATEWAY, safeMessage);
    }

    public AgentRuntimeException(String safeMessage, Throwable cause) {
        super(AgentErrorCode.AGENT_RUNTIME_UNAVAILABLE, HttpStatus.BAD_GATEWAY, safeMessage, cause);
    }
}
