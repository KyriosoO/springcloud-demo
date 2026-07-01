package com.dylan.agent.invocation.model;

/**
 * Invocation Scope 封闭接口。
 */
public sealed interface InvocationScope permits ConversationScope, RunScope {
    String scopeId();
    boolean isCompatibleWith(InvocationOrigin origin);
}
