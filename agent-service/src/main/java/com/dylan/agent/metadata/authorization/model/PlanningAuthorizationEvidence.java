package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;

import java.time.Instant;
import java.util.Objects;

/** One request-scoped evidence chain captured before Route. */
public record PlanningAuthorizationEvidence(
        String requestCorrelationId,
        String subjectRef,
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
        Instant capturedAt,
        Instant absoluteDeadline) {

    public PlanningAuthorizationEvidence {
        requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        subjectRef = requireNonBlank(subjectRef, "subjectRef");
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
        Objects.requireNonNull(capturedAt, "capturedAt must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
    }

    public String evidenceDigest() {
        return Integer.toHexString(Objects.hash(
                requestCorrelationId, subjectRef, profileKey, metadataBundleVersion,
                metadataBundleDigest, policyVersion, permissionEvidenceId, permissionVersion,
                domainMetadataEvidence));
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
