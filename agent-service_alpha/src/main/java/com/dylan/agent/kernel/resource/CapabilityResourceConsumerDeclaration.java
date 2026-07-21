package com.dylan.agent.kernel.resource;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;
import java.util.Set;

/** Validator、Handler、Provider 或 Result projector 的静态维度消费声明。 */
public record CapabilityResourceConsumerDeclaration(
        String consumerId,
        ContractRef contractRef,
        Set<ResourceLimitDimension> requiredDimensions) {

    public CapabilityResourceConsumerDeclaration {
        if (consumerId == null || consumerId.isBlank()) {
            throw new IllegalArgumentException("consumerId must not be blank");
        }
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        requiredDimensions = Set.copyOf(
                Objects.requireNonNull(requiredDimensions, "requiredDimensions must not be null"));
        if (requiredDimensions.isEmpty()) {
            throw new IllegalArgumentException("requiredDimensions must not be empty");
        }
    }
}
