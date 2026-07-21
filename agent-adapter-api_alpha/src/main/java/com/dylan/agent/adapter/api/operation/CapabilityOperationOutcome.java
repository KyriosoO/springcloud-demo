package com.dylan.agent.adapter.api.operation;

/** 单次 operation 的封闭 typed outcome。 */
public sealed interface CapabilityOperationOutcome<R>
        permits CapabilityOperationSuccess, CapabilityOperationFailure {

    CapabilityOperationMetadata metadata();
}
