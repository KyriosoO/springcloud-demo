package com.dylan.agent.metadata.catalog;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;

import java.time.Duration;
import java.util.Objects;
import java.util.Set;

/** Route 使用的请求级 available capability 投影。 */
public record AvailableCapability(
        String capabilityId,
        AgentPlanKind planKind,
        AgentDomainMode domainMode,
        CapabilityRoutingDescriptor routingDescriptor,
        Set<String> allowedDomains,
        AgentCapabilityRiskLevel riskLevel,
        AgentCapabilityExecutionMode executionMode,
        Duration maxTotalDuration,
        int maxRepairAttempts,
        int maxPageSize,
        int maxResultRows,
        long maxResultBytes,
        String registrationIdentity) {
    public AvailableCapability {
        capabilityId = requireNonBlank(capabilityId, "capabilityId");
        Objects.requireNonNull(planKind, "planKind must not be null");
        Objects.requireNonNull(domainMode, "domainMode must not be null");
        Objects.requireNonNull(routingDescriptor, "routingDescriptor must not be null");
        allowedDomains = Set.copyOf(Objects.requireNonNull(allowedDomains, "allowedDomains must not be null"));
        Objects.requireNonNull(riskLevel, "riskLevel must not be null");
        Objects.requireNonNull(executionMode, "executionMode must not be null");
        Objects.requireNonNull(maxTotalDuration, "maxTotalDuration must not be null");
        if (maxRepairAttempts < 0 || maxPageSize < 0 || maxResultRows < 0 || maxResultBytes < 0) {
            throw new IllegalArgumentException("available capability numeric limits must be non-negative");
        }
        registrationIdentity = requireNonBlank(registrationIdentity, "registrationIdentity");
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
