package com.dylan.agent.metadata.profile.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContributions;
import java.util.Objects;
import java.util.Set;

/** Profile 拥有的静态 definition；绝不存储 user permission 或 policy facts。 */
public record AgentProfileDefinition(
        AgentProfileVersionKey key,
        ProfileBehaviorAssetRef promptProfileRef,
        Set<String> allowedCapabilityIds,
        Set<RuntimeContextType> readableContextTypes,
        Set<RuntimeContextType> writableContextTypes,
        AgentCapabilityRiskLevel maxRiskLevel,
        AgentCapabilityExecutionMode maxExecutionMode,
        PlanningBudgetLimits planningBudgetLimits,
        CapabilityResourceLimitContributions resourceLimitContributions) {

    public AgentProfileDefinition {
        Objects.requireNonNull(key, "key must not be null");
        Objects.requireNonNull(promptProfileRef, "promptProfileRef must not be null");
        allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        readableContextTypes = Set.copyOf(Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        writableContextTypes = Set.copyOf(Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        Objects.requireNonNull(planningBudgetLimits, "planningBudgetLimits must not be null");
        Objects.requireNonNull(resourceLimitContributions, "resourceLimitContributions must not be null");
    }

    private static Set<String> copyNonBlankSet(Set<String> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.stream()
                .map(value -> {
                    Objects.requireNonNull(value, name + " element must not be null");
                    String normalized = value.trim();
                    if (normalized.isEmpty()) {
                        throw new IllegalArgumentException(name + " element must not be blank");
                    }
                    return normalized;
                })
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }
}
