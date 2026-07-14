package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Instant;
import java.time.Duration;
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
        String canonical = invocationId + "|" + requestCorrelationId + "|" + subjectRef() + "|"
                + owner.type() + ":" + owner.id() + "|" + scope.scopeId() + "|" + profileKey + "|"
                + metadataBundleVersion + "|" + metadataBundleDigest + "|" + policyVersion + "|"
                + permissionEvidenceId + "|" + permissionVersion + "|" + domainMetadataEvidence.safeRef()
                + "|" + globalContextTtlUpperBound;
        try {
            return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
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
