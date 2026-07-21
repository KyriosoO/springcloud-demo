package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * Conversation Scope（CHAT 模式）。
 */
public final class ConversationScope implements InvocationScope {

    private final String scopeId;

    public ConversationScope(String scopeId) {
        this.scopeId = Objects.requireNonNull(scopeId);
        if (scopeId.isBlank()) {
            throw new IllegalArgumentException("scopeId must not be blank");
        }
    }

    @Override
    public String scopeId() { return scopeId; }

    @Override
    public boolean isCompatibleWith(InvocationOrigin origin) {
        return origin instanceof ChatInvocationOrigin;
    }
}
