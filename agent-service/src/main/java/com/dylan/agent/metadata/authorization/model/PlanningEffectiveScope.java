package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.time.Duration;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Request-scoped effective authorization envelope for Planning.
 *
 * <p>This is the already-intersected Profile/Policy/Permission/Delegation
 * result consumed by D02_03 Catalog/D04 seam. It is not a permission cache and
 * does not contain JWT, role facts, policy expressions, domain catalog facts or
 * adapter metadata.</p>
 */
public final class PlanningEffectiveScope {

    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<CanonicalFieldRef, FieldAccess> fieldAccess;
    private final Set<RuntimeContextType> readableContextTypes;
    private final Set<RuntimeContextType> writableContextTypes;
    private final AgentCapabilityRiskLevel maxRiskLevel;
    private final AgentCapabilityExecutionMode maxExecutionMode;
    private final Duration maxTotalDuration;
    private final int maxRepairAttempts;
    private final int maxPageSize;
    private final int maxResultRows;
    private final long maxResultBytes;

    public PlanningEffectiveScope(
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<CanonicalFieldRef, FieldAccess> fieldAccess,
            Set<RuntimeContextType> readableContextTypes,
            Set<RuntimeContextType> writableContextTypes,
            AgentCapabilityRiskLevel maxRiskLevel,
            AgentCapabilityExecutionMode maxExecutionMode,
            Duration maxTotalDuration,
            int maxRepairAttempts,
            int maxPageSize,
            int maxResultRows,
            long maxResultBytes) {
        this.allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        this.allowedDomains = copyNonBlankSet(allowedDomains, "allowedDomains");
        this.fieldAccess = copyFieldAccess(fieldAccess);
        this.readableContextTypes = Set.copyOf(
                Objects.requireNonNull(readableContextTypes, "readableContextTypes must not be null"));
        this.writableContextTypes = Set.copyOf(
                Objects.requireNonNull(writableContextTypes, "writableContextTypes must not be null"));
        this.maxRiskLevel = Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        this.maxExecutionMode = Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        this.maxTotalDuration = requirePositive(maxTotalDuration, "maxTotalDuration");
        if (maxRepairAttempts < 0) {
            throw new IllegalArgumentException("maxRepairAttempts must be non-negative");
        }
        if (maxPageSize < 0) {
            throw new IllegalArgumentException("maxPageSize must be non-negative");
        }
        if (maxResultRows < 0) {
            throw new IllegalArgumentException("maxResultRows must be non-negative");
        }
        if (maxResultBytes < 0) {
            throw new IllegalArgumentException("maxResultBytes must be non-negative");
        }
        this.maxRepairAttempts = maxRepairAttempts;
        this.maxPageSize = maxPageSize;
        this.maxResultRows = maxResultRows;
        this.maxResultBytes = maxResultBytes;
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

    public Duration maxTotalDuration() {
        return maxTotalDuration;
    }

    public int maxRepairAttempts() {
        return maxRepairAttempts;
    }

    public int maxPageSize() {
        return maxPageSize;
    }

    public int maxResultRows() {
        return maxResultRows;
    }

    public long maxResultBytes() {
        return maxResultBytes;
    }

    private static Duration requirePositive(Duration value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
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
     * Effective field-level limits for a canonical field.
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
