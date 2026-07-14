package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

import java.util.Objects;

public record DocumentAclScopeAllowed(
        DocumentAclScopeSnapshot scope,
        CapabilityOperationMetadata metadata) implements DocumentAclScopeResolution {
    public DocumentAclScopeAllowed {
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(metadata, "metadata must not be null");
    }
}
