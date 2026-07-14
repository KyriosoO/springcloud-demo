package com.dylan.agent.adapter.api.operation;

/** 不泄露 provider 原始错误的安全失败码。 */
public enum CapabilityOperationFailureCode {
    DISABLED,
    INVALID_REQUEST,
    PROVIDER_UNAVAILABLE,
    PROVIDER_TIMEOUT,
    PROVIDER_FAILED,
    INVALID_RESPONSE,
    LIMIT_EXCEEDED,
    DEADLINE_EXCEEDED,
    CANCELLED,
    LATE_RESULT,
    SECURITY_REJECTED,
    BINDING_MISMATCH
}
