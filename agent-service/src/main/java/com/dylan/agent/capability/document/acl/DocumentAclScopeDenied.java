package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

import java.util.Objects;

public record DocumentAclScopeDenied(
        DocumentAclDenyReason reason,
        String decisionEvidenceRef,
        CapabilityOperationMetadata metadata) implements DocumentAclScopeResolution {
    public DocumentAclScopeDenied {
        Objects.requireNonNull(reason, "reason must not be null");
        if (decisionEvidenceRef == null || decisionEvidenceRef.isBlank()) {
            throw new IllegalArgumentException("decisionEvidenceRef must not be blank");
        }
        Objects.requireNonNull(metadata, "metadata must not be null");
    }
}
