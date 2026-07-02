package com.dylan.agent.metadata.profile.model;

import java.util.Objects;

/** Exact immutable profile version key. */
public record AgentProfileVersionKey(String agentId, String version) {
    public AgentProfileVersionKey {
        agentId = requireNonBlank(agentId, "agentId");
        version = requireNonBlank(version, "version");
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
