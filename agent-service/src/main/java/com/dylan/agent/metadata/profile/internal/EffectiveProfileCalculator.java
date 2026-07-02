package com.dylan.agent.metadata.profile.internal;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.metadata.policy.model.AgentPolicySnapshot;
import com.dylan.agent.metadata.policy.model.BudgetLimits;
import com.dylan.agent.metadata.policy.model.ProfileConstraints;
import com.dylan.agent.metadata.profile.model.AgentProfileDefinition;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;

import java.time.Duration;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** Stateless deterministic Profile ∩ Policy calculator. */
public final class EffectiveProfileCalculator {

    public EffectiveProfile compute(AgentProfileDefinition profile, AgentPolicySnapshot policy) {
        Objects.requireNonNull(profile, "profile must not be null");
        Objects.requireNonNull(policy, "policy must not be null");
        ProfileConstraints constraints = policy.profileConstraints().get(profile.key().agentId());
        if (constraints != null && !constraints.enabled()) {
            throw new IllegalStateException("profile disabled by policy: " + profile.key());
        }
        Set<String> capabilities = constraints == null || constraints.allowedCapabilityIds().isEmpty()
                ? profile.allowedCapabilityIds()
                : intersection(profile.allowedCapabilityIds(), constraints.allowedCapabilityIds());
        BudgetLimits policyBudget = constraints == null
                ? policy.globalBudgetUpperBound()
                : constraints.budgetLimits().orElse(policy.globalBudgetUpperBound());
        return new EffectiveProfile(
                profile.key(),
                policy.policyVersion(),
                capabilities,
                policy.domainSecurityConstraints().keySet(),
                constraints == null || constraints.readableContextTypes().isEmpty()
                        ? profile.readableContextTypes()
                        : intersection(profile.readableContextTypes(), constraints.readableContextTypes()),
                constraints == null || constraints.writableContextTypes().isEmpty()
                        ? profile.writableContextTypes()
                        : intersection(profile.writableContextTypes(), constraints.writableContextTypes()),
                minRisk(profile.maxRiskLevel(), constraints == null ? null : constraints.maxRiskLevel().orElse(null)),
                minExecutionMode(profile.maxExecutionMode(), constraints == null ? null : constraints.maxExecutionMode().orElse(null)),
                minDuration(profile.maxTotalDuration(), policyBudget.maxTotalDuration()),
                Math.min(profile.maxRepairAttempts(), policyBudget.maxRepairAttempts()),
                Math.min(profile.maxPageSize(), policyBudget.maxPageSize()),
                Math.min(profile.maxResultRows(), policyBudget.maxResultRows()),
                Math.min(profile.maxResultBytes(), policyBudget.maxResultBytes()));
    }

    private static <T> Set<T> intersection(Set<T> left, Set<T> right) {
        return left.stream().filter(right::contains).collect(Collectors.toUnmodifiableSet());
    }

    private static Duration minDuration(Duration left, Duration right) {
        return left.compareTo(right) <= 0 ? left : right;
    }

    private static AgentCapabilityRiskLevel minRisk(AgentCapabilityRiskLevel left, AgentCapabilityRiskLevel right) {
        return right == null || left.ordinal() <= right.ordinal() ? left : right;
    }

    private static AgentCapabilityExecutionMode minExecutionMode(
            AgentCapabilityExecutionMode left,
            AgentCapabilityExecutionMode right) {
        return right == null || left.ordinal() <= right.ordinal() ? left : right;
    }
}
