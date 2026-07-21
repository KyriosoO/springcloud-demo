package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** 查询执行失败时抛出，携带安全消息（不泄露内部细节）。 */
public class AgentQueryException extends AgentException {
    public AgentQueryException(String safeMessage) {
        super(AgentErrorCode.AGENT_QUERY_FAILED, HttpStatus.BAD_GATEWAY, safeMessage);
    }

    public AgentQueryException(String safeMessage, Throwable cause) {
        super(AgentErrorCode.AGENT_QUERY_FAILED, HttpStatus.BAD_GATEWAY, safeMessage, cause);
    }
}
