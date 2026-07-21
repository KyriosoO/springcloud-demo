package com.dylan.agent.planning.model;

import java.time.Instant;

/** PAI-1：Planning Artifact 的逻辑身份与安全绑定摘要。 */
public record PlanningArtifactIdentity(
        String invocationId,
        String requestCorrelationId,
        String registrationIdentity,
        String authorizationSnapshotRef,
        String contextSnapshotSetDigest,
        Instant absoluteDeadline,
        String bindingDigest) {

    public PlanningArtifactIdentity {
        requireText(invocationId, "invocationId");
        requireText(requestCorrelationId, "requestCorrelationId");
        requireText(registrationIdentity, "registrationIdentity");
        requireText(authorizationSnapshotRef, "authorizationSnapshotRef");
        requireDigest(contextSnapshotSetDigest, "contextSnapshotSetDigest");
        if (absoluteDeadline == null) {
            throw new IllegalArgumentException("absoluteDeadline must not be null");
        }
        requireDigest(bindingDigest, "bindingDigest");
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }

    private static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
    }
}
