package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/** 只保存静态强类型 Contract 的不可变注册表。 */
public final class CapabilityResourceLimitRegistry {

    private final Map<ContractRef, CapabilityResourceLimitContract<?>> contracts;

    public CapabilityResourceLimitRegistry(Collection<CapabilityResourceLimitContract<?>> contracts) {
        Objects.requireNonNull(contracts, "contracts must not be null");
        Map<ContractRef, CapabilityResourceLimitContract<?>> indexed = new LinkedHashMap<>();
        for (CapabilityResourceLimitContract<?> contract : contracts) {
            Objects.requireNonNull(contract, "contract must not be null");
            if (contract.supportedDimensions() == null || contract.supportedDimensions().isEmpty()) {
                throw new IllegalArgumentException("resource limit contract dimensions must not be empty");
            }
            CapabilityResourceLimitContract<?> previous = indexed.putIfAbsent(contract.contractRef(), contract);
            if (previous != null) {
                throw new IllegalArgumentException("duplicate resource limit contract: " + contract.contractRef());
            }
        }
        this.contracts = Map.copyOf(indexed);
    }

    public <T extends CapabilityResourceLimit> CapabilityResourceLimitContract<T> require(
            ContractRef contractRef,
            Class<T> limitType) {
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(limitType, "limitType must not be null");
        CapabilityResourceLimitContract<?> contract = contracts.get(contractRef);
        if (contract == null) {
            throw new IllegalArgumentException("resource limit contract not registered: " + contractRef);
        }
        if (!limitType.equals(contract.limitType())) {
            throw new IllegalArgumentException("resource limit contract type mismatch: " + contractRef);
        }
        CapabilityResourceLimitContract<T> typed = (CapabilityResourceLimitContract<T>) contract;
        return typed;
    }
}
