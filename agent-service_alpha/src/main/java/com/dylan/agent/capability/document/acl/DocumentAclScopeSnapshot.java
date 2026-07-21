package com.dylan.agent.capability.document.acl;

import java.time.Instant;
import java.util.Objects;
import java.util.Set;

/** strict authority response 本地校验和 canonicalization 后的短生命周期 scope。 */
public record DocumentAclScopeSnapshot(
        String tenantId,
        String subjectPrincipalId,
        Set<String> departmentIds,
        Set<String> roleIds,
        Set<String> attributeKeys,
        DocumentIdConstraint documentIdConstraint,
        Set<String> deniedDocumentIds,
        String authorityVersion,
        String permissionVersion,
        Instant issuedAt,
        Instant expiresAt,
        String authorityEvidenceRef,
        String locallyComputedCanonicalDigest) {

    public DocumentAclScopeSnapshot {
        tenantId = requireText(tenantId, "tenantId");
        subjectPrincipalId = requireText(subjectPrincipalId, "subjectPrincipalId");
        departmentIds = OnlyDocumentIds.stableSet(departmentIds, "departmentIds");
        roleIds = OnlyDocumentIds.stableSet(roleIds, "roleIds");
        attributeKeys = OnlyDocumentIds.stableSet(attributeKeys, "attributeKeys");
        Objects.requireNonNull(documentIdConstraint, "documentIdConstraint must not be null");
        deniedDocumentIds = OnlyDocumentIds.stableSet(deniedDocumentIds, "deniedDocumentIds");
        authorityVersion = requireVersion(authorityVersion, "authorityVersion");
        permissionVersion = requireText(permissionVersion, "permissionVersion");
        Objects.requireNonNull(issuedAt, "issuedAt must not be null");
        Objects.requireNonNull(expiresAt, "expiresAt must not be null");
        if (expiresAt.isBefore(issuedAt) || expiresAt.equals(issuedAt)) {
            throw new IllegalArgumentException("expiresAt must be after issuedAt");
        }
        authorityEvidenceRef = requireText(authorityEvidenceRef, "authorityEvidenceRef");
        locallyComputedCanonicalDigest = requireDigest(
                locallyComputedCanonicalDigest, "locallyComputedCanonicalDigest");
    }

    public boolean isCurrentAt(Instant now) {
        return !issuedAt.isAfter(now) && expiresAt.isAfter(now);
    }

    private static String requireVersion(String value, String name) {
        String normalized = requireText(value, name);
        if (!normalized.matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")) {
            throw new IllegalArgumentException(name + " is not canonical");
        }
        return normalized;
    }

    private static String requireDigest(String value, String name) {
        String normalized = requireText(value, name);
        if (!normalized.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be SHA-256 hex");
        return normalized;
    }

    private static String requireText(String value, String name) {
        return OnlyDocumentIds.canonicalValue(value, name);
    }
}
