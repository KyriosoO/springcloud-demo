package com.dylan.agent.metadata.authorization.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/** 单一权威来源对 Capability 资源限额给出的完整强类型上界。 */
public record CapabilityResourceLimitContribution<T extends CapabilityResourceLimit>(
        ResourceLimitSource source,
        ContractRef contractRef,
        Class<T> limitType,
        T upperBound,
        String evidenceRef) {

    public CapabilityResourceLimitContribution {
        Objects.requireNonNull(source, "source must not be null");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(limitType, "limitType must not be null");
        Objects.requireNonNull(upperBound, "upperBound must not be null");
        if (!limitType.isInstance(upperBound)) {
            throw new IllegalArgumentException("resource limit contribution type mismatch");
        }
        if (evidenceRef == null || evidenceRef.isBlank()) {
            throw new IllegalArgumentException("evidenceRef must not be blank");
        }
    }
}
