package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;

import java.time.Instant;
import java.util.Objects;

/** 不含 raw principal 的单 Invocation ACL execution evidence。 */
public record DocumentAclExecutionEvidence(
        String invocationId,
        String requestCorrelationId,
        String registrationIdentity,
        ExecutionSubjectRef subjectRef,
        DocumentCorpusKey corpusKey,
        DocumentPlanOperation operation,
        PermissionEvidenceReference permissionEvidence,
        String aclAuthorityVersion,
        String aclScopeDigest,
        String resolveOperationMetadataDigest,
        String profileProjectionDigest,
        ResourceLimitReference resourceLimitReference,
        Instant issuedAt,
        Instant expiresAt,
        String canonicalDigest) {

    public DocumentAclExecutionEvidence {
        if (invocationId == null || invocationId.isBlank()
                || requestCorrelationId == null || requestCorrelationId.isBlank()
                || registrationIdentity == null || registrationIdentity.isBlank()) {
            throw new IllegalArgumentException("ACL evidence execution binding must be complete");
        }
        Objects.requireNonNull(subjectRef);
        Objects.requireNonNull(corpusKey);
        Objects.requireNonNull(operation);
        Objects.requireNonNull(permissionEvidence);
        Objects.requireNonNull(resourceLimitReference);
        Objects.requireNonNull(issuedAt);
        Objects.requireNonNull(expiresAt);
        requireDigest(aclScopeDigest, "aclScopeDigest");
        requireDigest(resolveOperationMetadataDigest, "resolveOperationMetadataDigest");
        requireDigest(profileProjectionDigest, "profileProjectionDigest");
        requireDigest(canonicalDigest, "canonicalDigest");
    }

    private static void requireDigest(String value, String field) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(field + " must be lowercase SHA-256 hex");
        }
    }
}
