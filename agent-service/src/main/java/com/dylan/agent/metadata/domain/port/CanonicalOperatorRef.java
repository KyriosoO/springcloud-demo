package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.api.enums.AgentOperator;

import java.util.Objects;

/** Canonical operator reference scoped to a canonical field. */
public record CanonicalOperatorRef(CanonicalFieldRef fieldRef, AgentOperator operator) {
    public CanonicalOperatorRef {
        Objects.requireNonNull(fieldRef, "fieldRef must not be null");
        Objects.requireNonNull(operator, "operator must not be null");
    }
}
