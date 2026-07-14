package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

import java.util.Objects;

public record DocumentAclScopeFailed(
        DocumentAclFailureCode code,
        String diagnosticId,
        CapabilityOperationMetadata metadata) implements DocumentAclScopeResolution {
    public DocumentAclScopeFailed {
        Objects.requireNonNull(code, "code must not be null");
        if (diagnosticId == null || diagnosticId.isBlank()) {
            throw new IllegalArgumentException("diagnosticId must not be blank");
        }
        Objects.requireNonNull(metadata, "metadata must not be null");
    }
}
