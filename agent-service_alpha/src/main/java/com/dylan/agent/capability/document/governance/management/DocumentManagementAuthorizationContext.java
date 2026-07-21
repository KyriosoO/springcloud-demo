package com.dylan.agent.capability.document.governance.management;

import java.time.Instant;
import java.util.Objects;
import java.util.Set;

/** 由认证边界构造的管理上下文，不接受 request body 自报 actor/scope。 */
public record DocumentManagementAuthorizationContext(
        String serviceSubject,
        String actorSafeRef,
        Set<DocumentManagementScope> scopes,
        Instant authenticatedAt,
        String authenticationEvidenceDigest) {
    public DocumentManagementAuthorizationContext {
        serviceSubject = requireText(serviceSubject, "serviceSubject");
        actorSafeRef = requireText(actorSafeRef, "actorSafeRef");
        scopes = Set.copyOf(Objects.requireNonNull(scopes, "scopes must not be null"));
        Objects.requireNonNull(authenticatedAt, "authenticatedAt must not be null");
        if (authenticationEvidenceDigest == null || !authenticationEvidenceDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("authenticationEvidenceDigest must be SHA-256 hex");
        }
    }

    public void require(DocumentManagementScope scope) {
        if (!scopes.contains(scope)) throw new SecurityException("required document management scope is absent");
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
        return value;
    }
}
