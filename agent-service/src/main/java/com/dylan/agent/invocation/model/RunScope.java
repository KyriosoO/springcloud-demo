package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * RunScope: D06 TASK 使用的 InvocationScope 实现。
 * D03 不创建此实例。D06 Coordinator 负责构建。
 */
public final class RunScope implements InvocationScope {

    private final String scopeId;

    public RunScope(String scopeId) {
        this.scopeId = Objects.requireNonNull(scopeId);
        if (scopeId.isBlank()) {
            throw new IllegalArgumentException("scopeId must not be blank");
        }
    }

    @Override
    public String scopeId() { return scopeId; }

    @Override
    public boolean isCompatibleWith(InvocationOrigin origin) {
        return origin instanceof TaskInvocationOrigin;
    }
}
