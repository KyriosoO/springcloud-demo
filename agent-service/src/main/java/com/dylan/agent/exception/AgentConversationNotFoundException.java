package com.dylan.agent.exception;

import org.springframework.http.HttpStatus;

import com.dylan.agent.api.enums.AgentErrorCode;

/** 会话不存在或不属于当前用户时抛出。 */
public class AgentConversationNotFoundException extends AgentException {
    public AgentConversationNotFoundException(String safeMessage) {
        super(AgentErrorCode.AGENT_CONVERSATION_NOT_FOUND, HttpStatus.NOT_FOUND, safeMessage);
    }
}
