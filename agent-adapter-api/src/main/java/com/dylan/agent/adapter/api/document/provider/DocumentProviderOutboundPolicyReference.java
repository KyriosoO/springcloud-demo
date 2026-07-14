package com.dylan.agent.adapter.api.document.provider;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import java.time.Instant;

public record DocumentProviderOutboundPolicyReference(
        String invocationId,
        String operationId,
        CapabilityOperationType operationType,
        String decisionDigest,
        String inputDigest,
        ResourceLimitReference resourceLimitReference,
        Instant validUntil) {
    public DocumentProviderOutboundPolicyReference {
        if (invocationId == null || invocationId.isBlank()
                || operationId == null || operationId.isBlank()
                || operationType == null
                || decisionDigest == null || !decisionDigest.matches("[0-9a-f]{64}")
                || inputDigest == null || !inputDigest.matches("[0-9a-f]{64}")
                || resourceLimitReference == null || validUntil == null) {
            throw new IllegalArgumentException("document provider outbound policy reference invalid");
        }
    }
}
