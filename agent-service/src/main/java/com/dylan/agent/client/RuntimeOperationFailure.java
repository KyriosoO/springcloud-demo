package com.dylan.agent.client;

/**
 * Runtime Route/Plan 调用失败分类。
 */
public enum RuntimeOperationFailure {
    TRANSPORT,
    PROTOCOL,
    AUTHENTICATION,
    PROVIDER,
    DEADLINE,
    REPAIR_EXHAUSTED,
    INTERNAL
}
