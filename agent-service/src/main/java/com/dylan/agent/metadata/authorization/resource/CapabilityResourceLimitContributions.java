package com.dylan.agent.metadata.authorization.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Collection;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** 按 source + ContractRef 唯一索引的不可变 typed contribution 集合。 */
public final class CapabilityResourceLimitContributions {

    private final Map<ResourceLimitSource, Map<ContractRef, CapabilityResourceLimitContribution<?>>> bySource;

    private CapabilityResourceLimitContributions(
            Map<ResourceLimitSource, Map<ContractRef, CapabilityResourceLimitContribution<?>>> bySource) {
        this.bySource = bySource;
    }

    public static CapabilityResourceLimitContributions of(
            Collection<? extends CapabilityResourceLimitContribution<?>> contributions) {
        Objects.requireNonNull(contributions, "contributions must not be null");
        Map<ResourceLimitSource, Map<ContractRef, CapabilityResourceLimitContribution<?>>> mutable =
                new EnumMap<>(ResourceLimitSource.class);
        for (CapabilityResourceLimitContribution<?> contribution : contributions) {
            Objects.requireNonNull(contribution, "contribution must not be null");
            var byContract = mutable.computeIfAbsent(
                    contribution.source(), ignored -> new LinkedHashMap<>());
            if (byContract.putIfAbsent(contribution.contractRef(), contribution) != null) {
                throw new IllegalArgumentException("duplicate resource contribution: "
                        + contribution.source() + "/" + contribution.contractRef());
            }
        }
        Map<ResourceLimitSource, Map<ContractRef, CapabilityResourceLimitContribution<?>>> frozen =
                new EnumMap<>(ResourceLimitSource.class);
        mutable.forEach((source, values) -> frozen.put(source, Map.copyOf(values)));
        return new CapabilityResourceLimitContributions(Map.copyOf(frozen));
    }

    public static CapabilityResourceLimitContributions empty() {
        return of(List.of());
    }

    public CapabilityResourceLimitContributions merge(CapabilityResourceLimitContributions other) {
        Objects.requireNonNull(other, "other must not be null");
        return of(java.util.stream.Stream.concat(all().stream(), other.all().stream()).toList());
    }

    public List<CapabilityResourceLimitContribution<?>> all() {
        return bySource.values().stream().flatMap(values -> values.values().stream()).toList();
    }

    public <T extends CapabilityResourceLimit> CapabilityResourceLimitContribution<T> require(
            ResourceLimitSource source,
            ContractRef contractRef,
            Class<T> limitType) {
        Objects.requireNonNull(source, "source must not be null");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(limitType, "limitType must not be null");
        CapabilityResourceLimitContribution<?> contribution =
                bySource.getOrDefault(source, Map.of()).get(contractRef);
        if (contribution == null) {
            throw new IllegalStateException("missing resource contribution: " + source + "/" + contractRef);
        }
        if (!limitType.equals(contribution.limitType())) {
            throw new IllegalStateException("resource contribution type mismatch: " + contractRef);
        }
        @SuppressWarnings("unchecked")
        CapabilityResourceLimitContribution<T> typed =
                (CapabilityResourceLimitContribution<T>) contribution;
        return typed;
    }
}
