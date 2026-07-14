package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.Duration;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Objects;

/** Route 前捕获的单请求 evidence chain。 */
public record PlanningAuthorizationEvidence(
        String invocationId,
        String requestCorrelationId,
        ExecutionSubjectRef subject,
        ContextOwnerRef owner,
        ConversationScope scope,
        AgentProfileRef agentProfileRef,
        AgentProfileVersionKey profileKey,
        String metadataBundleVersion,
        String metadataBundleDigest,
        String policyVersion,
        String permissionEvidenceId,
        String permissionVersion,
        DelegationConstraintRef delegationConstraintRef,
        EffectiveProfile effectiveProfile,
        PlanningEffectiveScope planningScope,
        DomainMetadataEvidence domainMetadataEvidence,
        Duration globalContextTtlUpperBound,
        Instant capturedAt,
        Instant absoluteDeadline) {

    public PlanningAuthorizationEvidence {
        invocationId = requireNonBlank(invocationId, "invocationId");
        requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        Objects.requireNonNull(subject, "subject must not be null");
        Objects.requireNonNull(owner, "owner must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        if (agentProfileRef.expectedVersion().isEmpty()) {
            throw new IllegalArgumentException("agentProfileRef must bind an exact version");
        }
        Objects.requireNonNull(profileKey, "profileKey must not be null");
        metadataBundleVersion = requireNonBlank(metadataBundleVersion, "metadataBundleVersion");
        metadataBundleDigest = requireNonBlank(metadataBundleDigest, "metadataBundleDigest");
        policyVersion = requireNonBlank(policyVersion, "policyVersion");
        permissionEvidenceId = requireNonBlank(permissionEvidenceId, "permissionEvidenceId");
        permissionVersion = requireNonBlank(permissionVersion, "permissionVersion");
        Objects.requireNonNull(delegationConstraintRef, "delegationConstraintRef must not be null");
        Objects.requireNonNull(effectiveProfile, "effectiveProfile must not be null");
        Objects.requireNonNull(planningScope, "planningScope must not be null");
        Objects.requireNonNull(domainMetadataEvidence, "domainMetadataEvidence must not be null");
        Objects.requireNonNull(globalContextTtlUpperBound, "globalContextTtlUpperBound must not be null");
        if (globalContextTtlUpperBound.isZero() || globalContextTtlUpperBound.isNegative()) {
            throw new IllegalArgumentException("globalContextTtlUpperBound must be positive");
        }
        Objects.requireNonNull(capturedAt, "capturedAt must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
    }

    public String evidenceDigest() {
        DigestWriter writer = new DigestWriter("PAE-1")
                .text(invocationId).text(requestCorrelationId)
                .text(subject.type()).text(subject.id())
                .text(owner.type()).text(owner.id()).text(scope.scopeId())
                .text(agentProfileRef.agentId()).text(agentProfileRef.expectedVersion().orElseThrow())
                .text(profileKey.agentId()).text(profileKey.version())
                .text(metadataBundleVersion).text(metadataBundleDigest).text(policyVersion)
                .text(permissionEvidenceId).text(permissionVersion)
                .text(delegationConstraintRef.constraintId()).text(delegationConstraintRef.version())
                .text(domainMetadataEvidence.safeRef())
                .text(globalContextTtlUpperBound.toString())
                .text(capturedAt.toString()).text(absoluteDeadline.toString());
        writePlanningScope(writer, planningScope);
        return writer.hex();
    }

    private static void writePlanningScope(DigestWriter writer, PlanningEffectiveScope planningScope) {
        writer.integer(planningScope.allowedCapabilityIds().size());
        planningScope.allowedCapabilityIds().stream().sorted().forEach(writer::text);
        writer.integer(planningScope.allowedDomains().size());
        planningScope.allowedDomains().stream().sorted().forEach(writer::text);

        writer.integer(planningScope.fieldAccess().size());
        planningScope.fieldAccess().entrySet().stream()
                .sorted(Comparator.comparing((java.util.Map.Entry<com.dylan.agent.metadata.domain.port.CanonicalFieldRef,
                        PlanningEffectiveScope.FieldAccess> entry) -> entry.getKey().domain())
                        .thenComparing(entry -> entry.getKey().field()))
                .forEach(entry -> {
                    PlanningEffectiveScope.FieldAccess access = entry.getValue();
                    writer.text(entry.getKey().domain()).text(entry.getKey().field())
                            .bool(access.filterAllowed()).bool(access.displayAllowed());
                    writer.integer(access.allowedOperators().size());
                    access.allowedOperators().stream().map(Enum::name).sorted().forEach(writer::text);
                    writer.integer(access.allowedFunctions().size());
                    access.allowedFunctions().stream().sorted().forEach(writer::text);
                    writer.text(access.requiredMask().map(Enum::name).orElse(""));
                });

        writer.text(planningScope.externalProcessingAuthorizationEvidence().canonicalDigest());
        writer.integer(planningScope.readableContextTypes().size());
        planningScope.readableContextTypes().stream().map(Enum::name).sorted().forEach(writer::text);
        writer.integer(planningScope.writableContextTypes().size());
        planningScope.writableContextTypes().stream().map(Enum::name).sorted().forEach(writer::text);
        writer.text(planningScope.maxRiskLevel().name()).text(planningScope.maxExecutionMode().name())
                .text(planningScope.planningBudgetLimits().maxTotalDuration().toString())
                .integer(planningScope.planningBudgetLimits().maxRepairAttempts());

        var contributions = planningScope.resourceLimitContributions().all().stream()
                .sorted(Comparator.comparing(
                                (com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContribution<?> value)
                                        -> value.source().name())
                        .thenComparing(value -> value.contractRef().namespace())
                        .thenComparing(value -> value.contractRef().name())
                        .thenComparing(value -> value.contractRef().version())
                        .thenComparing(value -> value.evidenceRef()))
                .toList();
        writer.integer(contributions.size());
        contributions.forEach(value -> writer.text(value.source().name())
                .text(value.contractRef().namespace()).text(value.contractRef().name())
                .text(value.contractRef().version()).text(value.limitType().getName())
                .text(value.evidenceRef()));
    }

    private static final class DigestWriter {
        private final MessageDigest digest;

        private DigestWriter(String prefix) {
            try {
                digest = MessageDigest.getInstance("SHA-256");
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException("SHA-256 unavailable", ex);
            }
            text(prefix);
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

        private DigestWriter bool(boolean value) {
            digest.update((byte) (value ? 1 : 0));
            return this;
        }

        private String hex() {
            return HexFormat.of().formatHex(digest.digest());
        }
    }

    public String subjectRef() {
        return subject.type() + ":" + subject.id();
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
