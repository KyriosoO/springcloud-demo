package com.dylan.agent.capability;

import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.model.AgentUserContext;

/**
 * 传入 {@link AgentCapabilityHandler#execute} 的不可变上下文。
 * 携带会话/turn 标识、规范化消息、用户上下文和上一轮查询上下文。
 */
public final class CapabilityExecutionContext {

    private final String conversationId;
    private final String turnId;
    private final String normalizedMessage;
    private final AgentUserContext userContext;
    private final RuntimeQueryContext previousQuery;

    public CapabilityExecutionContext(
            String conversationId,
            String turnId,
            String normalizedMessage,
            AgentUserContext userContext,
            RuntimeQueryContext previousQuery) {
        this.conversationId = conversationId;
        this.turnId = turnId;
        this.normalizedMessage = normalizedMessage;
        this.userContext = userContext;
        this.previousQuery = previousQuery;
    }

    public String conversationId() {
        return conversationId;
    }

    public String turnId() {
        return turnId;
    }

    public String normalizedMessage() {
        return normalizedMessage;
    }

    public AgentUserContext userContext() {
        return userContext;
    }

    public RuntimeQueryContext previousQuery() {
        return previousQuery;
    }
}
