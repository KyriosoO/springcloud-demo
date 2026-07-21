package com.dylan.agent.lifecycle.model;

/**
 * Invocation 内部响应类型。不直接替代 Agent API response enum。
 */
public enum InvocationResponseType {
    SUCCESS,
    CLARIFY,
    FAILURE,
    CANCELLED
}
