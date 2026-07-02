package com.dylan.agent.lifecycle;

import com.dylan.agent.invocation.model.InvocationHandle;

/**
 * 短启动事务的结果。
 */
public record StartWriteResult(InvocationHandle handle) {
    public StartWriteResult {
        java.util.Objects.requireNonNull(handle, "handle must not be null");
    }
}
