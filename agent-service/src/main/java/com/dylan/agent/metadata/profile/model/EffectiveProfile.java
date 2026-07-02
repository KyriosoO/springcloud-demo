package com.dylan.agent.metadata.profile.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.time.Duration;
import java.util.Objects;
import java.util.Set;

/** Deterministic Profile ∩ Policy result; UserPermission is applied later. */
public record EffectiveProfile(
        AgentProfileVersionKey profileKey,
        String policyVersion,
        Set<String> allowedCapabilityIds,
        Set<String> allowedDomains,
        Set<RuntimeContextType> readableContextTypes,
        Set<RuntimeContextType> writableContextTypes,
        AgentCapabilityRiskLevel maxRiskLevel,
        AgentCapabilityExecutionMode maxExecutionMode,
        Duration maxTotalDuration,
        int maxRepairAttempts,
        int maxPageSize,
        int maxResultRows,
        long maxResultBytes) {

    public EffectiveProfile {
        Objects.requireNonNull(profileKey, "profileKey must not be null");
        policyVersion = requireNonBlank(policyVersion, "policyVersion");
        allowedCapabilityIds = Set.copyOf(Objects.requireNonNull(allowedCapabilityIds, "allowedCapabilityIds must not be null"));
        allowedDomains = Set.copyOf(Objects.requireNonNull(allowedDomains, "allowedDomains must not be null"));
        readableContextTypes = Set.copyOf(Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        writableContextTypes = Set.copyOf(Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        Objects.requireNonNull(maxTotalDuration, "maxTotalDuration must not be null");
        if (maxRepairAttempts < 0 || maxPageSize < 0 || maxResultRows < 0 || maxResultBytes < 0) {
            throw new IllegalArgumentException("effective profile numeric limits must be non-negative");
        }
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
