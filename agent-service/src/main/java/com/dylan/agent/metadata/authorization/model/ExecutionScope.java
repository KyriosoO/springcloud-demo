package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** Execution 复检后的不可变授权范围；只能与 Snapshot 相同或更严格。 */
public final class ExecutionScope {

    private final String invocationId;
    private final String requestCorrelationId;
    private final ExecutionSubjectRef subject;
    private final ContextOwnerRef owner;
    private final ConversationScope scope;
    private final AgentProfileRef agentProfileRef;
    private final DomainMetadataEvidence domainMetadataEvidence;
    private final Instant recheckedAt;
    private final Instant absoluteDeadline;
    private final String currentPermissionEvidenceId;
    private final String currentPermissionVersion;
    private final String currentPolicyVersion;
    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<String, Set<String>> allowedFields;
    private final Map<String, Set<AgentOperator>> allowedOperators;
    private final Map<String, Set<String>> allowedFunctions;
    private final Map<String, MaskType> fieldMasks;
    private final ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence;
    private final Set<RuntimeContextType> readableContextTypes;
    private final Set<RuntimeContextType> writableContextTypes;
    private final AgentCapabilityRiskLevel maxRiskLevel;
    private final AgentCapabilityExecutionMode maxExecutionMode;
    private final Duration globalContextTtlUpperBound;
    private final EffectiveCapabilityResourceLimits resourceLimits;

    public ExecutionScope(
            String invocationId,
            String requestCorrelationId,
            ExecutionSubjectRef subject,
            ContextOwnerRef owner,
            ConversationScope scope,
            AgentProfileRef agentProfileRef,
            DomainMetadataEvidence domainMetadataEvidence,
            Instant recheckedAt,
            Instant absoluteDeadline,
            String currentPermissionEvidenceId,
            String currentPermissionVersion,
            String currentPolicyVersion,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields,
            Map<String, Set<AgentOperator>> allowedOperators,
            Map<String, Set<String>> allowedFunctions,
            Map<String, MaskType> fieldMasks,
            ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence,
            Set<RuntimeContextType> readableContextTypes,
            Set<RuntimeContextType> writableContextTypes,
            AgentCapabilityRiskLevel maxRiskLevel,
            AgentCapabilityExecutionMode maxExecutionMode,
            Duration globalContextTtlUpperBound,
            EffectiveCapabilityResourceLimits resourceLimits) {
        this.invocationId = requireNonBlank(invocationId, "invocationId");
        this.requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        this.subject = Objects.requireNonNull(subject, "subject must not be null");
        this.owner = Objects.requireNonNull(owner, "owner must not be null");
        this.scope = Objects.requireNonNull(scope, "scope must not be null");
        this.agentProfileRef = Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        if (agentProfileRef.expectedVersion().isEmpty()) {
            throw new IllegalArgumentException("agentProfileRef must bind an exact version");
        }
        this.domainMetadataEvidence = Objects.requireNonNull(domainMetadataEvidence);
        this.recheckedAt = Objects.requireNonNull(recheckedAt);
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
        if (!recheckedAt.isBefore(absoluteDeadline)) {
            throw new IllegalArgumentException("recheckedAt must be before absoluteDeadline");
        }
        this.currentPermissionEvidenceId = requireNonBlank(
                currentPermissionEvidenceId, "currentPermissionEvidenceId");
        this.currentPermissionVersion = requireNonBlank(currentPermissionVersion, "currentPermissionVersion");
        this.currentPolicyVersion = requireNonBlank(currentPolicyVersion, "currentPolicyVersion");
        this.allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        this.allowedDomains = copyNonBlankSet(allowedDomains, "allowedDomains");
        this.allowedFields = copyStringSetMap(allowedFields, "allowedFields");
        this.allowedOperators = copySetMap(allowedOperators, "allowedOperators");
        this.allowedFunctions = copyStringSetMap(allowedFunctions, "allowedFunctions");
        this.fieldMasks = copyValueMap(fieldMasks, "fieldMasks");
        this.externalProcessingAuthorizationEvidence = Objects.requireNonNull(
                externalProcessingAuthorizationEvidence,
                "externalProcessingAuthorizationEvidence must not be null");
        this.readableContextTypes = Set.copyOf(Objects.requireNonNull(readableContextTypes));
        this.writableContextTypes = Set.copyOf(Objects.requireNonNull(writableContextTypes));
        this.maxRiskLevel = Objects.requireNonNull(maxRiskLevel);
        this.maxExecutionMode = Objects.requireNonNull(maxExecutionMode);
        this.globalContextTtlUpperBound = Objects.requireNonNull(globalContextTtlUpperBound);
        if (globalContextTtlUpperBound.isZero() || globalContextTtlUpperBound.isNegative()) {
            throw new IllegalArgumentException("globalContextTtlUpperBound must be positive");
        }
        this.resourceLimits = Objects.requireNonNull(resourceLimits, "resourceLimits must not be null");
        var binding = resourceLimits.bindingIdentity();
        if (!invocationId.equals(binding.invocationId())
                || !requestCorrelationId.equals(binding.requestCorrelationId())) {
            throw new IllegalArgumentException("resource limits binding does not match execution scope");
        }
    }

    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public ExecutionSubjectRef subject() { return subject; }
    public String subjectRef() { return subject.type() + ":" + subject.id(); }
    public ContextOwnerRef owner() { return owner; }
    public ConversationScope scope() { return scope; }
    public AgentProfileRef agentProfileRef() { return agentProfileRef; }
    public DomainMetadataEvidence domainMetadataEvidence() { return domainMetadataEvidence; }
    public Instant recheckedAt() { return recheckedAt; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
    public Duration remainingDeadline() { return Duration.between(recheckedAt, absoluteDeadline); }
    public String currentPermissionEvidenceId() { return currentPermissionEvidenceId; }
    public String currentPermissionVersion() { return currentPermissionVersion; }
    public String currentPolicyVersion() { return currentPolicyVersion; }
    public Set<String> allowedCapabilityIds() { return allowedCapabilityIds; }
    public Set<String> allowedDomains() { return allowedDomains; }
    public Map<String, Set<String>> allowedFields() { return allowedFields; }
    public Map<String, Set<AgentOperator>> allowedOperators() { return allowedOperators; }
    public Map<String, Set<String>> allowedFunctions() { return allowedFunctions; }
    public Map<String, MaskType> fieldMasks() { return fieldMasks; }
    public ExternalProcessingAuthorizationEvidence externalProcessingAuthorizationEvidence() {
        return externalProcessingAuthorizationEvidence;
    }
    public Set<RuntimeContextType> readableContextTypes() { return readableContextTypes; }
    public Set<RuntimeContextType> writableContextTypes() { return writableContextTypes; }
    public AgentCapabilityRiskLevel maxRiskLevel() { return maxRiskLevel; }
    public AgentCapabilityExecutionMode maxExecutionMode() { return maxExecutionMode; }
    public Duration globalContextTtlUpperBound() { return globalContextTtlUpperBound; }
    public EffectiveCapabilityResourceLimits resourceLimits() { return resourceLimits; }

    private static Map<String, Set<String>> copyStringSetMap(Map<String, Set<String>> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.entrySet().stream().collect(Collectors.toUnmodifiableMap(
                entry -> requireNonBlank(entry.getKey(), name + " key"),
                entry -> copyNonBlankSet(entry.getValue(), name + " values")));
    }

    private static <T> Map<String, Set<T>> copySetMap(Map<String, Set<T>> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.entrySet().stream().collect(Collectors.toUnmodifiableMap(
                entry -> requireNonBlank(entry.getKey(), name + " key"),
                entry -> Set.copyOf(Objects.requireNonNull(entry.getValue(), name + " values"))));
    }

    private static <T> Map<String, T> copyValueMap(Map<String, T> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.entrySet().stream().collect(Collectors.toUnmodifiableMap(
                entry -> requireNonBlank(entry.getKey(), name + " key"),
                entry -> Objects.requireNonNull(entry.getValue(), name + " value")));
    }

    private static Set<String> copyNonBlankSet(Set<String> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.stream().map(value -> requireNonBlank(value, name + " element"))
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
}
