package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * CHAT Invocation 来源：conversationId + turnId。
 */
public non-sealed class ChatInvocationOrigin implements InvocationOrigin {

    private final String conversationId;
    private final String turnId;

    public ChatInvocationOrigin(String conversationId, String turnId) {
        this.conversationId = Objects.requireNonNull(conversationId);
        this.turnId = Objects.requireNonNull(turnId);
        if (conversationId.isBlank()) {
            throw new IllegalArgumentException("conversationId must not be blank");
        }
        if (turnId.isBlank()) {
            throw new IllegalArgumentException("turnId must not be blank");
        }
    }

    @Override
    public boolean isCompatibleWith(InvocationType type) {
        return type == InvocationType.CHAT;
    }

    public String conversationId() { return conversationId; }
    public String turnId() { return turnId; }
}
