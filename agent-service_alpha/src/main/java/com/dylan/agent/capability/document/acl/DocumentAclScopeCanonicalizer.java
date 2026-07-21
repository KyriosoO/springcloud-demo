package com.dylan.agent.capability.document.acl;

import java.util.Set;

final class DocumentAclScopeCanonicalizer {
    String digest(
            String tenantId,
            String subjectPrincipalId,
            Set<String> departmentIds,
            Set<String> roleIds,
            Set<String> attributeKeys,
            DocumentIdConstraint documentIdConstraint,
            Set<String> deniedDocumentIds,
            String authorityVersion,
            String permissionVersion,
            String issuedAt,
            String expiresAt,
            String authorityEvidenceRef) {
        return DocumentAclCanonicalDigests.digest("DAS-1",
                tenantId, subjectPrincipalId,
                canonicalSet(departmentIds), canonicalSet(roleIds), canonicalSet(attributeKeys),
                canonicalConstraint(documentIdConstraint), canonicalSet(deniedDocumentIds),
                authorityVersion, permissionVersion, issuedAt, expiresAt, authorityEvidenceRef);
    }

    private static String canonicalConstraint(DocumentIdConstraint constraint) {
        if (constraint instanceof AllPrincipalVisibleDocuments) return "ALL";
        if (constraint instanceof OnlyDocumentIds only) return "ONLY:" + canonicalSet(only.documentIds());
        throw new IllegalArgumentException("unknown document id constraint");
    }

    static String canonicalSet(Set<String> values) {
        return values.stream().sorted().map(DocumentAclScopeCanonicalizer::lengthPrefixed)
                .reduce("", String::concat);
    }

    private static String lengthPrefixed(String value) {
        return value.length() + ":" + value;
    }
}
