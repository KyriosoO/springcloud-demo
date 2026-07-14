package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.profile.model.PlanningBudgetLimits;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContributions;

import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Planning 使用的请求级 effective authorization envelope。
 *
 * <p>该类型是 Profile/Policy/Permission/Delegation 求交后的结果，
 * 供 D02_03 Catalog/D04 seam 消费。它不是权限缓存，不包含 JWT、role 事实、
 * policy 表达式、domain catalog 事实或 adapter metadata。</p>
 */
public final class PlanningEffectiveScope {

    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<CanonicalFieldRef, FieldAccess> fieldAccess;
    private final ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence;
    private final Set<RuntimeContextType> readableContextTypes;
    private final Set<RuntimeContextType> writableContextTypes;
    private final AgentCapabilityRiskLevel maxRiskLevel;
    private final AgentCapabilityExecutionMode maxExecutionMode;
    private final PlanningBudgetLimits planningBudgetLimits;
    private final CapabilityResourceLimitContributions resourceLimitContributions;

    public PlanningEffectiveScope(
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<CanonicalFieldRef, FieldAccess> fieldAccess,
            ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence,
            Set<RuntimeContextType> readableContextTypes,
            Set<RuntimeContextType> writableContextTypes,
            AgentCapabilityRiskLevel maxRiskLevel,
            AgentCapabilityExecutionMode maxExecutionMode,
            PlanningBudgetLimits planningBudgetLimits,
            CapabilityResourceLimitContributions resourceLimitContributions) {
        this.allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        this.allowedDomains = copyNonBlankSet(allowedDomains, "allowedDomains");
        this.fieldAccess = copyFieldAccess(fieldAccess);
        this.externalProcessingAuthorizationEvidence = Objects.requireNonNull(
                externalProcessingAuthorizationEvidence,
                "externalProcessingAuthorizationEvidence must not be null");
        this.readableContextTypes = Set.copyOf(
                Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        this.writableContextTypes = Set.copyOf(
                Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        this.maxRiskLevel = Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        this.maxExecutionMode = Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        this.planningBudgetLimits = Objects.requireNonNull(
                planningBudgetLimits, "planningBudgetLimits must not be null");
        this.resourceLimitContributions = Objects.requireNonNull(
                resourceLimitContributions, "resourceLimitContributions must not be null");
    }

    public Set<String> allowedCapabilityIds() {
        return allowedCapabilityIds;
    }

    public Set<String> allowedDomains() {
        return allowedDomains;
    }

    public Map<CanonicalFieldRef, FieldAccess> fieldAccess() {
        return fieldAccess;
    }

    public ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence() {
        return externalProcessingAuthorizationEvidence;
    }

    public Set<RuntimeContextType> readableContextTypes() {
        return readableContextTypes;
    }

    public Set<RuntimeContextType> writableContextTypes() {
        return writableContextTypes;
    }

    public AgentCapabilityRiskLevel maxRiskLevel() {
        return maxRiskLevel;
    }

    public AgentCapabilityExecutionMode maxExecutionMode() {
        return maxExecutionMode;
    }

    public PlanningBudgetLimits planningBudgetLimits() {
        return planningBudgetLimits;
    }

    public CapabilityResourceLimitContributions resourceLimitContributions() {
        return resourceLimitContributions;
    }

    private static Map<CanonicalFieldRef, FieldAccess> copyFieldAccess(
            Map<CanonicalFieldRef, FieldAccess> source) {
        Objects.requireNonNull(source, "fieldAccess must not be null");
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> Objects.requireNonNull(entry.getKey(), "field ref must not be null"),
                        entry -> Objects.requireNonNull(entry.getValue(), "field access must not be null")));
    }

    private static Set<String> copyNonBlankSet(Set<String> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.stream()
                .map(value -> requireNonBlank(value, name + " element"))
                .collect(Collectors.toUnmodifiableSet());
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    /**
     * canonical field 的 effective 字段级限制。
     */
    public record FieldAccess(
            boolean filterAllowed,
            boolean displayAllowed,
            Set<AgentOperator> allowedOperators,
            Set<String> allowedFunctions,
            Optional<MaskType> requiredMask) {

        public FieldAccess {
            allowedOperators = Set.copyOf(
                    Objects.requireNonNull(allowedOperators, "allowedOperators must not be null"));
            allowedFunctions = copyNonBlankSet(allowedFunctions, "allowedFunctions");
            requiredMask = Objects.requireNonNull(requiredMask, "requiredMask must not be null");
        }
    }
}
