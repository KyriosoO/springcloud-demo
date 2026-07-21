package com.dylan.agent.capability.document.acl;

import java.time.Duration;

/** ACL authority parser 与 filter compiler 的 operational/security cap。 */
public record DocumentAclCompilerLimits(
        int maxDepartments,
        int maxRoles,
        int maxAttributes,
        int maxAllowedDocumentIds,
        int maxDeniedDocumentIds,
        int maxAstNodes,
        int maxAstDepth,
        int maxTerms,
        int maxCanonicalBytes,
        int maxWireBytes,
        int maxCurrentnessCandidates,
        Duration maxAuthorityEvidenceTtl) {

    public DocumentAclCompilerLimits {
        if (maxDepartments < 1 || maxRoles < 1 || maxAttributes < 1
                || maxAllowedDocumentIds < 1 || maxDeniedDocumentIds < 1
                || maxAstNodes < 1 || maxAstDepth < 1 || maxTerms < 1
                || maxCanonicalBytes < 1 || maxWireBytes < 1 || maxCurrentnessCandidates < 1) {
            throw new IllegalArgumentException("ACL compiler limits must be positive");
        }
        if (maxAuthorityEvidenceTtl == null || maxAuthorityEvidenceTtl.isZero()
                || maxAuthorityEvidenceTtl.isNegative()) {
            throw new IllegalArgumentException("maxAuthorityEvidenceTtl must be positive");
        }
    }

    public static DocumentAclCompilerLimits secureDefaults() {
        return new DocumentAclCompilerLimits(
                128, 128, 128, 512, 512, 64, 8, 1024,
                128 * 1024, 256 * 1024, 200, Duration.ofMinutes(30));
    }

    void validateScope(DocumentAclScopeSnapshot scope) {
        requireAtMost(scope.departmentIds().size(), maxDepartments, "departmentIds");
        requireAtMost(scope.roleIds().size(), maxRoles, "roleIds");
        requireAtMost(scope.attributeKeys().size(), maxAttributes, "attributeKeys");
        if (scope.documentIdConstraint() instanceof OnlyDocumentIds only) {
            requireAtMost(only.documentIds().size(), maxAllowedDocumentIds, "allowedDocumentIds");
        }
        requireAtMost(scope.deniedDocumentIds().size(), maxDeniedDocumentIds, "deniedDocumentIds");
        if (Duration.between(scope.issuedAt(), scope.expiresAt()).compareTo(maxAuthorityEvidenceTtl) > 0) {
            throw new IllegalArgumentException("ACL authority evidence TTL exceeds cap");
        }
    }

    private static void requireAtMost(int actual, int maximum, String field) {
        if (actual > maximum) throw new IllegalArgumentException(field + " exceeds ACL compiler cap");
    }
}
