package com.dylan.agent.metadata.context.request;

import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;

import java.util.Objects;

/** Request to load one declared Context for Planning. */
public record ContextReadRequest(
        String requestCorrelationId,
        ContextOwnerRef owner,
        InvocationScope scope,
        ContextReadDeclaration declaration,
        PlanningAuthorizationEvidence evidence) {
    public ContextReadRequest {
        requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        Objects.requireNonNull(owner, "owner must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(declaration, "declaration must not be null");
        Objects.requireNonNull(evidence, "evidence must not be null");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
