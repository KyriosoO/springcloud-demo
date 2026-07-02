package com.dylan.agent.metadata.config;

import java.time.Duration;
import java.util.Objects;

/** Startup/reload validation for metadata instance config. */
public final class AgentMetadataPropertiesValidator {

    private AgentMetadataPropertiesValidator() {
    }

    public static void validate(AgentMetadataProperties properties) {
        Objects.requireNonNull(properties, "properties must not be null");
        requireNonBlank(properties.getBundleVersion(), "agent.metadata.bundle-version");
        requireNonBlank(properties.getDefaultProfileId(), "agent.metadata.default-profile-id");
        Duration timeout = Objects.requireNonNull(
                properties.getReloadValidationTimeout(),
                "agent.metadata.reload-validation-timeout must not be null");
        if (timeout.compareTo(Duration.ofMillis(100)) < 0 || timeout.compareTo(Duration.ofSeconds(30)) > 0) {
            throw new IllegalStateException("agent.metadata.reload-validation-timeout must be between 100ms and 30s");
        }
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalStateException(name + " must not be blank");
        }
        return normalized;
    }
}
