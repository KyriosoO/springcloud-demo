package com.dylan.agent.adapter.api.document.provider;

import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationRequest;

public record DocumentEmbeddingOperationRequest(
        DocumentEmbeddingInputProjection input,
        DocumentProviderOutboundPolicyReference outboundPolicyReference,
        CapabilityOperationContext operationContext) implements CapabilityOperationRequest {
}
