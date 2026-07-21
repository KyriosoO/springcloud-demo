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

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.Duration;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** Planning 阶段冻结的 capability-scoped 不可变授权快照。 */
public final class AuthorizationSnapshot {

    private final String snapshotId;
    private final String invocationId;
    private final String requestCorrelationId;
    private final ExecutionSubjectRef subject;
    private final ContextOwnerRef owner;
    private final ConversationScope scope;
    private final AgentProfileRef agentProfileRef;
    private final String policyVersion;
    private final String permissionEvidenceId;
    private final String permissionVersion;
    private final DelegationConstraintRef delegationConstraintRef;
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
    private final Instant capturedAt;
    private final Instant absoluteDeadline;
    private final DomainMetadataEvidence domainMetadataEvidence;
    private final EffectiveCapabilityResourceLimits resourceLimits;
    private final String safeReference;

    public AuthorizationSnapshot(
            String snapshotId,
            String invocationId,
            String requestCorrelationId,
            ExecutionSubjectRef subject,
            ContextOwnerRef owner,
            ConversationScope scope,
            AgentProfileRef agentProfileRef,
            String policyVersion,
            String permissionEvidenceId,
            String permissionVersion,
            DelegationConstraintRef delegationConstraintRef,
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
            Instant capturedAt,
            Instant absoluteDeadline,
            DomainMetadataEvidence domainMetadataEvidence,
            EffectiveCapabilityResourceLimits resourceLimits) {
        this.snapshotId = requireNonBlank(snapshotId, "snapshotId");
        this.invocationId = requireNonBlank(invocationId, "invocationId");
        this.requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        this.subject = Objects.requireNonNull(subject, "subject must not be null");
        this.owner = Objects.requireNonNull(owner, "owner must not be null");
        this.scope = Objects.requireNonNull(scope, "scope must not be null");
        this.agentProfileRef = Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        if (agentProfileRef.expectedVersion().isEmpty()) {
            throw new IllegalArgumentException("agentProfileRef must bind an exact version");
        }
        this.policyVersion = requireNonBlank(policyVersion, "policyVersion");
        this.permissionEvidenceId = requireNonBlank(permissionEvidenceId, "permissionEvidenceId");
        this.permissionVersion = requireNonBlank(permissionVersion, "permissionVersion");
        this.delegationConstraintRef = Objects.requireNonNull(
                delegationConstraintRef, "delegationConstraintRef must not be null");
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
        this.maxRiskLevel = Objects.requireNonNull(maxRiskLevel, "maxRiskLevel must not be null");
        this.maxExecutionMode = Objects.requireNonNull(maxExecutionMode, "maxExecutionMode must not be null");
        this.globalContextTtlUpperBound = Objects.requireNonNull(
                globalContextTtlUpperBound, "globalContextTtlUpperBound must not be null");
        if (globalContextTtlUpperBound.isZero() || globalContextTtlUpperBound.isNegative()) {
            throw new IllegalArgumentException("globalContextTtlUpperBound must be positive");
        }
        this.capturedAt = Objects.requireNonNull(capturedAt, "capturedAt must not be null");
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
        if (!capturedAt.isBefore(absoluteDeadline)) {
            throw new IllegalArgumentException("capturedAt must be before absoluteDeadline");
        }
        this.domainMetadataEvidence = Objects.requireNonNull(
                domainMetadataEvidence, "domainMetadataEvidence must not be null");
        this.resourceLimits = Objects.requireNonNull(resourceLimits, "resourceLimits must not be null");
        var binding = resourceLimits.bindingIdentity();
        if (!invocationId.equals(binding.invocationId())
                || !requestCorrelationId.equals(binding.requestCorrelationId())) {
            throw new IllegalArgumentException("resource limits binding does not match authorization snapshot");
        }
        this.safeReference = createSafeReference();
    }

    public String snapshotId() { return snapshotId; }
    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public ExecutionSubjectRef subject() { return subject; }
    public String subjectRef() { return subject.type() + ":" + subject.id(); }
    public ContextOwnerRef owner() { return owner; }
    public ConversationScope scope() { return scope; }
    public AgentProfileRef agentProfileRef() { return agentProfileRef; }
    public String profileVersion() { return agentProfileRef.expectedVersion().orElseThrow(); }
    public String policyVersion() { return policyVersion; }
    public String permissionEvidenceId() { return permissionEvidenceId; }
    public String permissionVersion() { return permissionVersion; }
    public DelegationConstraintRef delegationConstraintRef() { return delegationConstraintRef; }
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
    public Instant capturedAt() { return capturedAt; }
    public Instant snapshotTime() { return capturedAt; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
    public DomainMetadataEvidence domainMetadataEvidence() { return domainMetadataEvidence; }
    public EffectiveCapabilityResourceLimits resourceLimits() { return resourceLimits; }

    /**
     * ASR-1：不暴露权限正文、但绑定本快照安全语义与同一资源限额引用的持久化引用。
     * capturedAt 不参与计算；绝对截止时间和带可用性时点的 Domain evidence 仍属于安全绑定。
     */
    public String safeReference() { return safeReference; }

    private String createSafeReference() {
        DigestWriter writer = new DigestWriter("ASR-1")
                .text(snapshotId)
                .text(invocationId)
                .text(requestCorrelationId)
                .text(subject.type()).text(subject.id())
                .text(owner.type()).text(owner.id())
                .text(scope.scopeId())
                .text(agentProfileRef.agentId()).text(profileVersion())
                .text(policyVersion)
                .text(permissionEvidenceId).text(permissionVersion)
                .text(delegationConstraintRef.constraintId()).text(delegationConstraintRef.version());
        writeStringSet(writer, "capabilities", allowedCapabilityIds);
        writeStringSet(writer, "domains", allowedDomains);
        writeStringSetMap(writer, "fields", allowedFields);
        writeOperatorMap(writer, allowedOperators);
        writeStringSetMap(writer, "functions", allowedFunctions);
        writer.text("masks").integer(fieldMasks.size());
        fieldMasks.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry ->
                writer.text(entry.getKey()).text(entry.getValue().name()));
        writer.text(externalProcessingAuthorizationEvidence.canonicalDigest());
        writeEnumSet(writer, "readable-contexts", readableContextTypes);
        writeEnumSet(writer, "writable-contexts", writableContextTypes);
        writer.text(maxRiskLevel.name()).text(maxExecutionMode.name())
                .longValue(globalContextTtlUpperBound.getSeconds())
                .integer(globalContextTtlUpperBound.getNano())
                .text(absoluteDeadline.toString())
                .text(domainMetadataEvidence.safeRef());
        var limitRef = resourceLimits.reference();
        writer.text(limitRef.contractRef().namespace())
                .text(limitRef.contractRef().name())
                .text(limitRef.contractRef().version())
                .text(limitRef.canonicalDigest())
                .text(limitRef.invocationId())
                .text(limitRef.registrationIdentity());
        return "ASR-1:" + writer.hex();
    }

    private static void writeStringSet(DigestWriter writer, String label, Set<String> values) {
        writer.text(label).integer(values.size());
        values.stream().sorted().forEach(writer::text);
    }

    private static void writeStringSetMap(
            DigestWriter writer, String label, Map<String, Set<String>> values) {
        writer.text(label).integer(values.size());
        values.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry -> {
            writer.text(entry.getKey()).integer(entry.getValue().size());
            entry.getValue().stream().sorted().forEach(writer::text);
        });
    }

    private static void writeOperatorMap(
            DigestWriter writer, Map<String, Set<AgentOperator>> values) {
        writer.text("operators").integer(values.size());
        values.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry -> {
            writer.text(entry.getKey()).integer(entry.getValue().size());
            entry.getValue().stream().map(Enum::name).sorted().forEach(writer::text);
        });
    }

    private static void writeEnumSet(DigestWriter writer, String label, Set<? extends Enum<?>> values) {
        writer.text(label).integer(values.size());
        values.stream().map(Enum::name).sorted(Comparator.naturalOrder()).forEach(writer::text);
    }

    private static final class DigestWriter {
        private final MessageDigest digest;

        private DigestWriter(String generation) {
            try {
                this.digest = MessageDigest.getInstance("SHA-256");
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException("SHA-256 unavailable", ex);
            }
            text(generation);
        }

        private DigestWriter text(String value) {
            byte[] bytes = Objects.requireNonNull(value, "digest value must not be null")
                    .getBytes(StandardCharsets.UTF_8);
            integer(bytes.length);
            digest.update(bytes);
            return this;
        }

        private DigestWriter integer(int value) {
            digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(value).array());
            return this;
        }

        private DigestWriter longValue(long value) {
            digest.update(ByteBuffer.allocate(Long.BYTES).putLong(value).array());
            return this;
        }

        private String hex() { return HexFormat.of().formatHex(digest.digest()); }
    }

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
