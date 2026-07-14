package com.dylan.agent.adapter.api.operation;

/** capability-local provider 的 typed request 必须内嵌唯一 operation context。 */
public interface CapabilityOperationRequest {

    CapabilityOperationContext operationContext();
}
