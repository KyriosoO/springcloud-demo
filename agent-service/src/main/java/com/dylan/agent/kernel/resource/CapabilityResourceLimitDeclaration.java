package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;
import java.util.Set;

/** Capability Definition 对单一资源限额契约的静态声明。 */
public record CapabilityResourceLimitDeclaration<T extends CapabilityResourceLimit>(
        ContractRef contractRef,
        Class<T> limitType,
        T intrinsicUpperBound,
        Set<ResourceLimitDimension> applicableDimensions) {

    public CapabilityResourceLimitDeclaration {
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(limitType, "limitType must not be null");
        Objects.requireNonNull(intrinsicUpperBound, "intrinsicUpperBound must not be null");
        if (!limitType.isInstance(intrinsicUpperBound)) {
            throw new IllegalArgumentException("intrinsic upper bound type mismatch");
        }
        applicableDimensions = Set.copyOf(
                Objects.requireNonNull(applicableDimensions, "applicableDimensions must not be null"));
        if (applicableDimensions.isEmpty()) {
            throw new IllegalArgumentException("applicableDimensions must not be empty");
        }
    }
}
