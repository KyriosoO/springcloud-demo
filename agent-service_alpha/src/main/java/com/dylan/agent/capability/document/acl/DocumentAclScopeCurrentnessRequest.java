package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationRequest;

import java.util.Objects;

public record DocumentAclScopeCurrentnessRequest(
        DocumentAclExecutionEvidence evidence,
        CapabilityOperationContext operationContext) implements CapabilityOperationRequest {
    public DocumentAclScopeCurrentnessRequest {
        Objects.requireNonNull(evidence);
        Objects.requireNonNull(operationContext);
        validate(evidence, operationContext);
    }

    static void validate(DocumentAclExecutionEvidence evidence, CapabilityOperationContext context) {
        if (!evidence.invocationId().equals(context.invocationId())
                || !evidence.requestCorrelationId().equals(context.requestCorrelationId())
                || !evidence.resourceLimitReference().equals(context.resourceLimits().reference())) {
            throw new IllegalArgumentException("ACL currentness operation binding mismatch");
        }
    }
}
