package com.dylan.agent.capability.document.profile;

import java.util.Map;
import java.util.Objects;

/** exact policyVersion 的 immutable Document constraint lookup。 */
public final class DocumentPolicyConstraintRegistry {
    private final Map<String, DocumentPolicyConstraint> constraints;

    DocumentPolicyConstraintRegistry(Map<String, DocumentPolicyConstraint> constraints) {
        this.constraints = Map.copyOf(Objects.requireNonNull(constraints));
    }

    public DocumentPolicyConstraint require(String policyVersion) {
        DocumentPolicyConstraint result = constraints.get(policyVersion);
        if (result == null) throw new IllegalArgumentException("document policy constraint is unavailable");
        return result;
    }
}
