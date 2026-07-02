package com.dylan.agent.metadata.profile.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.time.Duration;
import java.util.Objects;
import java.util.Set;

/** Profile-owned static definition; it never stores user permission or policy facts. */
public record AgentProfileDefinition(
        AgentProfileVersionKey key,
        ProfileBehaviorAssetRef promptProfileRef,
        Set<String> allowedCapabilityIds,
        Set<RuntimeContextType> readableContextTypes,
        Set<RuntimeContextType> writableContextTypes,
        AgentCapabilityRiskLevel maxRiskLevel,
        AgentCapabilityExecutionMode maxExecutionMode,
        Duration maxTotalDuration,
        int maxRepairAttempts,
        int maxPageSize,
        int maxResultRows,
        long maxResultBytes) {

    public AgentProfileDefinition {
        Objects.requireNonNull(key, "key must not be null");
        Objects.requireNonNull(promptProfileRef, "promptProfileRef must not be null");
        allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        readableContextTypes = Set.copyOf(Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        writableContextTypes = Set.copyOf(Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        requirePositive(maxTotalDuration, "maxTotalDuration");
        if (maxRepairAttempts < 0 || maxPageSize < 0 || maxResultRows < 0 || maxResultBytes < 0) {
            throw new IllegalArgumentException("profile numeric limits must be non-negative");
        }
    }

    private static Duration requirePositive(Duration value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
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
