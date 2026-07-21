package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** 仅从短生命周期 raw scope 与 DAE-1 evidence 构建 schema-v3 protected filter。 */
public final class DocumentProtectedFilterFactory {
    private final DocumentProtectedFilterCanonicalizer canonicalizer;

    public DocumentProtectedFilterFactory(DocumentAclCompilerLimits limits) {
        this.canonicalizer = new DocumentProtectedFilterCanonicalizer(limits);
    }

    public DocumentProtectedFilterBinding build(
            DocumentAclScopeSnapshot scope,
            DocumentAclExecutionEvidence evidence) {
        List<DocumentProtectedFilterNode> visibility = new ArrayList<>();
        visibility.add(new DocumentExactTerm(DocumentAclIndexField.VISIBILITY, "PUBLIC"));
        visibility.add(new DocumentExactTerm(DocumentAclIndexField.VISIBILITY, "TENANT"));
        visibility.add(new DocumentAllOf(List.of(
                new DocumentExactTerm(DocumentAclIndexField.VISIBILITY, "USER"),
                new DocumentAnyTerms(DocumentAclIndexField.USER_IDS, Set.of(scope.subjectPrincipalId())))));
        addVisibility(visibility, "DEPARTMENT", DocumentAclIndexField.DEPARTMENT_IDS, scope.departmentIds());
        addVisibility(visibility, "ROLE", DocumentAclIndexField.ROLE_IDS, scope.roleIds());
        addVisibility(visibility, "ATTRIBUTE", DocumentAclIndexField.ATTRIBUTE_KEYS, scope.attributeKeys());

        List<DocumentProtectedFilterNode> roots = new ArrayList<>();
        roots.add(new DocumentExactTerm(DocumentAclIndexField.TENANT_ID, scope.tenantId()));
        roots.add(new DocumentExactTerm(DocumentAclIndexField.STATUS, "ACTIVE"));
        if (scope.documentIdConstraint() instanceof OnlyDocumentIds only) {
            roots.add(new DocumentAnyTerms(DocumentAclIndexField.DOCUMENT_ID, only.documentIds()));
        }
        roots.add(new DocumentAnyOf(visibility));
        if (!scope.deniedDocumentIds().isEmpty()) {
            roots.add(new DocumentNoneTerms(DocumentAclIndexField.DOCUMENT_ID, scope.deniedDocumentIds()));
        }
        DocumentProtectedFilterNode root = new DocumentAllOf(roots);
        String filterDigest = canonicalizer.digest(
                evidence.corpusKey(), root, evidence.canonicalDigest(), evidence.profileProjectionDigest(),
                evidence.resourceLimitReference());
        return new DocumentProtectedFilterBinding(
                evidence.corpusKey(), root, filterDigest, evidence.canonicalDigest(),
                evidence.profileProjectionDigest(), evidence.resourceLimitReference());
    }
    private static void addVisibility(List<DocumentProtectedFilterNode> target, String visibility, DocumentAclIndexField field, Set<String> values) {
        if (values != null && !values.isEmpty()) target.add(new DocumentAllOf(List.of(new DocumentExactTerm(DocumentAclIndexField.VISIBILITY, visibility), new DocumentAnyTerms(field, Set.copyOf(values)))));
    }
}
