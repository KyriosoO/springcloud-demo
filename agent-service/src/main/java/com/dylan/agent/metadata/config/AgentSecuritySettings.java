package com.dylan.agent.metadata.config;

import java.time.Duration;
import java.util.Objects;

/**
 * 当前 metadata bundle 中的安全设置快照。
 */
public record AgentSecuritySettings(
        Duration globalMaxContextTtl,
        Duration contextCleanupDelay,
        int contextCleanupBatchSize,
        String activePayloadKeyId) {

    public AgentSecuritySettings {
        Objects.requireNonNull(globalMaxContextTtl, "globalMaxContextTtl must not be null");
        Objects.requireNonNull(contextCleanupDelay, "contextCleanupDelay must not be null");
        activePayloadKeyId = requireNonBlank(activePayloadKeyId, "activePayloadKeyId");
        if (globalMaxContextTtl.isZero() || globalMaxContextTtl.isNegative()) {
            throw new IllegalArgumentException("globalMaxContextTtl must be positive");
        }
        if (contextCleanupDelay.isNegative()) {
            throw new IllegalArgumentException("contextCleanupDelay must not be negative");
        }
        if (contextCleanupBatchSize < 1 || contextCleanupBatchSize > 1000) {
            throw new IllegalArgumentException("contextCleanupBatchSize must be 1-1000");
        }
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
