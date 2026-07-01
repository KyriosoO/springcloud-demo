package com.dylan.agent.invocation.model;

/**
 * Invocation 来源封闭接口。
 */
public sealed interface InvocationOrigin
        permits ChatInvocationOrigin, TaskInvocationOrigin {
    boolean isCompatibleWith(InvocationType type);
}
