package com.dylan.agent.metadata.policy.model;

import java.time.Duration;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import com.dylan.agent.metadata.profile.model.PlanningBudgetLimits;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContributions;

/** 不可变 active policy version；Policy 只能收紧 profile 与 permission scope。 */
public record AgentPolicySnapshot(
        String policyVersion,
        Map<String, ProfileConstraints> profileConstraints,
        Map<String, CapabilityConstraints> capabilityConstraints,
        Map<String, DomainSecurityConstraints> domainSecurityConstraints,
        PlanningBudgetLimits globalPlanningBudgetUpperBound,
        CapabilityResourceLimitContributions resourceLimitContributions,
        Duration globalContextTtlUpperBound,
        Set<EmergencyRevocation> emergencyRevocations) {
    public AgentPolicySnapshot {
        policyVersion = requireNonBlank(policyVersion, "policyVersion");
        profileConstraints = Map.copyOf(Objects.requireNonNull(profileConstraints, "profileConstraints must not be null"));
        capabilityConstraints = Map.copyOf(Objects.requireNonNull(capabilityConstraints, "capabilityConstraints must not be null"));
        domainSecurityConstraints = Map.copyOf(Objects.requireNonNull(domainSecurityConstraints, "domainSecurityConstraints must not be null"));
        Objects.requireNonNull(globalPlanningBudgetUpperBound, "globalPlanningBudgetUpperBound must not be null");
        Objects.requireNonNull(resourceLimitContributions, "resourceLimitContributions must not be null");
        Objects.requireNonNull(globalContextTtlUpperBound, "globalContextTtlUpperBound must not be null");
        if (globalContextTtlUpperBound.isZero() || globalContextTtlUpperBound.isNegative()) {
            throw new IllegalArgumentException("globalContextTtlUpperBound must be positive");
        }
        emergencyRevocations = Set.copyOf(Objects.requireNonNull(emergencyRevocations, "emergencyRevocations must not be null"));
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
