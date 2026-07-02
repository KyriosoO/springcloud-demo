package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.metadata.authorization.model.DelegationConstraint;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;

import java.util.Map;
import java.util.Objects;

/** 只读 delegation 边界；未知引用必须 fail closed。 */
public final class DelegationBoundary {

    private final Map<DelegationConstraintRef, DelegationConstraint> constraints;

    public DelegationBoundary(Map<DelegationConstraintRef, DelegationConstraint> constraints) {
        this.constraints = Map.copyOf(Objects.requireNonNull(constraints, "constraints must not be null"));
    }

    public DelegationConstraint require(DelegationConstraintRef ref) {
        DelegationConstraint constraint = constraints.get(Objects.requireNonNull(ref));
        if (constraint == null) {
            throw new IllegalStateException("unknown delegation constraint: " + ref);
        }
        return constraint;
    }
}
