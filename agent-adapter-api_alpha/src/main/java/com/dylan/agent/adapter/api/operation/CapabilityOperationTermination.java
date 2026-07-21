package com.dylan.agent.adapter.api.operation;

/** 单次 capability-local operation 的终止语义。 */
public enum CapabilityOperationTermination {
    SUCCEEDED,
    DISABLED,
    FAILED,
    DEADLINE_EXCEEDED,
    CANCELLED,
    REJECTED
}
