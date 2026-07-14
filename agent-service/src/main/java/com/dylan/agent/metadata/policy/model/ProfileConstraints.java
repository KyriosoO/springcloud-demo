package com.dylan.agent.metadata.policy.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import com.dylan.agent.metadata.profile.model.PlanningBudgetLimits;

/** 只能收紧 Profile 的 deployment policy constraints。 */
public record ProfileConstraints(
        boolean enabled,
        Set<String> allowedCapabilityIds,
        Set<RuntimeContextType> readableContextTypes,
        Set<RuntimeContextType> writableContextTypes,
        Optional<AgentCapabilityRiskLevel> maxRiskLevel,
        Optional<AgentCapabilityExecutionMode> maxExecutionMode,
        Optional<PlanningBudgetLimits> planningBudgetLimits) {
    public ProfileConstraints {
        allowedCapabilityIds = Set.copyOf(Objects.requireNonNull(allowedCapabilityIds, "allowedCapabilityIds must not be null"));
        readableContextTypes = Set.copyOf(Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        writableContextTypes = Set.copyOf(Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        maxRiskLevel = Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        maxExecutionMode = Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        planningBudgetLimits = Objects.requireNonNull(
                planningBudgetLimits, "planningBudgetLimits must not be null");
    }
}
