package com.dylan.agent.metadata.context.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;

import java.util.Objects;

/**
 * Stable logical key for one persisted capability context record.
 */
public record ContextRecordKey(
        ContextOwnerRef owner,
        InvocationScope scope,
        RuntimeContextType contextType) {

    public ContextRecordKey {
        Objects.requireNonNull(owner, "owner must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(contextType, "contextType must not be null");
    }
}
