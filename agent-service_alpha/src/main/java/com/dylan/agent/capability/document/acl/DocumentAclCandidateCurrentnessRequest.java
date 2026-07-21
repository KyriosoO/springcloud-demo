package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclObjectRef;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationRequest;

import java.util.List;
import java.util.Objects;

public record DocumentAclCandidateCurrentnessRequest(
        DocumentAclExecutionEvidence evidence,
        List<DocumentAclObjectRef> candidates,
        String candidateSetDigest,
        CapabilityOperationContext operationContext) implements CapabilityOperationRequest {
    public DocumentAclCandidateCurrentnessRequest {
        Objects.requireNonNull(evidence);
        candidates = List.copyOf(candidates == null ? List.of() : candidates);
        if (candidateSetDigest == null || !candidateSetDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("candidateSetDigest must be lowercase SHA-256 hex");
        }
        Objects.requireNonNull(operationContext);
        DocumentAclScopeCurrentnessRequest.validate(evidence, operationContext);
    }
}
