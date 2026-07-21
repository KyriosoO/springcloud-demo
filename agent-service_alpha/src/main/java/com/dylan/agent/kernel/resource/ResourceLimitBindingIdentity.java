package com.dylan.agent.kernel.resource;

import java.time.Instant;

/** 有效资源限额与当前 Invocation/Registration/授权证据的绑定。 */
public record ResourceLimitBindingIdentity(
        String invocationId,
        String requestCorrelationId,
        String registrationIdentity,
        String authorizationEvidenceDigest,
        Instant frozenAt) {

    public ResourceLimitBindingIdentity {
        requireText(invocationId, "invocationId");
        requireText(requestCorrelationId, "requestCorrelationId");
        requireText(registrationIdentity, "registrationIdentity");
        requireText(authorizationEvidenceDigest, "authorizationEvidenceDigest");
        if (frozenAt == null) {
            throw new IllegalArgumentException("frozenAt must not be null");
        }
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}
